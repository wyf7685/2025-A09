"""
对话式数据分析接口
"""

import json
import re
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.v1.sessions import sessions
from app.api.v1.uploads import datasets
from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain.llm import get_chat_model, get_llm
from app.core.datasource import PandasDataSource
from app.log import logger

router = APIRouter()

# Agent 实例缓存
agents: dict[str, DataAnalyzerAgent] = {}


def clean_message_for_session_name(message: str, max_length: int = 30) -> str:
    """清理并截断消息内容作为会话名称"""
    # 移除多余的空白字符
    cleaned = re.sub(r"\s+", " ", message).strip()

    # 移除特殊字符，保留中英文、数字、常用标点
    cleaned = re.sub(r"[^\u4e00-\u9fa5\w\s\.\?\!\,\:\;\(\)\[\]\-\+\=]", "", cleaned)

    # 如果消息过长，智能截断
    if len(cleaned) > max_length:
        # 尝试在标点符号处截断
        truncate_pos = max_length - 3
        for punct in ["。", "？", "！", ".", "?", "!", "，", ","]:
            punct_pos = cleaned.rfind(punct, 0, truncate_pos)
            if punct_pos > max_length // 2:
                return cleaned[: punct_pos + 1]

        # 如果没有合适的标点，直接截断
        cleaned = cleaned[: max_length - 3] + "..."

    return cleaned if cleaned else "未命名对话"


class ChatRequest(BaseModel):
    session_id: str
    message: str
    dataset_id: str | None = None


async def generate_chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    """生成聊天流响应"""
    try:
        session_id = request.session_id
        user_message = request.message.strip()
        dataset_id = request.dataset_id

        # 基本参数检查
        if not session_id or session_id not in sessions:
            yield json.dumps({"error": "Session not found"})
            return

        if not user_message:
            yield json.dumps({"error": "Message is required"})
            return

        # 获取当前数据集
        if not dataset_id:
            dataset_id = sessions[session_id]["current_dataset"]

        if not dataset_id or dataset_id not in datasets:
            yield json.dumps({"error": "No dataset available"})
            return

        df = datasets[dataset_id]

        # 获取或创建 Agent
        if session_id not in agents:
            agents[session_id] = DataAnalyzerAgent(PandasDataSource(df), get_llm(), get_chat_model())
            agents[session_id].load_state(STATE_DIR / f"{session_id}.json")

        agent = agents[session_id]

        # 在获取 agent 后，检查消息历史
        if not agent.get_first_user_message():
            # 自动补充一条系统欢迎消息或数据集概览
            agent.stream("请对当前数据集进行基本描述")  # 或自定义一句欢迎/引导语

        # 开始时间
        start_time = datetime.now().isoformat()

        # 初始化响应变量
        full_response = ""

        # 流式输出
        async for event in agent.astream(user_message):
            match event.type:
                case "llm_token":
                    full_response += event.content
                    yield json.dumps({"type": "message", "content": event.content}) + "\n"
                case "tool_call" | "tool_result" | "tool_error":
                    try:
                        msg = event.model_dump_json() + "\n"
                    except Exception:
                        logger.exception("转换事件为 JSON 失败")
                    else:
                        yield msg

        # 保存状态
        agent.save_state(STATE_DIR / f"{session_id}.json")

        # 如果这是第一条消息，设置会话名称
        if len(sessions[session_id]["chat_history"]) == 0:
            session_name = clean_message_for_session_name(user_message)
            sessions[session_id]["name"] = session_name
            logger.info(f"设置会话 {session_id} 名称为: {session_name}")

        # 记录对话历史
        chat_entry = {
            "timestamp": start_time,
            "user_message": user_message,
            "ai_response": full_response,
        }

        sessions[session_id]["chat_history"].append(chat_entry)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()})

    except Exception as e:
        logger.exception("流式对话分析失败")
        yield json.dumps({"error": str(e)})


@router.post("/chat/stream")
async def chat_analysis_stream(request: ChatRequest) -> StreamingResponse:
    """对话式数据分析（流式输出）"""
    return StreamingResponse(generate_chat_stream(request), media_type="text/event-stream")
