"""
会话管理接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.log import logger
from app.schemas.session import Session, SessionListItem
from app.services.datasource import datasource_service
from app.services.session import session_service

# 模拟数据存储，在实际项目中应替换为数据库
# sessions: dict[str, Session] = {}

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

        if not datasource_service.source_exists(request.dataset_id):
            raise HTTPException(status_code=404, detail="Dataset not found")

        return session_service.create_session(request.dataset_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}") from e


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Session:
    """获取会话信息"""
    if session := session_service.get_session(session_id):
        return session

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions")
async def get_sessions() -> list[SessionListItem]:
    """获取所有会话列表"""
    try:
        return sorted(session_service.list_sessions(), key=lambda x: x.created_at, reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {e}") from e


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    """删除会话"""
    if not session_service.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    session_service.delete_session(session_id)
    return {"success": True, "message": f"Session {session_id} deleted"}
