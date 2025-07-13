"""
智能数据分析平台 - FastAPI 后端
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils import configure_matplotlib_fonts

configure_matplotlib_fonts()

from app.api.v1 import router as api_router

# 创建 FastAPI 应用
app = FastAPI(
    title="智能数据分析平台",
    description="基于 LangChain 的智能数据分析 API 服务",
    version="1.0.0",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vue 开发服务器默认端口
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=True,
    )
