"""
Dremio 数据源接口
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.api.v1.sessions import get_or_create_session, sessions
from app.api.v1.uploads import datasets
from app.core.dremio import DremioClient
from app.log import logger

router = APIRouter(prefix="/dremio")


@router.get("/sources")
async def get_dremio_sources() -> dict[str, list[dict[str, str]]]:
    """获取 Dremio 数据源列表"""
    try:
        # client = DremioClient()
        # 模拟数据源列表，实际可能需要查询 catalog
        sources = [
            {"name": "sample_data", "type": "csv", "description": "示例数据"},
            {"name": "postgres_db", "type": "database", "description": "PostgreSQL数据库"},
        ]
        return {"sources": sources}
    except Exception as e:
        logger.exception("获取 Dremio 数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to get Dremio sources: {e}") from e


@router.post("/load")
async def load_dremio_data(request_data: dict[str, Any] = Body()) -> dict[str, Any]:
    """从 Dremio 加载数据"""
    try:
        source_name = request_data.get("source_name")
        session_id = request_data.get("session_id")
        fetch_all = request_data.get("fetch_all", False)

        if not source_name:
            raise HTTPException(status_code=400, detail="Source name is required")

        session_id = get_or_create_session(session_id)

        client = DremioClient()
        df = client.read_source(source_name, fetch_all=fetch_all)

        # 存储数据集
        dataset_id = f"{session_id}_dremio_{source_name}"
        datasets[dataset_id] = df
        sessions[session_id]["current_dataset"] = dataset_id

        # 数据概览
        overview = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head().to_dict(orient="records"),
            "source": source_name,
        }

        return {"success": True, "session_id": session_id, "dataset_id": dataset_id, "overview": overview}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("从 Dremio 加载数据失败")
        raise HTTPException(status_code=500, detail=f"Failed to load data from Dremio: {e}") from e
