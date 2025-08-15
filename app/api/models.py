"""
模型管理接口
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.log import logger
from app.schemas.ml_model import MLModelInfoOut
from app.schemas.session import SessionID
from app.services.model_registry import model_registry

router = APIRouter(prefix="/models")


class GetModelsResponse(BaseModel):
    models: list[MLModelInfoOut]


@router.get("")
async def get_trained_models(session_id: SessionID) -> dict[str, Sequence[MLModelInfoOut]]:
    """获取已训练的模型列表"""
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")

        return {"models": model_registry.list_models(session_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取模型列表失败")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {e}") from e


@router.get("/all")
async def get_all_models() -> dict[str, Sequence[MLModelInfoOut]]:
    """获取所有模型列表"""
    try:
        return {"models": model_registry.list_models()}
    except Exception as e:
        logger.exception("获取所有模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to get all models: {e}") from e


class CreateModelRequest(BaseModel):
    name: str
    type: str
    description: str | None = ""
    config: dict[str, Any] = {}


@router.post("")
async def create_model(request: CreateModelRequest) -> dict[str, Any]:
    """创建新模型"""
    try:
        model_name = request.name
        model_type = request.type
        description = request.description
        config = request.config

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

        return {"success": True, "model": model_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to create model: {e}") from e


class UpdateModelRequest(BaseModel):
    status: str


@router.put("/{model_id}")
async def update_model(model_id: str, request: UpdateModelRequest) -> dict[str, Any]:
    """更新模型状态"""
    try:
        status = request.status

        # 这里应该实际更新模型状态
        # 目前只是返回成功响应
        return {"success": True, "model_id": model_id, "status": status}

    except Exception as e:
        logger.exception("更新模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to update model: {e}") from e


@router.delete("/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    """删除模型"""
    try:
        # 从模型注册表删除模型
        success = await model_registry.delete_model(model_id)

        if not success:
            raise HTTPException(status_code=404, detail="Model not found")

        return {"success": True, "model_id": model_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {e}") from e


@router.get("/{model_id}")
async def download_model(model_id: str) -> FileResponse:
    """下载模型文件"""
    try:
        model_archive = await model_registry.pack_model(model_id)
        return FileResponse(model_archive, media_type="application/zip", filename=f"model_{model_id}.zip")
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Model not found") from e
    except Exception as e:
        logger.exception("下载模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to download model: {e}") from e
