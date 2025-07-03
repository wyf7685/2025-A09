import base64
import datetime
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from src.chain import GeneralDataAnalysis, NL2DataAnalysis, get_llm
from src.dremio_client import DremioClient

app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# 全局存储
chat_sessions = {}  # 存储聊天会话
current_datasets = {}  # 存储当前数据集


def safe_convert_for_json(obj):
    """处理JSON序列化问题"""
    if isinstance(obj, (np.integer, np.int64)):  # type: ignore
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif pd.isna(obj):
        return None
    return obj


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """文件上传接口"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "没有上传文件"}), 400

        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "文件名为空"}), 400

        if not file.filename.lower().endswith(".csv"):
            return jsonify({"error": "仅支持 CSV 文件"}), 400

        # 保存文件
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = app.config["UPLOAD_FOLDER"] / f"{file_id}_{filename}"
        file.save(file_path)

        # 使用DremioClient读取数据
        with DremioClient().data_source_csv(file_path) as source:
            df = source.read(limit=5)
            shape = source.shape()

        # 存储数据集
        dataset_info = {
            "id": file_id,
            "filename": filename,
            "file_path": str(file_path),
            "shape": [int(shape[0]), int(shape[1])],
            "columns": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
        }

        current_datasets[file_id] = {"info": dataset_info, "dataframe": df}

        # 创建新的聊天会话
        session_id = str(uuid.uuid4())
        chat_sessions[session_id] = {
            "dataset_id": file_id,
            "messages": [],
            "created_at": datetime.datetime.now().isoformat(),
        }

        return jsonify(
            {
                "success": True,
                "message": f"文件 {filename} 上传成功！",
                "dataset": dataset_info,
                "session_id": session_id,
                "data_preview": {
                    "shape": dataset_info["shape"],
                    "columns": dataset_info["columns"],
                    "sample": df.to_dict("records"),
                },
            }
        )

    except Exception as e:
        return jsonify({"error": f"上传文件时出错: {str(e)}"}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """对话分析接口"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        message = data.get("message")

        if not session_id or session_id not in chat_sessions:
            return jsonify({"error": "无效的会话ID"}), 400

        if not message or not message.strip():
            return jsonify({"error": "消息不能为空"}), 400

        session = chat_sessions[session_id]
        dataset_id = session["dataset_id"]

        if dataset_id not in current_datasets:
            return jsonify({"error": "数据集不存在"}), 404

        df = current_datasets[dataset_id]["dataframe"]

        # 添加用户消息到会话
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        session["messages"].append(user_message)

        # 使用NL2DataAnalysis进行分析
        llm = get_llm()
        analyzer = NL2DataAnalysis(llm, "docker")  # 使用docker模式提高安全性

        result = analyzer.invoke((df, message))

        # 处理分析结果
        assistant_response = {
            "role": "assistant",
            "timestamp": datetime.datetime.now().isoformat(),
            "success": result["success"],
        }

        if result["success"]:
            response_content = "✅ 分析完成\n\n"

            # 添加执行输出
            if result["output"]:
                response_content += f"**执行结果:**\n```\n{result['output']}\n```\n\n"

            # 添加计算结果
            if result["result"] is not None:
                if isinstance(result["result"], pd.DataFrame):
                    if len(result["result"]) <= 10:
                        response_content += f"**数据结果:**\n```\n{result['result'].to_string()}\n```\n\n"
                    else:
                        response_content += f"**数据结果:** (显示前10行)\n```\n{result['result'].head(10).to_string()}\n```\n\n"

                    # 存储完整结果供下载
                    assistant_response["data_result"] = {
                        "type": "dataframe",
                        "data": result["result"].to_dict("records"),
                        "columns": result["result"].columns.tolist(),
                    }
                elif isinstance(result["result"], pd.Series):
                    response_content += (
                        f"**计算结果:**\n```\n{result['result'].to_string()}\n```\n\n"
                    )
                    assistant_response["data_result"] = {
                        "type": "series",
                        "data": result["result"].to_dict(),
                    }
                else:
                    response_content += f"**计算结果:** {result['result']}\n\n"
                    assistant_response["data_result"] = {
                        "type": "value",
                        "data": str(result["result"]),
                    }

            # 处理图表
            if result["figure"]:
                try:
                    img_data = base64.b64encode(result["figure"].getvalue()).decode()
                    assistant_response["figure"] = f"data:image/png;base64,{img_data}"
                    response_content += "📊 **生成了可视化图表**\n\n"
                except Exception as e:
                    print(f"处理图表失败: {e}")

            assistant_response["content"] = response_content
        else:
            assistant_response["content"] = f"❌ 分析失败: {result['error']}"
            assistant_response["error"] = result["error"]

        # 添加助手回复到会话
        session["messages"].append(assistant_response)

        return jsonify(
            {
                "success": True,
                "response": assistant_response,
                "session": {
                    "id": session_id,
                    "message_count": len(session["messages"]),
                },
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"处理对话时出错: {str(e)}"}), 500


