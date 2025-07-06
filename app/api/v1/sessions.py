"""
会话管理接口
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

# 模拟数据存储，在实际项目中应替换为数据库
sessions: dict[str, dict[str, Any]] = {}

router = APIRouter()


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


@router.post("/sessions")
async def create_session() -> dict[str, Any]:
    """创建新会话"""
    session_id = get_or_create_session()
    return {"session_id": session_id, "session": sessions[session_id]}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """获取会话信息"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"session": sessions[session_id]}


@router.get("/sessions")
async def get_sessions() -> list[dict[str, Any]]:
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

        return session_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {e}") from e
