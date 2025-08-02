"""
MCP连接管理接口
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.exception import MCPServiceError
from app.log import logger
from app.schemas.mcp import Connection, MCPConnection
from app.services.mcp import mcp_service

router = APIRouter(prefix="/mcp-connections", tags=["MCP Connections"])


class CreateMCPConnectionRequest(BaseModel):
    """创建MCP连接请求"""

    name: str
    description: str | None = None
    connection: Connection


@router.post("", response_model=MCPConnection)
async def create_mcp_connection(request: CreateMCPConnectionRequest) -> MCPConnection:
    """
    创建新的MCP连接
    """
    try:
        connection = MCPConnection(
            id=str(uuid.uuid4()),
            name=request.name,
            description=request.description,
            connection=request.connection,
        )

        await mcp_service.register(connection)
        return connection

    except MCPServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("创建MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to create MCP connection: {e}") from e


@router.get("")
async def list_mcp_connections() -> dict[str, MCPConnection]:
    """
    获取所有MCP连接
    """
    try:
        return mcp_service.all()
    except Exception as e:
        logger.exception("获取MCP连接列表失败")
        raise HTTPException(status_code=500, detail=f"Failed to list MCP connections: {e}") from e


@router.get("/{connection_id}")
async def get_mcp_connection(connection_id: str) -> MCPConnection:
    """
    获取指定MCP连接
    """
    try:
        return mcp_service.get(connection_id)
    except MCPServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("获取MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to get MCP connection: {e}") from e


class UpdateMCPConnectionRequest(BaseModel):
    """更新MCP连接请求"""

    name: str | None = None
    description: str | None = None
    connection: Connection | None = None


@router.put("/{connection_id}", response_model=MCPConnection)
async def update_mcp_connection(connection_id: str, request: UpdateMCPConnectionRequest) -> MCPConnection:
    """
    更新MCP连接
    """
    try:
        # 获取现有连接
        existing = mcp_service.get(connection_id)

        # 更新字段
        updated_connection = MCPConnection(
            id=existing.id,
            name=request.name if request.name is not None else existing.name,
            description=request.description if request.description is not None else existing.description,
            connection=request.connection if request.connection is not None else existing.connection,
        )

        # 删除旧连接并添加新连接
        await mcp_service.delete(connection_id)
        await mcp_service.register(updated_connection)

        return updated_connection

    except MCPServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("更新MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to update MCP connection: {e}") from e


@router.delete("/{connection_id}")
async def delete_mcp_connection(connection_id: str) -> dict[str, Any]:
    """
    删除MCP连接
    """
    try:
        await mcp_service.delete(connection_id)
        return {"success": True, "message": f"MCP connection {connection_id} deleted"}
    except MCPServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("删除MCP连接失败")
        raise HTTPException(status_code=500, detail=f"Failed to delete MCP connection: {e}") from e
