"""
会话管理接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.log import logger
from app.schemas.session import Session, SessionID, SessionListItem
from app.services.datasource import datasource_service
from app.services.session import session_service

router = APIRouter()


class CreateSessionRequest(BaseModel):
    dataset_ids: list[str]


@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> Session:
    """
    创建新会话

    必须指定一个数据集用于分析
    """
    try:
        if not request.dataset_ids:
            raise HTTPException(status_code=400, detail="At least one dataset ID is required")

        # 检查数据集是否存在
        for dataset_id in request.dataset_ids:
            if not await datasource_service.source_exists(dataset_id):
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")

        return await session_service.create_session(request.dataset_ids)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}") from e


class UpdateSessionRequest(BaseModel):
    name: str


@router.put("/sessions/{session_id}", response_model=Session)
async def update_session(session_id: SessionID, request: UpdateSessionRequest) -> Session:
    """
    更新会话信息

    目前支持更新会话名称
    """
    try:
        if not await session_service.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        session = await session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 更新会话名称
        session.name = request.name
        await session_service.save_session(session)

        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {e}") from e


@router.get("/sessions/{session_id}")
async def get_session(session_id: SessionID) -> Session:
    """获取会话信息"""
    if session := await session_service.get_session(session_id):
        return session_service.tool_name_repr(session)

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions")
async def get_sessions() -> list[SessionListItem]:
    """获取所有会话列表"""
    try:
        return sorted(session_service.list_sessions(), key=lambda x: x.created_at, reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {e}") from e


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: SessionID) -> dict[str, Any]:
    """删除会话"""
    try:
        if not await session_service.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        await session_service.delete_session(session_id)
        return {"success": True, "message": f"Session {session_id} deleted"}
    except KeyError as e:
        logger.warning(f"删除会话时出现错误: {e}")
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.exception(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}") from e
