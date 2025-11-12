import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.log import configure_logging
from app.utils import configure_matplotlib_fonts

configure_logging()
configure_matplotlib_fonts()

from app.api import router as api_router
from app.const import VERSION
from app.core.config import settings
from app.core.lifespan import lifespan

# 创建 FastAPI 应用
app = FastAPI(
    title="智能数据分析平台",
    description="基于 LangChain 的智能数据分析 API 服务",
    version=VERSION,
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
    uvicorn.run("app.__main__:app", host=settings.HOST, port=settings.PORT)
