"""
会话管理接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.exception import MCPServerNotFound
from app.log import logger
from app.schemas.custom_model import LLModelID
from app.schemas.mcp import MCPConnection
from app.schemas.ml_model import MLModelInfoOut
from app.schemas.session import Session, SessionID, SessionListItem
from app.services.agent import daa_service
from app.services.datasource import datasource_service
from app.services.mcp import mcp_service
from app.services.model_registry import model_registry
from app.services.session import session_service

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    dataset_ids: list[str]


@router.post("")
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

        return await session_service.create(request.dataset_ids)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}") from e


class UpdateSessionRequest(BaseModel):
    name: str


@router.put("/{session_id}", response_model=Session)
async def update_session(session_id: SessionID, request: UpdateSessionRequest) -> Session:
    """
    更新会话信息

    目前支持更新会话名称
    """
    try:
        if not await session_service.exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 更新会话名称
        session.name = request.name
        await session_service.save_session(session)

        return session_service.tool_name_repr(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {e}") from e


class AgentModelConfigUpdate(BaseModel):
    default: LLModelID | None = None
    chat: LLModelID | None = None
    create_title: LLModelID | None = None
    summary: LLModelID | None = None
    code_generation: LLModelID | None = None


@router.put("/{session_id}/model_config")
async def update_session_model_config(session_id: SessionID, request: AgentModelConfigUpdate) -> None:
    try:
        if not await session_service.exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        for attr, value in request.model_dump().items():
            if value is not None:
                setattr(session.agent_model_config, attr, value)
        await session_service.save_session(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新会话模型配置失败")
        raise HTTPException(status_code=500, detail=f"Failed to update session model config: {e}") from e


@router.get("/{session_id}")
async def get_session(session_id: SessionID) -> Session:
    """获取会话信息"""
    if session := await session_service.get(session_id):
        return session_service.tool_name_repr(session)

    raise HTTPException(status_code=404, detail="Session not found")


@router.get("")
async def get_sessions() -> list[SessionListItem]:
    """获取所有会话列表"""
    try:
        return sorted(session_service.list_all(), key=lambda x: x.created_at, reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {e}") from e


@router.delete("/{session_id}")
async def delete_session(session_id: SessionID) -> dict[str, Any]:
    """删除会话"""
    try:
        if not await session_service.exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        await session_service.delete(session_id)
        return {"success": True, "message": f"Session {session_id} deleted"}
    except KeyError as e:
        logger.warning(f"删除会话时出现错误: {e}")
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.exception(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}") from e


class AddMCPToSessionRequest(BaseModel):
    """向会话添加MCP连接请求"""

    mcp_ids: list[str]


@router.post("/{session_id}/mcp")
async def add_mcp_to_session(session_id: SessionID, request: AddMCPToSessionRequest) -> Session:
    """
    向会话添加MCP连接
    """
    try:
        # 检查会话是否存在
        if not await session_service.exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 检查MCP连接是否存在
        for mcp_id in request.mcp_ids:
            try:
                mcp_service.get(mcp_id)
            except MCPServerNotFound as e:
                raise HTTPException(status_code=e.status_code, detail=str(e)) from e

        # 添加MCP连接ID到会话
        if session.mcp_ids is None:
            session.mcp_ids = []

        # 避免重复添加
        for mcp_id in request.mcp_ids:
            if mcp_id not in session.mcp_ids:
                session.mcp_ids.append(mcp_id)

        # 刷新MCP连接状态
        await daa_service.refresh_mcp(session)

        # 保存会话
        await session_service.save_session(session)

        return session_service.tool_name_repr(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("向会话添加MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to add MCP to session: {e}") from e


class RemoveMCPFromSessionRequest(BaseModel):
    """从会话移除MCP连接请求"""

    mcp_ids: list[str]


@router.delete("/{session_id}/mcp")
async def remove_mcp_from_session(session_id: SessionID, request: RemoveMCPFromSessionRequest) -> Session:
    """
    从会话移除MCP连接
    """
    try:
        # 检查会话是否存在
        if not await session_service.exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 移除MCP连接ID
        if session.mcp_ids:
            for mcp_id in request.mcp_ids:
                if mcp_id in session.mcp_ids:
                    session.mcp_ids.remove(mcp_id)

        # 刷新MCP连接状态
        await daa_service.refresh_mcp(session)

        # 保存会话
        await session_service.save_session(session)

        return session_service.tool_name_repr(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("从会话移除MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to remove MCP from session: {e}") from e


@router.get("/{session_id}/mcp")
async def get_session_mcp_connections(session_id: SessionID) -> list[MCPConnection]:
    """
    获取会话关联的MCP连接
    """
    try:
        # 检查会话是否存在
        if not await session_service.exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        session = await session_service.get(session_id)
        if not session or not session.mcp_ids:
            return []

        connections: list[MCPConnection] = []
        for mcp_id in session.mcp_ids:
            try:
                connections.append(mcp_service.get(mcp_id))
            except MCPServerNotFound:
                # MCP连接不存在，跳过
                logger.warning(f"MCP connection {mcp_id} not found in session {session_id}")
                continue

        return connections

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取会话MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to get session MCP connections: {e}") from e


class AddModelsToSessionRequest(BaseModel):
    model_ids: list[str]


@router.post("/{session_id}/models")
async def add_models_to_session(session_id: SessionID, request: AddModelsToSessionRequest) -> None:
    """向会话添加外部模型引用"""
    try:
        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 检查模型是否存在
        for model_id in request.model_ids:
            model = model_registry.get_model(model_id)
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        # 添加模型ID到会话
        if session.model_ids is None:
            session.model_ids = []

        # 避免重复添加
        for model_id in request.model_ids:
            if model_id not in session.model_ids:
                session.model_ids.append(model_id)

        await session_service.save_session(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("添加模型到会话失败")
        raise HTTPException(status_code=500, detail=f"Failed to add models to session: {e}") from e


class RemoveModelsFromSessionRequest(BaseModel):
    model_ids: list[str]


@router.delete("/{session_id}/models")
async def remove_models_from_session(session_id: SessionID, request: RemoveModelsFromSessionRequest) -> None:
    """从会话中移除模型引用"""
    try:
        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 移除模型ID
        if session.model_ids:
            session.model_ids = [mid for mid in session.model_ids if mid not in request.model_ids]

        await session_service.save_session(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("从会话移除模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to remove models from session: {e}") from e


@router.get("/{session_id}/models", response_model=list[MLModelInfoOut])
async def get_session_models(session_id: SessionID) -> list[MLModelInfoOut]:
    """获取会话关联的所有模型信息"""
    try:
        session = await session_service.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.model_ids:
            return []

        return [model for model_id in session.model_ids if (model := model_registry.get_model(model_id))]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取会话模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to get session models: {e}") from e
