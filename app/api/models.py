"""
模型管理接口
"""

import secrets
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.log import logger
from app.schemas.ml_model import MLModelInfoOut
from app.schemas.session import SessionID
from app.services.datasource import temp_file_service
from app.services.model_registry import model_registry

router = APIRouter(prefix="/models", tags=["ML Models"])


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


class GetModelLinkResponse(BaseModel):
    path: str


@router.get("/{model_id}/link")
async def get_model_link(model_id: str) -> GetModelLinkResponse:
    """获取模型文件下载链接"""
    try:
        archive_file_id = await model_registry.pack_model(model_id)
        entry = temp_file_service.get_entry(archive_file_id)
        assert entry is not None, "Temporary file entry should exist"
        metadata = entry[1]
        metadata["filename"] = f"model_{model_id}.zip"
        metadata["token"] = token = secrets.token_urlsafe(32)
        return GetModelLinkResponse(path=f"/files/{archive_file_id}?token={token}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Model not found") from e
    except Exception as e:
        logger.exception("下载模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to download model: {e}") from e
