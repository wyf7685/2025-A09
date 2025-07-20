"""
数据清洗相关 API - 集成基于LangChain和LangGraph的智能Agent
"""

import contextlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.const import UPLOAD_DIR
from app.core.agent.agents.clean_data import smart_clean_agent
from app.log import logger
from app.services.datasource import datasource_service

# 创建路由实例
router = APIRouter(prefix="/clean", tags=["数据清洗"])


class CleaningRequest(BaseModel):
    """清洗请求模型"""

    file_id: str
    user_requirements: str | None = None
    model_name: str | None = None


class CleaningActionRequest(BaseModel):
    """清洗动作请求模型"""

    file_id: str
    actions: list[dict[str, Any]]


class FieldMappingRequest(BaseModel):
    """字段映射请求模型"""

    source_id: str
    field_mappings: dict[str, str]


class ExecuteCleaningRequest(BaseModel):
    """执行清洗请求模型"""

    selected_suggestions: list[dict[str, Any]]
    field_mappings: dict[str, str] | None = None
    user_requirements: str | None = None
    model_name: str | None = None


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

        # 初始化变量
        field_mappings = {}
        cleaned_file_path = None

        try:
            # 保存上传的文件
            with temp_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 使用智能Agent处理文件
            result = smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)

            if result["success"]:
                # 如果有字段映射，准备应用到数据（但不立即上传）
                field_mappings = result.get("field_mappings", {})
                cleaned_file_path = None

                if field_mappings:
                    logger.info(f"检测到字段映射，准备应用: {field_mappings}")

                    # 应用字段映射，生成映射后的数据文件
                    mapping_result = smart_clean_agent.apply_user_selected_cleaning(
                        file_path=temp_path,
                        selected_suggestions=[],  # 只应用字段映射，不执行其他清洗
                        field_mappings=field_mappings,
                    )

                    if mapping_result["success"]:
                        # 保存应用字段映射后的数据文件，供后续使用
                        cleaned_df = mapping_result["cleaned_data"]
                        cleaned_file_path = UPLOAD_DIR / f"{file_id}_mapped{file_extension}"

                        if file_extension == ".csv":
                            cleaned_df.to_csv(cleaned_file_path, index=False)
                        elif file_extension in [".xlsx", ".xls"]:
                            cleaned_df.to_excel(cleaned_file_path, index=False)

                        logger.info(f"字段映射应用完成，数据已准备: {cleaned_file_path}")
                    else:
                        logger.warning(f"字段映射应用失败: {mapping_result.get('error')}")

            # 构建返回结果
            response = {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "upload_time": datetime.now().isoformat(),
                    "file_size": temp_path.stat().st_size,
                    "file_extension": file_extension,
                },
                "success": result["success"],
                "quality_report": result.get("quality_report"),
                "field_mappings": result.get("field_mappings", {}),
                "cleaning_suggestions": result.get("cleaning_suggestions", []),
                "summary": result.get("summary", ""),
                "error": result.get("error") if not result["success"] else None,
                "field_mappings_applied": bool(field_mappings),
                "cleaned_file_path": str(cleaned_file_path) if cleaned_file_path else None,
            }

            # 记录日志
            if result["success"]:
                quality_score = result.get("quality_report", {}).get("overall_score", 0)
                logger.info(
                    f"智能数据清洗分析完成: {file.filename}, "
                    f"质量分数: {quality_score:.2f}, "
                    f"字段映射: {len(field_mappings)} 个"
                )
            else:
                logger.error(f"智能数据清洗分析失败: {file.filename}, 错误: {result.get('error')}")

            return response

        finally:
            # 清理原始临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"数据质量分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据质量分析失败: {e}") from e


