import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.log import configure_logging
from app.utils import configure_matplotlib_fonts

configure_matplotlib_fonts()
configure_logging()

from app import api
from app.core.lifespan import lifespan

# 创建 FastAPI 应用
app = FastAPI(
    title="智能数据分析平台",
    description="基于 LangChain 的智能数据分析 API 服务",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vue 开发服务器默认端口
        "http://localhost:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(api.router)


if __name__ == "__main__":
    uvicorn.run("app.__main__:app", host="0.0.0.0", port=8081)  # noqa: S104
