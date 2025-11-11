from fastapi import APIRouter

from app.api.agent_source import router as agent_source_router
from app.api.auth import RequiresLogin
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.clean import router as clean_router
from app.api.datasources import router as datasources_router
from app.api.health import router as health_router
from app.api.mcp import router as mcp_router
from app.api.model_config import router as model_config_router
from app.api.models import router as models_router
from app.api.sessions import router as sessions_router
from app.api.workflow import router as workflow_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(sessions_router, dependencies=[RequiresLogin()])
router.include_router(chat_router, dependencies=[RequiresLogin()])
router.include_router(models_router, dependencies=[RequiresLogin()])
router.include_router(model_config_router, dependencies=[RequiresLogin()])
router.include_router(datasources_router, dependencies=[RequiresLogin()])
router.include_router(clean_router, dependencies=[RequiresLogin()])
router.include_router(mcp_router, dependencies=[RequiresLogin()])
router.include_router(workflow_router, dependencies=[RequiresLogin()])
router.include_router(agent_source_router, dependencies=[RequiresLogin()])
