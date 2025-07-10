"""
数据集管理接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.v1.sessions import sessions
from app.core.dremio import dremio_client
from app.log import logger

router = APIRouter()


@router.get("/datasets")
async def get_datasets() -> list[dict[str, Any]]:
    """获取所有可用的数据集"""
    try:
        # 统一从Dremio获取所有数据源信息
        sources = dremio_client.query_source_tables()

        dataset_list = [
            {
                "id": ".".join(source),
                "name": source[-1],
                "type": "TABLE",
                "description": f"来自Dremio的数据源: {'.'.join(source)}",
            }
            for source in sources
        ]
        return dataset_list

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取数据集列表失败")
        raise HTTPException(status_code=500, detail=f"Failed to get datasets: {e}") from e


@router.get("/datasets/{dataset_id}/preview")
async def get_dataset_preview(dataset_id: str, limit: int = 10) -> dict[str, Any]:
    """获取数据集预览"""
    try:
        if not dataset_id:
            raise HTTPException(status_code=404, detail="Dataset not found")

        df = dremio_client.read_source(dataset_id.split("."))
        preview_df = df.head(limit)

        return {
            "columns": df.columns.tolist(),
            "data": preview_df.to_dict(orient="records"),
            "total_rows": df.shape[0],
            "preview_rows": preview_df.shape[0],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取数据集预览失败")
        raise HTTPException(status_code=500, detail=f"Failed to get dataset preview: {e}") from e
