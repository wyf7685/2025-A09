"""
数据清洗相关 API
"""

import contextlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.const import UPLOAD_DIR
from app.core.agent.clean_data_agent import CleanDataAgent
from app.log import logger

# 创建路由实例
router = APIRouter(prefix="/clean", tags=["数据清洗"])

# 数据清洗 Agent 实例
clean_agent = CleanDataAgent()


@router.post("/check")
async def check_data_quality(
    file: UploadFile = File(...), filename: str | None = Form(None), description: str | None = Form(None)
) -> dict[str, Any]:
    """
    检测上传文件的数据质量和规范性

    Args:
        file: 上传的 CSV/Excel 文件
        filename: 用户指定的文件名（可选）
        description: 文件描述（可选）

    Returns:
        数据质量检测结果
    """
    try:
        # 验证文件类型
        if not file.filename:
            raise HTTPException(status_code=400, detail="请上传有效的文件")
        # 检查文件扩展名
        allowed_extensions = [".csv", ".xlsx", ".xls"]
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail="只支持 CSV 和 Excel 文件格式")

        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        temp_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

        try:
            # 保存上传的文件
            with temp_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 使用数据清洗 Agent 检测数据质量
            quality_result = clean_agent.check_data_quality(temp_path)

            # 获取详细的清洗建议
            suggestions = clean_agent.get_cleaning_suggestions(quality_result.get("issues", []))

            # 构建返回结果
            result = {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "user_filename": filename or file.filename,
                    "description": description or "",
                    "upload_time": datetime.now().isoformat(),
                    "file_size": quality_result.get("data_info", {}).get("file_size", 0),
                },
                "quality_check": quality_result,
                "cleaning_suggestions": suggestions,
                "status": "success",
            }

            # 记录日志
            logger.info(f"数据质量检测完成: {file.filename}, 质量分数: {quality_result.get('quality_score', 0)}")

            return result

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"数据质量检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据质量检测失败: {e}") from e


@router.post("/apply-cleaning")
async def apply_cleaning_action(file: UploadFile = File(...), actions: str = Form(...)) -> dict[str, Any]:
    """
    应用数据清洗动作

    Args:
        file: 上传的数据文件
        actions: JSON 格式的清洗动作列表

    Returns:
        清洗结果
    """
    try:
        # 解析清洗动作
        cleaning_actions = json.loads(actions)

        # 验证文件类型
        if not file.filename:
            raise HTTPException(status_code=400, detail="请上传有效的文件")

        # 检查文件扩展名
        allowed_extensions = [".csv", ".xlsx", ".xls"]
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail="只支持 CSV 和 Excel 文件格式")

        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        temp_path = UPLOAD_DIR / f"{file_id}{file_extension}"

        try:
            # 保存上传的文件
            with temp_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 应用清洗动作
            df = pd.read_csv(temp_path) if file_extension == ".csv" else pd.read_excel(temp_path)
            results = []
            for action in cleaning_actions:
                result = clean_agent.apply_cleaning_action(df, temp_path, action)
                results.append(result)
            df.to_csv(temp_path, index=False) if file_extension == ".csv" else df.to_excel(temp_path, index=False)

            # 记录日志
            logger.info(f"数据清洗动作应用完成: {file.filename}, 共 {len(results)} 个动作")

            return {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "processed_time": datetime.now().isoformat(),
                },
                "cleaning_results": results,
                "status": "success",
            }

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"数据清洗动作应用失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据清洗动作应用失败: {e}") from e


@router.post("/suggestions")
async def get_cleaning_suggestions(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    获取数据清洗建议

    Args:
        file: 上传的数据文件

    Returns:
        清洗建议列表
    """
    try:
        # 验证文件类型
        if not file.filename:
            raise HTTPException(status_code=400, detail="请上传有效的文件")

        # 检查文件扩展名
        allowed_extensions = [".csv", ".xlsx", ".xls"]
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail="只支持 CSV 和 Excel 文件格式")

        # 生成唯一文件名
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}{file_extension}"

        try:
            # 保存上传的文件
            with temp_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 检测数据质量
            quality_result = clean_agent.check_data_quality(temp_path)

            # 获取清洗建议
            suggestions = clean_agent.get_cleaning_suggestions(quality_result.get("issues", []))

            return {"suggestions": suggestions, "status": "success"}

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"获取清洗建议失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取清洗建议失败: {e}") from e


@router.post("/quality-report")
async def get_quality_report(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    获取详细的数据质量报告

    Args:
        file: 上传的数据文件

    Returns:
        详细的数据质量报告
    """
    try:
        # 验证文件类型
        if not file.filename:
            raise HTTPException(status_code=400, detail="请上传有效的文件")

        # 检查文件扩展名
        allowed_extensions = [".csv", ".xlsx", ".xls"]
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail="只支持 CSV 和 Excel 文件格式")

        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        original_filename = file.filename
        temp_filename = f"{file_id}_{original_filename}"
        temp_path = UPLOAD_DIR / temp_filename

        try:
            # 保存上传的文件
            with temp_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 检测数据质量
            quality_result = clean_agent.check_data_quality(temp_path)

            return {"quality_report": quality_result, "status": "success"}

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"获取质量报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取质量报告失败: {e}") from e
