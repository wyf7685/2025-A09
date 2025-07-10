"""
智能数据分析平台 - FastAPI 后端
"""
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1 import router as api_v1_router
from app.core.dremio import dremio_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # on startup
    dremio_client.init()
    yield
    # on shutdown
    dremio_client.close()


# 创建 FastAPI 应用
app = FastAPI(
    title="DataWise",
    lifespan=lifespan,
)

# --- 添加CORS中间件 ---
origins = [
    "http://localhost",
    "http://localhost:5173",  # 假设这是你前端开发服务器的地址
    "http://localhost:5175",
    "http://127.0.0.1",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5175",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- ---------------- ---


# 注册API路由
app.include_router(api_v1_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=True,
    )
