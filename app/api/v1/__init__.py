from fastapi import APIRouter

from app.api.v1.analysis import router as analysis_router
from app.api.v1.chat import router as chat_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.dremio import router as dremio_router
from app.api.v1.health import router as health_router
from app.api.v1.models import router as models_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.uploads import router as uploads_router

router = APIRouter()

# 注册各个路由
router.include_router(health_router)
router.include_router(sessions_router)
router.include_router(uploads_router)
router.include_router(dremio_router)
router.include_router(chat_router)
router.include_router(analysis_router)
router.include_router(datasets_router)
router.include_router(models_router)
