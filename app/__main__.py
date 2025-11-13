from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.log import configure_logging

configure_logging()

from app.api import router as api_router
from app.const import VERSION
from app.core.config import settings
from app.core.lifespan import lifespan

# 创建 FastAPI 应用
app = FastAPI(
    title="DataForge",
    description="Dataforge - 智能数据锻造平台",
    version=VERSION,
    openapi_url="/openapi.json" if not settings.APP_IS_PROD else None,
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# 注册API路由
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.__main__:app", host=settings.HOST, port=settings.PORT)
