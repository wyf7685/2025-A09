"""
模型管理接口
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.v1.chat import agents
from app.log import logger

router = APIRouter()


class CreateModelRequest(BaseModel):
    name: str
    type: str
    description: str | None = ""
    config: dict[str, Any] = {}


class UpdateModelRequest(BaseModel):
    status: str


@router.get("/models")
async def get_trained_models(session_id: str) -> dict[str, dict[str, Any]]:
    """获取已训练的模型列表"""
    try:
        if not session_id or session_id not in agents:
            raise HTTPException(status_code=404, detail="Session agent not found")

        return {"models": agents[session_id].trained_models}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取模型列表失败")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {e}") from e


@router.post("/models")
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


@router.put("/models/{model_id}")
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


@router.delete("/models/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    """删除模型"""
    try:
        # 这里应该实际删除模型
        # 目前只是返回成功响应
        return {"success": True, "model_id": model_id}

    except Exception as e:
        logger.exception("删除模型失败")
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {e}") from e