@router.post("/check")
async def check_data_quality(
    file: UploadFile = File(...), filename: str | None = Form(None), description: str | None = Form(None)
) -> dict[str, Any]:
    """
    检测上传文件的数据质量和规范性（保持向后兼容）

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

            # 使用智能Agent处理文件
            result = smart_clean_agent.process_file(temp_path)

            # 转换为向后兼容的格式
            if result["success"]:
                quality_report = result.get("quality_report", {})
                cleaning_suggestions = result.get("cleaning_suggestions", [])

                # 转换清洗建议格式
                legacy_suggestions = [
                    {
                        "type": suggestion.get("issue_type", "unknown"),
                        "column": suggestion.get("column", ""),
                        "description": suggestion.get("description", ""),
                        "severity": suggestion.get("priority", "medium"),
                        "options": [
                            {
                                "method": suggestion.get("parameters", {}).get("method", "default"),
                                "description": suggestion.get("suggested_action", ""),
                            }
                        ],
                    }
                    for suggestion in cleaning_suggestions
                ]

                # 构建向后兼容的结果
                return {
                    "file_info": {
                        "file_id": file_id,
                        "original_filename": file.filename,
                        "user_filename": filename or file.filename,
                        "description": description or "",
                        "upload_time": datetime.now().isoformat(),
                        "file_size": quality_report.get("file_size", 0),
                    },
                    "quality_check": {
                        "is_valid": quality_report.get("overall_score", 0) >= 80,
                        "quality_score": quality_report.get("overall_score", 0),
                        "issues": quality_report.get("issues", []),
                        "data_info": {
                            "rows": quality_report.get("total_rows", 0),
                            "columns": quality_report.get("total_columns", 0),
                            "missing_values_total": quality_report.get("missing_values_count", 0),
                            "file_size": temp_path.stat().st_size,
                            "file_format": file_extension,
                        },
                    },
                    "cleaning_suggestions": legacy_suggestions,
                    "status": "success",
                }

            raise HTTPException(status_code=500, detail=result.get("error", "处理失败"))
        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()
    except HTTPException:
        raise
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
        try:
            cleaning_actions = json.loads(actions)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"清洗动作格式错误: {e}") from e

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

            # 使用智能Agent应用清洗动作
            result = smart_clean_agent.apply_cleaning_actions(temp_path, cleaning_actions)

            # 构建返回结果
            response = {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "processed_time": datetime.now().isoformat(),
                },
                "success": result["success"],
                "cleaning_results": result.get("results", []),
                "cleaned_rows": result.get("cleaned_rows", 0),
                "cleaned_columns": result.get("cleaned_columns", 0),
                "error": result.get("error") if not result["success"] else None,
            }

            # 记录日志
            if result["success"]:
                logger.info(f"数据清洗动作应用完成: {file.filename}, 共 {len(cleaning_actions)} 个动作")
            else:
                logger.error(f"数据清洗动作应用失败: {file.filename}, 错误: {result.get('error')}")

            return response

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"数据清洗动作应用失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据清洗动作应用失败: {e}") from e


@router.post("/suggestions")
async def get_cleaning_suggestions(
    file: UploadFile = File(...), user_requirements: str | None = Form(None)
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
            result = smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)

            if result["success"]:
                return {
                    "suggestions": result.get("cleaning_suggestions", []),
                    "field_mappings": result.get("field_mappings", {}),
                    "summary": result.get("summary", ""),
                    "status": "success",
                }

            raise HTTPException(status_code=500, detail=result.get("error", "获取建议失败"))

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

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
            result = smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)

            if result["success"]:
                return {
                    "quality_report": result.get("quality_report"),
                    "field_mappings": result.get("field_mappings", {}),
                    "summary": result.get("summary", ""),
                    "status": "success",
                }

            raise HTTPException(status_code=500, detail=result.get("error", "获取质量报告失败"))

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"获取质量报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取质量报告失败: {e}") from e


@router.post("/field-mapping")
async def get_field_mapping(
    file: UploadFile = File(...),
    user_requirements: str | None = Form(None),
    # TODO: implement model selection
    # model_name: str | None = Form(None),
) -> dict[str, Any]:
    """
    使用LLM猜测数据源字段名并返回映射关系

    Args:
        file: 上传的数据文件
        user_requirements: 用户自定义要求（可选）
        model_name: 指定使用的LLM模型（可选）

    Returns:
        字段映射关系
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

            # 使用智能Agent获取字段映射
            result = smart_clean_agent.process_file(file_path=temp_path, user_requirements=user_requirements)

            if result["success"]:
                return {
                    "field_mappings": result.get("field_mappings", {}),
                    "summary": result.get("summary", ""),
                    "status": "success",
                }

            raise HTTPException(status_code=500, detail=result.get("error", "获取字段映射失败"))

        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"获取字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取字段映射失败: {e}") from e


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
            cleaning_request_data = json.loads(cleaning_data)
            selected_suggestions = cleaning_request_data.get("selected_suggestions", [])
            field_mappings = cleaning_request_data.get("field_mappings", {})
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

            # 使用智能Agent执行清洗
            # 即使没有选择的建议，也会应用字段映射
            result = smart_clean_agent.apply_user_selected_cleaning(
                temp_path, 
                selected_suggestions, 
                field_mappings,
                user_requirements  # 添加用户要求参数
            )

            if result["success"]:
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
                    "cleaning_summary": result["summary"],
                    "applied_operations": result["applied_operations"],
                    "final_columns": result["final_columns"],
                    "field_mappings_applied": result["field_mappings_applied"],
                    "cleaned_data_info": {
                        "shape": result["summary"]["final_shape"],
                        "rows": result["summary"]["final_shape"][0],
                        "columns": result["summary"]["final_shape"][1],
                        "rows_changed": result["summary"]["rows_changed"],
                        "columns_changed": result["summary"]["columns_changed"],
                    },
                }

                # 保存清洗后的数据到临时文件（可选，用于后续上传）
                cleaned_df = result["cleaned_data"]
                cleaned_file_path = UPLOAD_DIR / f"{file_id}_cleaned{file_extension}"

                # 调试日志：检查保存前的数据状态
                logger.info(f"=== 保存清洗后的数据 ===")
                logger.info(f"清洗后数据形状: {cleaned_df.shape}")
                logger.info(f"清洗后列名: {cleaned_df.columns.tolist()}")
                logger.info(f"保存文件路径: {cleaned_file_path}")

                if file_extension == ".csv":
                    cleaned_df.to_csv(cleaned_file_path, index=False)
                    logger.info(f"数据已保存为CSV文件")
                elif file_extension in [".xlsx", ".xls"]:
                    cleaned_df.to_excel(cleaned_file_path, index=False)
                    logger.info(f"数据已保存为Excel文件")

                response["cleaned_file_path"] = str(cleaned_file_path)

                # 记录日志
                operations_count = len(selected_suggestions)
                mappings_count = len(field_mappings)
                logger.info(f"数据清洗执行完成: {file.filename}, 应用了 {operations_count} 个清洗操作和 {mappings_count} 个字段映射")

                return response

            else:
                raise HTTPException(status_code=500, detail=result.get("error", "清洗执行失败"))

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
            result = smart_clean_agent.process_and_clean_file(temp_path, user_requirements, selected_suggestions)

            if result["success"]:
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
                    "analysis_result": result["analysis_result"],
                    "cleaning_result": result["cleaning_result"],
                    "field_mappings": result["field_mappings"],
                    "applied_operations": result["applied_operations"],
                    "summary": result["summary"],
                }

                # 保存清洗后的数据到临时文件
                if result.get("final_data") is not None:
                    cleaned_df = result["final_data"]
                    cleaned_file_path = UPLOAD_DIR / f"{file_id}_cleaned{file_extension}"

                    if file_extension == ".csv":
                        cleaned_df.to_csv(cleaned_file_path, index=False)
                    elif file_extension in [".xlsx", ".xls"]:
                        cleaned_df.to_excel(cleaned_file_path, index=False)

                    response["cleaned_file_path"] = str(cleaned_file_path)
                    response["cleaned_data_info"] = {
                        "shape": cleaned_df.shape,
                        "rows": len(cleaned_df),
                        "columns": len(cleaned_df.columns),
                        "column_names": cleaned_df.columns.tolist(),
                    }

                logger.info(f"完整数据分析和清洗完成: {file.filename}")
                return response

            raise HTTPException(status_code=500, detail=result.get("error", "分析和清洗失败"))

        finally:
            # 清理原始临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()

    except Exception as e:
        logger.error(f"数据分析和清洗失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据分析和清洗失败: {e}") from e


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    健康检查接口

    Returns:
        服务健康状态
    """
    try:
        # 检查智能Agent是否正常
        agent_status = "healthy" if smart_clean_agent else "unhealthy"

        return {
            "status": "healthy",
            "service": "data_cleaning_api",
            "agent_status": agent_status,
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "service": "data_cleaning_api",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


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


@router.get("/field-mappings/{source_id}")
async def get_field_mappings(source_id: str) -> dict[str, Any]:
    """
    获取数据源的字段映射

    Args:
        source_id: 数据源ID

    Returns:
        字段映射信息
    """
    try:
        # 获取数据源
        source = datasource_service.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="数据源不存在")

        return {
            "success": True,
            "source_id": source_id,
            "field_mappings": source.metadata.column_description or {},
            "source_name": source.metadata.name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {e}") from e
