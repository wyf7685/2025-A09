"""
对话式数据分析接口
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.log import logger
from app.schemas.chat import ChatEntry, UserChatMessage
from app.services.agent import AgentInUse, AgentNotFound, daa_service
from app.services.session import session_service

router = APIRouter(prefix="/chat")


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_id: str = "gemini-2.0-flash"  # 默认模型

    @field_validator("message", mode="after")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证消息内容是否为空"""
        if not v or not v.strip():
            raise ValueError("Message is required")
        return v.strip()


async def generate_chat_stream(request: ChatRequest) -> AsyncIterator[str]:
    """生成聊天流响应"""
    session = session_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_id = session.id

    try:
        async with daa_service.use_agent(session, request.model_id, create_if_non_exist=True) as agent:
            # 初始化响应变量
            chat_entry = ChatEntry(user_message=UserChatMessage(content=request.message))

            # 流式输出
            async for event in agent.astream(request.message):
                try:
                    msg = event.model_dump_json() + "\n"
                except Exception:
                    logger.exception("转换事件为 JSON 失败")
                else:
                    yield msg

                chat_entry.add_stream_event(event)

            chat_entry.merge_text()

            # 如果这是第一条消息，设置会话名称
            if len(session.chat_history) == 0:
                session.name = await agent.create_title_async()
                logger.info(f"设置会话 {session_id} 名称为: {session.name}")

        # 记录对话历史
        session.chat_history.append(chat_entry)
        session_service.save_session(session)

        # 发送完成信号
        yield json.dumps({"type": "done", "timestamp": datetime.now().isoformat()})

    except AgentInUse:
        logger.warning(f"会话 {session.id} 的 Agent 正在使用中")
        yield json.dumps({"error": f"会话 {session.id} 的 Agent 正在使用中"})

    except Exception as e:
        logger.exception("流式对话分析失败")
        yield json.dumps({"error": str(e)})


@router.post("/stream")
async def chat_analysis_stream(request: ChatRequest) -> StreamingResponse:
    """对话式数据分析（流式输出）"""
    return StreamingResponse(generate_chat_stream(request), media_type="text/event-stream")


class SummaryRequest(BaseModel):
    session_id: str
    model_id: str | None = None


class SummaryResponse(BaseModel):
    session_id: str
    summary: str
    figures: list[str]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


@router.post("/summary")
async def chat_summary(request: SummaryRequest) -> SummaryResponse:
    """获取对话摘要"""
    session = session_service.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        async with daa_service.use_agent(session, request.model_id, create_if_non_exist=False) as agent:
            summary, figures = await agent.summary_async()
            return SummaryResponse(
                session_id=session.id,
                summary=summary,
                figures=figures,
            )
    except AgentInUse:
        raise HTTPException(status_code=503, detail="Agent is currently in use, please try again later") from None
    except AgentNotFound:
        raise HTTPException(status_code=404, detail="Agent not found for this session") from None
    except Exception as e:
        logger.exception("获取对话摘要失败")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {e}") from e
