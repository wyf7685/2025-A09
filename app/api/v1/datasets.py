"""
数据集管理接口
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.v1.sessions import sessions
from app.api.v1.uploads import datasets
from app.log import logger

router = APIRouter()


@router.get("/datasets")
async def get_datasets(session_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """获取数据集列表"""
    try:
        dataset_list = []

        if session_id:
            # 获取指定会话的数据集
            if session_id not in sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            dataset_id = sessions[session_id].get("current_dataset")
            if dataset_id and dataset_id in datasets:
                df = datasets[dataset_id]
                dataset_list.append(
                    {
                        "id": dataset_id,
                        "name": dataset_id,
                        "rows": df.shape[0],
                        "columns": df.shape[1],
                        "session_id": session_id,
                    }
                )
        else:
            # 获取所有数据集
            for dataset_id, df in datasets.items():
                session_id = dataset_id.split("_")[0]
                dataset_list.append(
                    {
                        "id": dataset_id,
                        "name": dataset_id,
                        "rows": df.shape[0],
                        "columns": df.shape[1],
                        "session_id": session_id,
                    }
                )

        return {"datasets": dataset_list}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取数据集列表失败")
        raise HTTPException(status_code=500, detail=f"Failed to get datasets: {e}") from e


@router.get("/datasets/{dataset_id}/preview")
async def get_dataset_preview(dataset_id: str, limit: int = 10) -> dict[str, Any]:
    """获取数据集预览"""
    try:
        if dataset_id not in datasets:
            raise HTTPException(status_code=404, detail="Dataset not found")

        df = datasets[dataset_id]
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
