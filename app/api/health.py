"""
健康检查接口
"""

from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
