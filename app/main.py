"""
智能数据分析平台 - FastAPI 后端
"""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.v1 import router as api_router

# 加载环境变量
load_dotenv()

# 创建必要的目录
Path("uploads").mkdir(exist_ok=True)
Path("states").mkdir(exist_ok=True)
Path("exports").mkdir(exist_ok=True)

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
        "http://localhost:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(api_router)


# 创建一个支持SPA的静态文件处理类
class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:  # noqa: ANN001
        try:
            return await super().get_response(path, scope)
        except Exception:
            return await super().get_response("index.html", scope)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=True,
    )
