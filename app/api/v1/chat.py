"""
对话式数据分析接口
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.api.v1.datasources import datasources
from app.api.v1.sessions import sessions
from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain.llm import get_chat_model, get_llm
from app.log import logger

router = APIRouter()

# Agent 实例缓存
agents: dict[str, DataAnalyzerAgent] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    dataset_id: str | None = None

    @field_validator("session_id", mode="after")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """验证会话ID是否存在"""
        if not v or v not in sessions:
            raise ValueError("Session not found")
        return v

    @field_validator("message", mode="after")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证消息内容是否为空"""
        if not v or not v.strip():
            raise ValueError("Message is required")
        return v.strip()


async def generate_chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    """生成聊天流响应"""
    try:
        session_id = request.session_id
        dataset_id = request.dataset_id

        # 获取当前数据集
        if not dataset_id:
            dataset_id = sessions[session_id].dataset_id

        data_source = datasources[dataset_id]

        # 获取或创建 Agent
        if session_id not in agents:
            agents[session_id] = DataAnalyzerAgent(data_source.copy(), get_llm(), get_chat_model())
            agents[session_id].load_state(STATE_DIR / f"{session_id}.json")

        agent = agents[session_id]

        # 开始时间
        start_time = datetime.now().isoformat()

        # 初始化响应变量
        full_response = ""

        # 流式输出
        async for event in agent.astream(request.message):
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

        # 记录对话历史
        chat_entry = {
            "timestamp": start_time,
            "user_message": request.message,
            "ai_response": full_response,
        }

        sessions[session_id].chat_history.append(chat_entry)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()})

    except Exception as e:
        logger.exception("流式对话分析失败")
        yield json.dumps({"error": str(e)})


@router.post("/chat/stream")
async def chat_analysis_stream(request: ChatRequest) -> StreamingResponse:
    """对话式数据分析（流式输出）"""
    return StreamingResponse(generate_chat_stream(request), media_type="text/event-stream")
