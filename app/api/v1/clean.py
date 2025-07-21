"""
数据清洗相关 API - 集成基于LangChain和LangGraph的智能Agent
"""

import contextlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.const import UPLOAD_DIR
from app.core.agent import smart_clean_agent
from app.core.agent.schemas import is_failed, is_success
from app.log import logger
from app.services.datasource import datasource_service, tempfile_service

if TYPE_CHECKING:
    import pandas as pd

# 创建路由实例
router = APIRouter(prefix="/clean", tags=["数据清洗"])


@router.post("/analyze")
async def analyze_data_quality(
    file: UploadFile = File(...),
    user_requirements: str | None = Form(None),
    # TODO: implement model selection
    # model_name: str | None = Form(None),
) -> dict[str, Any]:
    """
    使用智能Agent分析数据质量并生成清洗建议
    如果有字段映射，立即应用并保存清洗后的数据文件

    Args:
        file: 上传的 CSV/Excel 文件
        user_requirements: 用户自定义清洗要求（可选）
        model_name: 指定使用的LLM模型（可选）

    Returns:
        包含质量报告、字段映射、清洗建议和总结的完整分析结果
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

            # 使用智能Agent处理文件
            result = await smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)
            resp_data = {}
            if is_success(result):
                # 如果有字段映射，准备应用到数据（但不立即上传）
                field_mappings = result.field_mappings
                cleaned_file_path = None

                if field_mappings:
                    logger.info(f"检测到字段映射，准备应用: {field_mappings}")

                    # 应用字段映射，生成映射后的数据文件
                    mapping_result = await smart_clean_agent.apply_user_selected_cleaning(
                        file_path=temp_path,
                        selected_suggestions=[],  # 只应用字段映射，不执行其他清洗
                        field_mappings=field_mappings,
                    )

                    if is_success(mapping_result):
                        # 保存应用字段映射后的数据文件，供后续使用
                        cleaned_df = mapping_result.cleaned_data
                        cleaned_file_path = UPLOAD_DIR / f"{file_id}_mapped{file_extension}"

                        if file_extension == ".csv":
                            cleaned_df.to_csv(cleaned_file_path, index=False)
                        elif file_extension in [".xlsx", ".xls"]:
                            cleaned_df.to_excel(cleaned_file_path, index=False)

                        logger.info(f"字段映射应用完成，数据已准备: {cleaned_file_path}")
                    elif is_failed(mapping_result):
                        logger.warning(f"字段映射应用失败: {mapping_result.message}")

                resp_data = {
                    "quality_report": result.quality_report,
                    "field_mappings": result.field_mappings,
                    "cleaning_suggestions": result.cleaning_suggestions,
                    "summary": result.summary,
                    "field_mappings_applied": bool(field_mappings),
                    "cleaned_file_id": tempfile_service.register(cleaned_file_path) if cleaned_file_path else None,
                }
                quality_score = result.quality_report.overall_score
                logger.info(
                    f"智能数据清洗分析完成: {file.filename}, "
                    f"质量分数: {quality_score:.2f}, "
                    f"字段映射: {len(field_mappings)} 个"
                )
            elif is_failed(result):
                resp_data = {"error": result.message}
                logger.error(f"智能数据清洗分析失败: {file.filename}, 错误: {result.message}")

            return {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "upload_time": datetime.now().isoformat(),
                    "file_size": temp_path.stat().st_size,
                    "file_extension": file_extension,
                },
                "success": result.success,
                **resp_data,
            }

        finally:
            # 清理原始临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"数据质量分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据质量分析失败: {e}") from e


class ExecuteCleaningRequest(BaseModel):
    """执行清洗请求模型"""

    selected_suggestions: list[dict[str, Any]]
    field_mappings: dict[str, str] = Field(default_factory=dict)
    user_requirements: str | None = None
    model_name: str | None = None


@router.post("/execute-cleaning")
async def execute_cleaning(
    file: UploadFile = File(...),
    cleaning_data: str = Form(...),  # JSON格式的清洗请求数据
) -> dict[str, Any]:
    """
    执行用户选择的数据清洗操作

    Args:
        file: 上传的数据文件
        cleaning_data: JSON格式的清洗请求数据，包含选择的建议、字段映射等

    Returns:
        清洗执行结果和清洗后的数据信息
    """
    try:
        # 解析清洗请求数据
        try:
            cleaning_request_data = ExecuteCleaningRequest.model_validate_json(cleaning_data)
            selected_suggestions = cleaning_request_data.selected_suggestions
            field_mappings = cleaning_request_data.field_mappings
            user_requirements = cleaning_request_data.user_requirements
            # model_name = cleaning_request_data.get("model_name")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"清洗请求数据格式错误: {e}") from e

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

            # 使用智能Agent执行清洗
            # 即使没有选择的建议，也会应用字段映射
            result = await smart_clean_agent.apply_user_selected_cleaning(
                temp_path,
                selected_suggestions,
                field_mappings,
                user_requirements,  # 添加用户要求参数
            )

            if is_failed(result):
                raise HTTPException(status_code=500, detail=result.message)
            assert is_success(result)

            # 构建返回结果
            response = {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "processing_time": datetime.now().isoformat(),
                    "file_size": temp_path.stat().st_size,
                    "file_extension": file_extension,
                },
                "success": True,
                "cleaning_summary": result.summary,
                "applied_operations": result.applied_operations,
                "final_columns": result.final_columns,
                "field_mappings_applied": result.field_mappings_applied,
                "cleaned_data_info": {
                    "shape": result.summary.final_shape,
                    "rows": result.summary.final_shape[0],
                    "columns": result.summary.final_shape[1],
                    "rows_changed": result.summary.rows_changed,
                    "columns_changed": result.summary.columns_changed,
                },
            }

            # 保存清洗后的数据到临时文件（可选，用于后续上传）
            cleaned_df = result.cleaned_data
            cleaned_file_path = UPLOAD_DIR / f"{file_id}_cleaned{file_extension}"

            # 调试日志：检查保存前的数据状态
            logger.info("=== 保存清洗后的数据 ===")
            logger.info(f"清洗后数据形状: {cleaned_df.shape}")
            logger.info(f"清洗后列名: {cleaned_df.columns.tolist()}")
            logger.info(f"保存文件路径: {cleaned_file_path}")

            if file_extension == ".csv":
                cleaned_df.to_csv(cleaned_file_path, index=False)
                logger.info("数据已保存为CSV文件")
            elif file_extension in [".xlsx", ".xls"]:
                cleaned_df.to_excel(cleaned_file_path, index=False)
                logger.info("数据已保存为Excel文件")

            response["cleaned_file_id"] = tempfile_service.register(cleaned_file_path)

            # 记录日志
            logger.info(
                f"数据清洗执行完成: {file.filename}, "
                f"应用了 {len(selected_suggestions)} 个清洗操作和 {len(field_mappings)} 个字段映射"
            )

            return response

        finally:
            # 清理原始临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"数据清洗执行失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据清洗执行失败: {e}") from e


@router.post("/analyze-and-clean")
async def analyze_and_clean(
    file: UploadFile = File(...),
    cleaning_data: str = Form(...),  # JSON格式的清洗请求数据
) -> dict[str, Any]:
    """
    完整的数据分析和清洗流程

    Args:
        file: 上传的数据文件
        cleaning_data: JSON格式的清洗请求数据

    Returns:
        包含分析结果和清洗结果的完整响应
    """
    try:
        # 解析清洗请求数据
        try:
            cleaning_request_data = json.loads(cleaning_data)
            selected_suggestions = cleaning_request_data.get("selected_suggestions", [])
            # field_mappings = cleaning_request_data.get("field_mappings", {})
            user_requirements = cleaning_request_data.get("user_requirements")
            # model_name = cleaning_request_data.get("model_name")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"清洗请求数据格式错误: {e}") from e

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

            # 使用智能Agent进行完整的分析和清洗流程
            result = await smart_clean_agent.process_and_clean_file(temp_path, user_requirements, selected_suggestions)

            if is_failed(result):
                raise HTTPException(status_code=500, detail=result.message)
            assert is_success(result)

            # 构建返回结果
            response = {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "processing_time": datetime.now().isoformat(),
                    "file_size": temp_path.stat().st_size,
                    "file_extension": file_extension,
                },
                "success": True,
                "analysis_result": result.analysis_result,
                "cleaning_result": result.cleaning_result,
                "field_mappings": result.field_mappings,
                "applied_operations": result.applied_operations,
                "summary": result.summary,
            }

            # 保存清洗后的数据到临时文件
            cleaned_df: pd.DataFrame = result.final_data
            cleaned_file_path = UPLOAD_DIR / f"{file_id}_cleaned{file_extension}"

            if file_extension == ".csv":
                cleaned_df.to_csv(cleaned_file_path, index=False)
            elif file_extension in [".xlsx", ".xls"]:
                cleaned_df.to_excel(cleaned_file_path, index=False)

            response["cleaned_file_id"] = tempfile_service.register(cleaned_file_path)
            response["cleaned_data_info"] = {
                "shape": cleaned_df.shape,
                "rows": len(cleaned_df),
                "columns": len(cleaned_df.columns),
                "column_names": cleaned_df.columns.tolist(),
            }

            logger.info(f"完整数据分析和清洗完成: {file.filename}")
            return response

        finally:
            # 清理原始临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"数据分析和清洗失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据分析和清洗失败: {e}") from e


@router.post("/suggestions")
async def get_cleaning_suggestions(
    file: UploadFile = File(...),
    user_requirements: str | None = Form(None),
) -> dict[str, Any]:
    """
    获取数据清洗建议（支持用户自定义要求）

    Args:
        file: 上传的数据文件
        user_requirements: 用户自定义清洗要求（可选）

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

            # 使用智能Agent获取建议
            result = await smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)

            if is_success(result):
                return {
                    "suggestions": result.cleaning_suggestions,
                    "field_mappings": result.field_mappings,
                    "summary": result.summary,
                }

            raise HTTPException(status_code=500, detail=result.message if is_failed(result) else "获取建议失败")

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取清洗建议失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取清洗建议失败: {e}") from e