@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    """生成智能分析报告"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        focus_areas = data.get("focus_areas", [])

        if not session_id or session_id not in chat_sessions:
            return jsonify({"error": "无效的会话ID"}), 400

        session = chat_sessions[session_id]
        dataset_id = session["dataset_id"]

        if dataset_id not in current_datasets:
            return jsonify({"error": "数据集不存在"}), 404

        df = current_datasets[dataset_id]["dataframe"]

        # 使用GeneralDataAnalysis生成报告
        llm = get_llm()
        analyzer = GeneralDataAnalysis(llm.with_retry(), execute_mode="docker")

        # 处理关注点
        focus_list = (
            [area.strip() for area in focus_areas if area.strip()]
            if focus_areas
            else None
        )

        report, figures = analyzer.invoke((df, focus_list))

        # 处理图片
        figure_data = []
        for i, fig in enumerate(figures):
            img_data = base64.b64encode(fig.getvalue()).decode()
            figure_data.append({"id": i, "data": f"data:image/png;base64,{img_data}"})

        # 添加报告到会话记录
        report_message = {
            "role": "assistant",
            "content": f"📋 **智能分析报告已生成**\n\n{report}",
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "report",
            "figures": figure_data,
        }
        session["messages"].append(report_message)

        return jsonify(
            {
                "success": True,
                "report": report,
                "figures": figure_data,
                "message": "智能分析报告生成成功",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": f"生成报告时出错: {str(e)}"}), 500


@app.route("/api/chat-history/<session_id>", methods=["GET"])
def get_chat_history(session_id):
    """获取聊天历史"""
    if session_id not in chat_sessions:
        return jsonify({"error": "会话不存在"}), 404

    session = chat_sessions[session_id]
    dataset_info = current_datasets.get(session["dataset_id"], {}).get("info", {})

    return jsonify(
        {
            "success": True,
            "session": {
                "id": session_id,
                "dataset": dataset_info,
                "messages": session["messages"],
                "created_at": session["created_at"],
            },
        }
    )


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    """获取所有会话列表"""
    sessions = []
    for session_id, session in chat_sessions.items():
        dataset_info = current_datasets.get(session["dataset_id"], {}).get("info", {})
        sessions.append(
            {
                "id": session_id,
                "dataset_name": dataset_info.get("filename", "Unknown"),
                "message_count": len(session["messages"]),
                "created_at": session["created_at"],
            }
        )

    return jsonify({"success": True, "sessions": sessions})


@app.route("/")
def index():
    """提供前端界面"""
    return render_template_string(
        open("templates/chat_interface.html", encoding="utf-8").read()
    )


if __name__ == "__main__":
    print("🚀 启动对话式AI数据分析平台...")
    print("📱 访问地址: http://localhost:5000")
    print("💡 采用对话形式进行数据分析")

    app.run(debug=True, host="0.0.0.0", port=5000)
