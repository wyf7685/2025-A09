from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.clean import router as clean_router
from app.api.datasources import router as datasources_router
from app.api.health import router as health_router
from app.api.mcp import router as mcp_router
from app.api.model_config import router as model_config_router
from app.api.models import router as models_router
from app.api.sessions import router as sessions_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(chat_router)
router.include_router(models_router)
router.include_router(model_config_router)
router.include_router(datasources_router)
router.include_router(clean_router)
router.include_router(mcp_router)
