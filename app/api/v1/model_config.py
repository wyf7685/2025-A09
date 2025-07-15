"""
模型配置接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.log import logger
from app.services.custom_model import CustomModelConfig, custom_model_manager

router = APIRouter(prefix="/models")


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


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


@router.post("/custom")
async def set_custom_model(request: CustomModelRequest) -> dict:
    """设置自定义模型配置"""
    try:
        config = CustomModelConfig(
            id=f"custom-{hash(request.api_url + request.model_name) % 100000}",
            name=request.name,
            provider=request.provider,
            api_url=request.api_url,
            api_key=request.api_key,
            model_name=request.model_name,
        )
        custom_model_manager.add_model(config)
        logger.info(f"设置自定义模型: {config.name} ({config.id})")
        return {"success": True, "message": "自定义模型配置成功", "model_id": config.id}
    except Exception as e:
        logger.error(f"设置自定义模型失败: {e}")
        raise HTTPException(status_code=500, detail="设置自定义模型失败") from e


@router.get("/custom/{model_id}")
async def get_custom_model(model_id: str) -> CustomModelConfig:
    """获取自定义模型配置"""
    config = custom_model_manager.get_model(model_id)
    if not config:
        raise HTTPException(status_code=404, detail="自定义模型未找到")
    return config


@router.get("/available")
async def get_available_models() -> ModelsResponse:
    """获取可用的模型列表"""
    models = []

    # Google Models
    if settings.GOOGLE_API_KEY:
        models.extend(
            [
                ModelInfo(id="gemini-2.0-flash", name="Gemini 2.0 Flash", provider="Google", available=True),
                ModelInfo(id="gemini-1.5-pro", name="Gemini 1.5 Pro", provider="Google", available=True),
            ]
        )
    else:
        models.extend(
            [
                ModelInfo(id="gemini-2.0-flash", name="Gemini 2.0 Flash", provider="Google", available=False),
                ModelInfo(id="gemini-1.5-pro", name="Gemini 1.5 Pro", provider="Google", available=False),
            ]
        )

    # OpenAI Models (only if using real OpenAI API)
    if settings.OPENAI_API_KEY and not settings.OPENAI_API_BASE:
        models.extend(
            [
                ModelInfo(id="gpt-4", name="GPT-4", provider="OpenAI", available=True),
                ModelInfo(id="gpt-3.5-turbo", name="GPT-3.5 Turbo", provider="OpenAI", available=True),
            ]
        )
    else:
        models.extend(
            [
                ModelInfo(id="gpt-4", name="GPT-4", provider="OpenAI", available=False),
                ModelInfo(id="gpt-3.5-turbo", name="GPT-3.5 Turbo", provider="OpenAI", available=False),
            ]
        )

    # DeepSeek Models
    if settings.OPENAI_API_KEY and settings.OPENAI_API_BASE:
        models.extend(
            [
                ModelInfo(id="deepseek-chat", name="DeepSeek Chat", provider="DeepSeek", available=True),
                ModelInfo(id="deepseek-coder", name="DeepSeek Coder", provider="DeepSeek", available=True),
            ]
        )
    else:
        models.extend(
            [
                ModelInfo(id="deepseek-chat", name="DeepSeek Chat", provider="DeepSeek", available=False),
                ModelInfo(id="deepseek-coder", name="DeepSeek Coder", provider="DeepSeek", available=False),
            ]
        )

    logger.info(f"返回 {len(models)} 个模型，其中 {len([m for m in models if m.available])} 个可用")
    return ModelsResponse(models=models)
