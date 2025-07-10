"""
会话管理接口
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.datasources import datasources
from app.log import logger


class Session(BaseModel):
    id: str
    dataset_id: str
    name: str = Field(default="新会话")
    chat_history: list[dict[str, Any]] = []
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# 模拟数据存储，在实际项目中应替换为数据库
sessions: dict[str, Session] = {}

router = APIRouter()


class CreateSessionRequest(BaseModel):
    dataset_id: str


@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> Session:
    """
    创建新会话

    必须指定一个数据集用于分析
    """
    try:
        # 检查数据集是否存在

        if request.dataset_id not in datasources:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # 创建新会话
        session_id = str(uuid.uuid4())

        # 设置会话的数据集
        sessions[session_id] = Session(id=session_id, dataset_id=request.dataset_id)

        return sessions[session_id]

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}") from e


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Session:
    """获取会话信息"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return sessions[session_id]


class SessionListItem(BaseModel):
    id: str
    name: str
    created_at: str
    chat_count: int


@router.get("/sessions")
async def get_sessions() -> list[SessionListItem]:
    """获取所有会话列表"""
    try:
        session_list = [
            SessionListItem(
                id=session.id,
                name=f"会话 {session.id[:8]}",
                created_at=session.created_at,
                chat_count=len(session.chat_history),
            )
            for session in sessions.values()
        ]

        # 按创建时间倒序排列
        session_list.sort(key=lambda x: x.created_at, reverse=True)

        return session_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {e}") from e


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """删除会话"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # 删除会话
    del sessions[session_id]
    return {"success": True, "message": f"Session {session_id} deleted"}
