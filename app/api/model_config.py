"""
模型配置接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.log import logger
from app.schemas.custom_model import CustomModelConfig, CustomModelInfo, LLModelID
from app.services.custom_model import custom_model_manager

router = APIRouter(prefix="/models", tags=["Model Config"])


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    available: bool


class CustomModelRequest(BaseModel):
    name: str
    provider: str
    api_url: str
    api_key: str
    model_name: str
    api_model_name: str  # API调用时使用的正确模型名称


class UpdateCustomModelRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    api_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    api_model_name: str | None = None  # API调用时使用的正确模型名称


_DEFAULT_API_URL = {
    "Deepseek": "https://api.deepseek.com/v1",
}


@router.post("/custom")
async def set_custom_model(request: CustomModelRequest) -> dict:
    """设置自定义模型配置"""
    try:
        config = CustomModelConfig(
            id=f"custom-{hash(request.api_url + request.model_name) % 100000}",
            name=request.name,
            provider=request.provider,
            api_url=request.api_url or _DEFAULT_API_URL.get(request.provider, ""),
            api_key=request.api_key,
            model_name=request.model_name,
            api_model_name=request.api_model_name,
        )
        await custom_model_manager.add_model(config)
        logger.info(f"设置自定义模型: {config.name} ({config.id})")
        return {"success": True, "message": "自定义模型配置成功", "model_id": config.id}
    except Exception as e:
        logger.error(f"设置自定义模型失败: {e}")
        raise HTTPException(status_code=500, detail="设置自定义模型失败") from e


@router.put("/custom/{model_id}")
async def update_custom_model(model_id: LLModelID, request: UpdateCustomModelRequest) -> dict:
    """更新自定义模型配置"""
    try:
        # 过滤掉None值
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="没有提供要更新的数据")

        success = await custom_model_manager.update_model(model_id, **update_data)
        if not success:
            raise HTTPException(status_code=404, detail="自定义模型未找到")

        logger.info(f"更新自定义模型: {model_id}")
        return {"success": True, "message": "自定义模型更新成功", "model_id": model_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新自定义模型失败: {e}")
        raise HTTPException(status_code=500, detail="更新自定义模型失败") from e


@router.get("/custom/{model_id}", response_model=CustomModelInfo)
async def get_custom_model(model_id: LLModelID) -> CustomModelConfig:
    """获取自定义模型配置（不返回API密钥）"""
    config = custom_model_manager.get_model(model_id)
    if not config:
        raise HTTPException(status_code=404, detail="自定义模型未找到")
    return config


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


@router.get("/available")
async def get_available_models() -> ModelsResponse:
    """获取可用的模型列表"""
    models = []

    # 获取自定义模型
    custom_models = custom_model_manager.list_models()

    # 只返回用户自定义的模型
    for model_config in custom_models.values():
        # 检查自定义模型是否有有效的API密钥
        is_available = bool(model_config.api_key and model_config.api_key.strip())
        model = ModelInfo(
            id=model_config.id,
            name=model_config.name,
            provider=model_config.provider,
            available=is_available,
        )
        models.append(model)

    logger.info(f"返回 {len(models)} 个自定义模型，其中 {len([m for m in models if m.available])} 个可用")
    return ModelsResponse(models=models)


@router.delete("/custom/{model_id}")
async def delete_custom_model(model_id: LLModelID) -> dict:
    """删除自定义模型配置"""
    try:
        success = await custom_model_manager.remove_model(model_id)
        if not success:
            raise HTTPException(status_code=404, detail="自定义模型未找到")

        logger.info(f"删除自定义模型: {model_id}")
        return {"success": True, "message": "自定义模型删除成功", "model_id": model_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除自定义模型失败: {e}")
        raise HTTPException(status_code=500, detail="删除自定义模型失败") from e
