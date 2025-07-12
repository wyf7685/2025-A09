"""
Dremio 数据源接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.v1.datasources import register_datasource
from app.core.datasource import create_dremio_source
from app.core.dremio import DremioClient, DremioSource
from app.log import logger

router = APIRouter(prefix="/dremio")


@router.get("/sources")
async def get_dremio_sources() -> list[DremioSource]:
    """获取 Dremio 数据源列表"""
    try:
        return DremioClient().list_sources()
    except Exception as e:
        logger.exception("获取 Dremio 数据源失败")
        raise HTTPException(status_code=500, detail=f"Failed to get Dremio sources: {e}") from e


class LoadDremioDataRequest(BaseModel):
    source: DremioSource
    fetch_all: bool = False


@router.post("/load")
async def load_dremio_data(request: LoadDremioDataRequest) -> dict[str, Any]:
    """从 Dremio 加载数据"""
    try:
        # 创建DataSource对象
        source = create_dremio_source(request.source)

        # 注册数据源
        source_id = register_datasource(source)

        # 获取预览数据
        preview = source.get_preview(5)

        # 数据概览
        overview = {
            "shape": [source.metadata.row_count or 0, source.metadata.column_count or 0],
            "columns": source.metadata.columns or [],
            "dtypes": source.metadata.dtypes or {},
            "preview": preview.to_dict(orient="records"),
            "source": request.source,
        }

        return {
            "success": True,
            "dataset_id": source_id,
            "overview": overview,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("从 Dremio 加载数据失败")
        raise HTTPException(status_code=500, detail=f"Failed to load data from Dremio: {e}") from e