@router.post("/quality-report")
async def get_quality_report(
    file: UploadFile = File(...), user_requirements: str | None = Form(None)
) -> dict[str, Any]:
    """
    获取详细的数据质量报告

    Args:
        file: 上传的数据文件
        user_requirements: 用户自定义要求（可选）

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

            # 使用智能Agent获取质量报告
            result = await smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)

            if is_success(result):
                return {
                    "quality_report": result.quality_report,
                    "field_mappings": result.field_mappings,
                    "summary": result.summary,
                }

            raise HTTPException(status_code=500, detail=result.message if is_failed(result) else "获取质量报告失败")

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取质量报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取质量报告失败: {e}") from e


class FieldMappingRequest(BaseModel):
    """字段映射请求模型"""

    source_id: str
    field_mappings: dict[str, str]


@router.post("/save-field-mappings")
async def save_field_mappings(request: FieldMappingRequest) -> dict[str, Any]:
    """
    保存字段映射到数据源

    Args:
        request: 包含数据源ID和字段映射的请求

    Returns:
        保存结果
    """
    try:
        # 获取数据源
        source = datasource_service.get_source(request.source_id)
        if not source:
            raise HTTPException(status_code=404, detail="数据源不存在")

        # 更新字段映射
        source.metadata.column_description = request.field_mappings

        # 这里可以添加持久化逻辑，比如保存到数据库
        # 目前只是更新内存中的映射

        logger.info(f"已保存数据源 {request.source_id} 的字段映射: {request.field_mappings}")

        return {
            "success": True,
            "message": "字段映射保存成功",
            "source_id": request.source_id,
            "field_mappings": request.field_mappings,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}") from e
