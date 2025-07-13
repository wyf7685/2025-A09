"""
模型配置接口
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.log import logger

router = APIRouter(prefix="/models")


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    available: bool


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


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
