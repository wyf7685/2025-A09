"""
文件上传接口
"""

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.const import UPLOAD_DIR
from app.log import logger

router = APIRouter()

# 数据集存储
datasets: dict[str, pd.DataFrame] = {}


def safe_convert_for_json(obj: object) -> object:
    """处理 JSON 序列化问题"""
    if isinstance(obj, int | np.integer):
        return int(obj)
    if isinstance(obj, np.floating | np.float64):
        return float(obj)
    if pd.isna(obj):  # type:ignore
        return None
    return obj


@router.post("/upload")
async def upload_file(file: UploadFile = File(), session_id: str | None = Form(None)) -> dict[str, Any]:
    """文件上传接口"""
    try:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # 导入会话管理函数
        from app.api.v1.sessions import get_or_create_session, sessions

        # 确保会话存在
        session_id = get_or_create_session(session_id)

        # 保存文件
        filename = f"{session_id}_{file.filename}"
        filepath = UPLOAD_DIR / filename

        content = await file.read()
        with filepath.open("wb") as f:
            f.write(content)

        # 读取数据
        try:
            if filepath.suffix.lower() == ".csv":
                df = pd.read_csv(filepath)
            elif filepath.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(filepath)
            else:
                raise HTTPException(status_code=400, detail="Unsupported file format")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to read file: {e}") from e

        # 存储数据集
        dataset_id = f"{session_id}_dataset"
        datasets[dataset_id] = df
        sessions[session_id]["current_dataset"] = dataset_id

        # 数据概览
        overview = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "preview": df.head().to_dict(orient="records"),
            "description": df.describe().to_dict(),
        }

        # 安全转换数据
        for record in overview["preview"]:
            for key, value in record.items():
                record[key] = safe_convert_for_json(value)

        return {"success": True, "session_id": session_id, "dataset_id": dataset_id, "overview": overview}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文件上传失败")
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}") from e
