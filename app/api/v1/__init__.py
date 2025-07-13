from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.datasources import router as datasources_router
from app.api.v1.health import router as health_router
from app.api.v1.models import router as models_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.clean import router as clean_router

router = APIRouter(prefix="/api")

# 注册各个路由
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(chat_router)
router.include_router(models_router)
router.include_router(datasources_router)
router.include_router(clean_router, prefix="/clean", tags=["数据清洗"])
