"""
智能数据分析平台 - Flask 后端
"""

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

# 导入现有的分析组件
from app.agent import DataAnalyzerAgent
from app.chain import get_chat_model
from app.chain.general_analysis import GeneralDataAnalysis, GeneralDataAnalysisInput
from app.chain.llm import get_llm, rate_limiter
from app.dremio_client import DremioClient
from app.log import logger

load_dotenv()

# Flask 应用初始化
app = Flask(__name__)
CORS(app)

# 配置
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

# 全局存储
sessions: dict[str, dict[str, Any]] = {}  # 会话管理
datasets: dict[str, pd.DataFrame] = {}  # 数据集缓存
agents: dict[str, DataAnalyzerAgent] = {}  # Agent 实例缓存


def get_or_create_session(session_id: str | None = None) -> str:
    """获取或创建会话"""
    if session_id is None:
        session_id = str(uuid.uuid4())

    if session_id not in sessions:
        sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now().isoformat(),
            "current_dataset": None,
            "chat_history": [],
            "analysis_results": [],
        }

    return session_id


def safe_convert_for_json(obj):
    """处理 JSON 序列化问题"""
    import numpy as np

    if isinstance(obj, (int, np.integer)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif pd.isna(obj):
        return None
    return obj


@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/sessions", methods=["POST"])
def create_session():
    """创建新会话"""
    session_id = get_or_create_session()
    return jsonify({"session_id": session_id, "session": sessions[session_id]})


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """获取会话信息"""
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({"session": sessions[session_id]})


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """获取所有会话列表"""
    try:
        session_list = []
        for session_id, session_data in sessions.items():
            session_list.append(
                {
                    "id": session_id,
                    "name": f"会话 {session_id[:8]}",
                    "created_at": session_data["created_at"],
                    "dataset_loaded": session_data["current_dataset"] is not None,
                    "chat_count": len(session_data["chat_history"]),
                    "analysis_count": len(session_data["analysis_results"]),
                }
            )

        # 按创建时间倒序排列
        session_list.sort(key=lambda x: x["created_at"], reverse=True)

        return jsonify(session_list)
    except Exception as e:
        logger.exception("获取会话列表失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """文件上传接口"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        session_id = request.form.get("session_id")
        if not file or not file.filename or file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        # 确保会话存在
        session_id = get_or_create_session(session_id)

        # 保存文件
        filename = f"{session_id}_{file.filename}"
        filepath = UPLOAD_FOLDER / filename
        file.save(filepath)

        # 读取数据
        try:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(filepath, encoding="utf-8")
            elif file.filename.endswith((".xlsx", ".xls")):
                df = pd.read_excel(filepath)
            else:
                return jsonify({"error": "Unsupported file format"}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to read file: {str(e)}"}), 400

        # 存储数据集
        dataset_id = f"{session_id}_dataset"
        datasets[dataset_id] = df
        sessions[session_id]["current_dataset"] = dataset_id

        # 数据概览
        overview = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head().to_dict(orient="records"),
            "description": df.describe().to_dict(),
        }

        # 安全转换数据
        for record in overview["preview"]:
            for key, value in record.items():
                record[key] = safe_convert_for_json(value)

        return jsonify({"success": True, "session_id": session_id, "dataset_id": dataset_id, "overview": overview})

    except Exception as e:
        logger.exception("文件上传失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/dremio/sources", methods=["GET"])
def get_dremio_sources():
    """获取 Dremio 数据源列表"""
    try:
        client = DremioClient()
        # 模拟数据源列表，实际可能需要查询 catalog
        sources = [
            {"name": "sample_data", "type": "csv", "description": "示例数据"},
            {"name": "postgres_db", "type": "database", "description": "PostgreSQL数据库"},
        ]
        return jsonify({"sources": sources})
    except Exception as e:
        logger.exception("获取 Dremio 数据源失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/dremio/load", methods=["POST"])
def load_dremio_data():
    """从 Dremio 加载数据"""
    try:
        data = request.get_json()
        source_name = data.get("source_name")
        session_id = data.get("session_id")
        fetch_all = data.get("fetch_all", False)

        if not source_name:
            return jsonify({"error": "Source name is required"}), 400

        session_id = get_or_create_session(session_id)

        client = DremioClient()
        df = client.read_source(source_name, fetch_all=fetch_all)

        # 存储数据集
        dataset_id = f"{session_id}_dremio_{source_name}"
        datasets[dataset_id] = df
        sessions[session_id]["current_dataset"] = dataset_id

        # 数据概览
        overview = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head().to_dict(orient="records"),
            "source": source_name,
        }

        return jsonify({"success": True, "session_id": session_id, "dataset_id": dataset_id, "overview": overview})

    except Exception as e:
        logger.exception("从 Dremio 加载数据失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat_analysis():
    """对话式数据分析"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        user_message = data.get("message", "").strip()

        if not session_id or session_id not in sessions:
            return jsonify({"error": "Invalid session"}), 400

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        # 获取当前数据集
        dataset_id = sessions[session_id]["current_dataset"]
        if not dataset_id or dataset_id not in datasets:
            return jsonify({"error": "No dataset loaded"}), 400

        df = datasets[dataset_id]

        # 获取或创建 Agent
        if session_id not in agents:
            limiter = rate_limiter(14)
            llm = limiter | get_llm()
            agents[session_id] = DataAnalyzerAgent(df, llm, get_chat_model(), pre_model_hook=limiter)

            # 加载会话状态（如果存在）
            state_file = Path(f"states/{session_id}.json")
            if state_file.exists():
                agents[session_id].load_state(state_file)

        agent = agents[session_id]

        # 执行分析
        message = agent.invoke(user_message)

        # 保存状态
        state_dir = Path("states")
        state_dir.mkdir(exist_ok=True)
        agent.save_state(state_dir / f"{session_id}.json")

        # 记录对话历史
        chat_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "ai_response": message.content,
            "execution_results": [],
        }

        # 添加执行结果（如果有图表）
        if hasattr(agent, "execution_results") and agent.execution_results:
            latest_results = agent.execution_results[-5:]  # 最近5个结果
            for query, result in latest_results:
                if result.get("figure") and result["figure"] is not None:
                    # 转换图表为 base64
                    figure_b64 = base64.b64encode(result["figure"]).decode()
                    chat_entry["execution_results"].append(
                        {"query": query, "success": result["success"], "output": result["output"], "figure": figure_b64}
                    )

        sessions[session_id]["chat_history"].append(chat_entry)

        return jsonify({"success": True, "response": message.content, "chat_entry": chat_entry})

    except Exception as e:
        logger.exception("对话分析失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis/general", methods=["POST"])
def general_analysis():
    """自动化数据分析报告"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")

        if not session_id or session_id not in sessions:
            return jsonify({"error": "Invalid session"}), 400

        # 获取当前数据集
        dataset_id = sessions[session_id]["current_dataset"]
        if not dataset_id or dataset_id not in datasets:
            return jsonify({"error": "No dataset loaded"}), 400

        df = datasets[dataset_id]

        # 创建分析引擎
        llm = get_llm()
        analysis = GeneralDataAnalysis(llm=llm)

        # 执行分析
        report, figures = analysis.invoke(GeneralDataAnalysisInput(df=df))

        # 转换图表为 base64
        figure_data = []
        for i, fig_bytes in enumerate(figures):
            figure_b64 = base64.b64encode(fig_bytes).decode()
            figure_data.append({"id": i, "data": figure_b64, "format": "png"})

        # 保存分析结果
        analysis_result = {
            "timestamp": datetime.now().isoformat(),
            "report": report,
            "figures": figure_data,
            "dataset_shape": df.shape,
        }

        sessions[session_id]["analysis_results"].append(analysis_result)

        return jsonify({"success": True, "report": report, "figures": figure_data})

    except Exception as e:
        logger.exception("自动分析失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models", methods=["GET"])
def get_trained_models():
    """获取已训练的模型列表"""
    try:
        session_id = request.args.get("session_id")

        if not session_id or session_id not in agents:
            return jsonify({"models": []})

        agent = agents[session_id]
        models = []

        if hasattr(agent, "trained_models"):
            for model_id, model_info in agent.trained_models.items():
                models.append(
                    {
                        "id": model_id,
                        "type": model_info.get("model_type", "unknown"),
                        "features": model_info.get("features", []),
                        "target": model_info.get("target", ""),
                        "score": model_info.get("score", 0),
                        "created_at": model_info.get("created_at", ""),
                    }
                )

        return jsonify({"models": models})

    except Exception as e:
        logger.exception("获取模型列表失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models", methods=["POST"])
def create_model():
    """创建新模型"""
    try:
        data = request.get_json()
        model_name = data.get("name")
        model_type = data.get("type")
        description = data.get("description", "")
        config = data.get("config", {})

        if not model_name or not model_type:
            return jsonify({"error": "Model name and type are required"}), 400

        # 创建模型记录
        model_id = str(uuid.uuid4())
        model_info = {
            "id": model_id,
            "name": model_name,
            "type": model_type,
            "description": description,
            "config": config,
            "status": "created",
            "accuracy": 0.0,
            "version": "v1.0.0",
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
        }

        return jsonify({"success": True, "model": model_info}), 201

    except Exception as e:
        logger.exception("创建模型失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models/<model_id>", methods=["PUT"])
def update_model(model_id: str):
    """更新模型状态"""
    try:
        data = request.get_json()
        status = data.get("status")

        if not status:
            return jsonify({"error": "Status is required"}), 400

        # 这里应该实际更新模型状态
        # 目前只是返回成功响应
        return jsonify({"success": True, "model_id": model_id, "status": status})

    except Exception as e:
        logger.exception("更新模型失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/models/<model_id>", methods=["DELETE"])
def delete_model(model_id: str):
    """删除模型"""
    try:
        # 这里应该实际删除模型
        # 目前只是返回成功响应
        return jsonify({"success": True, "model_id": model_id})

    except Exception as e:
        logger.exception("删除模型失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/report", methods=["POST"])
def export_report():
    """导出分析报告"""
    try:
        data = request.get_json()
        session_id = data.get("session_id")
        report_format = data.get("format", "markdown")  # markdown, pdf, html

        if not session_id or session_id not in sessions:
            return jsonify({"error": "Invalid session"}), 400

        session = sessions[session_id]

        if not session["analysis_results"]:
            return jsonify({"error": "No analysis results to export"}), 400
        # 获取最新的分析结果
        latest_result = session["analysis_results"][-1]
        report_content = latest_result["report"]

        # 创建导出文件
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_report_{session_id}_{timestamp}"
        filepath = None

        if report_format == "markdown":
            filepath = export_dir / f"{filename}.md"
            filepath.write_text(report_content, encoding="utf-8")
        elif report_format == "html":
            # 简单的 HTML 包装
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>数据分析报告</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1, h2, h3 {{ color: #333; }}
                    code {{ background: #f4f4f4; padding: 2px 4px; }}
                    pre {{ background: #f4f4f4; padding: 10px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <div id="content">
                    {report_content.replace("\n", "<br>")}
                </div>
            </body>
            </html>
            """
            filepath = export_dir / f"{filename}.html"
            filepath.write_text(html_content, encoding="utf-8")
        else:
            return jsonify({"error": "Unsupported format"}), 400

        if filepath is None:
            return jsonify({"error": "Failed to create export file"}), 500

        return send_file(filepath, as_attachment=True)

    except Exception as e:
        logger.exception("导出报告失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/datasets", methods=["GET"])
def get_datasets():
    """获取数据集列表"""
    try:
        session_id = request.args.get("session_id")

        if session_id and session_id in sessions:
            # 返回特定会话的数据集
            session = sessions[session_id]
            current_dataset = session["current_dataset"]

            if current_dataset and current_dataset in datasets:
                df = datasets[current_dataset]
                return jsonify(
                    {
                        "datasets": [
                            {
                                "id": current_dataset,
                                "name": current_dataset.split("_", 1)[-1],
                                "shape": df.shape,
                                "columns": df.columns.tolist(),
                                "loaded_at": session["created_at"],
                            }
                        ]
                    }
                )
            else:
                return jsonify({"datasets": []})
        else:
            # 返回所有数据集
            dataset_list = []
            for dataset_id, df in datasets.items():
                dataset_list.append(
                    {"id": dataset_id, "name": dataset_id, "shape": df.shape, "columns": df.columns.tolist()}
                )

            return jsonify({"datasets": dataset_list})

    except Exception as e:
        logger.exception("获取数据集列表失败")
        return jsonify({"error": str(e)}), 500


@app.route("/api/datasets/<dataset_id>/preview", methods=["GET"])
def get_dataset_preview(dataset_id: str):
    """获取数据集预览"""
    try:
        if dataset_id not in datasets:
            return jsonify({"error": "Dataset not found"}), 404

        df = datasets[dataset_id]
        limit = int(request.args.get("limit", 10))

        preview_data = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head(limit).to_dict(orient="records"),
            "statistics": df.describe().to_dict(),
        }

        # 安全转换数据
        for record in preview_data["preview"]:
            for key, value in record.items():
                record[key] = safe_convert_for_json(value)

        return jsonify(preview_data)

    except Exception as e:
        logger.exception("获取数据集预览失败")
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    """根路径 - API文档页面"""
    html_content = (
        """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>智能数据分析平台 - API文档</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background: #f5f7fa;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                text-align: center;
            }
            .header h1 {
                margin: 0;
                font-size: 2.5em;
            }
            .header p {
                margin: 10px 0 0 0;
                opacity: 0.9;
            }
            .status {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .status-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid #eee;
            }
            .status-item:last-child {
                border-bottom: none;
            }
            .status-badge {
                background: #4CAF50;
                color: white;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.9em;
            }
            .api-section {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .api-section h2 {
                color: #333;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }
            .api-endpoint {
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }
            .method {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.8em;
                font-weight: bold;
                margin-right: 10px;
            }
            .method.get { background: #28a745; color: white; }
            .method.post { background: #007bff; color: white; }
            .method.put { background: #ffc107; color: black; }
            .method.delete { background: #dc3545; color: white; }
            .path {
                font-family: monospace;
                background: #e9ecef;
                padding: 2px 6px;
                border-radius: 3px;
            }
            .description {
                margin-top: 10px;
                color: #666;
            }
            .quick-start {
                background: #e8f5e8;
                border: 1px solid #c3e6c3;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            .quick-start h3 {
                color: #2d5a2d;
                margin-top: 0;
            }
            code {
                background: #f1f3f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
            }
            pre {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                border: 1px solid #e9ecef;
            }
            .footer {
                text-align: center;
                padding: 30px;
                color: #666;
                border-top: 1px solid #eee;
                margin-top: 50px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 智能数据分析平台</h1>
            <p>基于 LangChain 的智能数据分析 Web 服务</p>
        </div>

        <div class="status">
            <h2>🚀 服务状态</h2>
            <div class="status-item">
                <span>API 服务</span>
                <span class="status-badge">运行中</span>
            </div>
            <div class="status-item">
                <span>当前时间</span>
                <span id="current-time">加载中...</span>
            </div>
            <div class="status-item">
                <span>活跃会话</span>
                <span id="session-count">"""
        + str(len(sessions))
        + """</span>
            </div>
            <div class="status-item">
                <span>数据集</span>
                <span id="dataset-count">"""
        + str(len(datasets))
        + """</span>
            </div>
        </div>

        <div class="quick-start">
            <h3>🎯 快速开始</h3>
            <p>前端应用地址：<a href="http://localhost:5173" target="_blank">http://localhost:5173</a></p>
            <p>如果前端未启动，请运行：</p>
            <pre><code># Windows
start.bat

# Linux/macOS  
./start.sh</code></pre>
        </div>

        <div class="api-section">
            <h2>📡 API 接口</h2>
            
            <div class="api-endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/health</span>
                <div class="description">健康检查接口</div>
            </div>

            <div class="api-endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/sessions</span>
                <div class="description">获取所有会话列表</div>
            </div>

            <div class="api-endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/sessions</span>
                <div class="description">创建新会话</div>
            </div>

            <div class="api-endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/upload</span>
                <div class="description">上传数据文件 (CSV/Excel)</div>
            </div>

            <div class="api-endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/chat</span>
                <div class="description">对话式数据分析</div>
            </div>

            <div class="api-endpoint">
                <span class="method post">POST</span>
                <span class="path">/api/analysis/general</span>
                <div class="description">自动化数据分析报告</div>
            </div>

            <div class="api-endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/models</span>
                <div class="description">获取模型列表</div>
            </div>

            <div class="api-endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/datasets</span>
                <div class="description">获取数据集列表</div>
            </div>

            <div class="api-endpoint">
                <span class="method get">GET</span>
                <span class="path">/api/dremio/sources</span>
                <div class="description">获取 Dremio 数据源</div>
            </div>
        </div>

        <div class="api-section">
            <h2>🧪 测试 API</h2>
            <p>您可以使用以下命令测试 API：</p>
            <pre><code># 健康检查
curl http://localhost:5000/api/health

# 创建会话
curl -X POST http://localhost:5000/api/sessions \\
     -H "Content-Type: application/json"

# 获取会话列表
curl http://localhost:5000/api/sessions</code></pre>
        </div>

        <div class="footer">
            <p>💡 提示：这是后端 API 服务，请使用前端应用进行完整的数据分析体验</p>
            <p>📚 更多信息请查看项目文档</p>
        </div>

        <script>
            // 更新当前时间
            function updateTime() {
                document.getElementById('current-time').textContent = new Date().toLocaleString('zh-CN');
            }
            
            updateTime();
            setInterval(updateTime, 1000);

            // 定期更新状态
            function updateStatus() {
                fetch('/api/health')
                    .then(response => response.json())
                    .then(data => {
                        console.log('API 健康状态:', data);
                    })
                    .catch(error => {
                        console.error('API 连接失败:', error);
                    });
            }

            setInterval(updateStatus, 30000); // 每30秒检查一次
        </script>
    </body>
    </html>
    """
    )
    return html_content


@app.route("/favicon.ico")
def favicon():
    """处理favicon请求"""
    return "", 204


if __name__ == "__main__":
    # 创建必要的目录
    Path("states").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)

    # 启动应用
    app.run(host="0.0.0.0", port=5000, debug=True)
