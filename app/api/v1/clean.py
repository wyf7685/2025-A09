"""
数据清洗相关 API - 集成基于LangChain和LangGraph的智能Agent
"""

import contextlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.const import UPLOAD_DIR
from app.core.agent.clean_data_agent import smart_clean_agent
from app.services.datasource import datasource_service
from app.log import logger

# 创建路由实例
router = APIRouter(prefix="/clean", tags=["数据清洗"])


class CleaningRequest(BaseModel):
    """清洗请求模型"""
    file_id: str
    user_requirements: Optional[str] = None
    model_name: Optional[str] = None


class CleaningActionRequest(BaseModel):
    """清洗动作请求模型"""
    file_id: str
    actions: List[Dict[str, Any]]


class FieldMappingRequest(BaseModel):
    """字段映射请求模型"""
    source_id: str
    field_mappings: Dict[str, str]


@router.post("/analyze")
async def analyze_data_quality(
    file: UploadFile = File(...), 
    user_requirements: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """
    使用智能Agent分析数据质量并生成清洗建议
    
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
            result = smart_clean_agent.process_file(
                file_path=str(temp_path),
                user_requirements=user_requirements
            )
            
            # 构建返回结果
            response = {
                "file_info": {
                    "file_id": file_id,
                    "original_filename": file.filename,
                    "upload_time": datetime.now().isoformat(),
                    "file_size": temp_path.stat().st_size,
                    "file_extension": file_extension
                },
                "success": result["success"],
                "quality_report": result.get("quality_report"),
                "field_mappings": result.get("field_mappings", {}),
                "cleaning_suggestions": result.get("cleaning_suggestions", []),
                "summary": result.get("summary", ""),
                "error": result.get("error") if not result["success"] else None
            }
            
            # 记录日志
            if result["success"]:
                quality_score = result.get("quality_report", {}).get("overall_score", 0)
                logger.info(f"智能数据清洗分析完成: {file.filename}, 质量分数: {quality_score:.2f}")
            else:
                logger.error(f"智能数据清洗分析失败: {file.filename}, 错误: {result.get('error')}")
            
            return response
            
        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()
    
    except Exception as e:
        logger.error(f"数据质量分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据质量分析失败: {e}") from e


@router.post("/check")
async def check_data_quality(
    file: UploadFile = File(...), 
    filename: str | None = Form(None), 
    description: str | None = Form(None)
) -> Dict[str, Any]:
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
            result = smart_clean_agent.process_file(str(temp_path))
            
            # 转换为向后兼容的格式
            if result["success"]:
                quality_report = result.get("quality_report", {})
                cleaning_suggestions = result.get("cleaning_suggestions", [])
                
                # 转换清洗建议格式
                legacy_suggestions = []
                for suggestion in cleaning_suggestions:
                    legacy_suggestions.append({
                        "type": suggestion.get("issue_type", "unknown"),
                        "column": suggestion.get("column", ""),
                        "description": suggestion.get("description", ""),
                        "severity": suggestion.get("priority", "medium"),
                        "options": [{
                            "method": suggestion.get("parameters", {}).get("method", "default"),
                            "description": suggestion.get("suggested_action", "")
                        }]
                    })
                
                # 构建向后兼容的结果
                legacy_result = {
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
                        }
                    },
                    "cleaning_suggestions": legacy_suggestions,
                    "status": "success",
                }
                
                return legacy_result
            else:
                raise HTTPException(status_code=500, detail=result.get("error", "处理失败"))
                
        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()
    
    except Exception as e:
        logger.error(f"数据质量检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据质量检测失败: {e}") from e


@router.post("/apply-cleaning")
async def apply_cleaning_action(
    file: UploadFile = File(...), 
    actions: str = Form(...)
) -> Dict[str, Any]:
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
            raise HTTPException(status_code=400, detail=f"清洗动作格式错误: {e}")
        
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
            result = smart_clean_agent.apply_cleaning_actions(str(temp_path), cleaning_actions)
            
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
                "error": result.get("error") if not result["success"] else None
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
    file: UploadFile = File(...),
    user_requirements: Optional[str] = Form(None)
) -> Dict[str, Any]:
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
            result = smart_clean_agent.process_file(
                file_path=str(temp_path),
                user_requirements=user_requirements
            )
            
            if result["success"]:
                return {
                    "suggestions": result.get("cleaning_suggestions", []),
                    "field_mappings": result.get("field_mappings", {}),
                    "summary": result.get("summary", ""),
                    "status": "success"
                }
            else:
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
    file: UploadFile = File(...),
    user_requirements: Optional[str] = Form(None)
) -> Dict[str, Any]:
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
            result = smart_clean_agent.process_file(
                file_path=str(temp_path),
                user_requirements=user_requirements
            )
            
            if result["success"]:
                return {
                    "quality_report": result.get("quality_report"),
                    "field_mappings": result.get("field_mappings", {}),
                    "summary": result.get("summary", ""),
                    "status": "success"
                }
            else:
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
    user_requirements: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None)
) -> Dict[str, Any]:
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
            result = smart_clean_agent.process_file(
                file_path=str(temp_path),
                user_requirements=user_requirements
            )
            
            if result["success"]:
                return {
                    "field_mappings": result.get("field_mappings", {}),
                    "summary": result.get("summary", ""),
                    "status": "success"
                }
            else:
                raise HTTPException(status_code=500, detail=result.get("error", "获取字段映射失败"))
                
        finally:
            # 清理临时文件
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()
    
    except Exception as e:
        logger.error(f"获取字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取字段映射失败: {e}") from e


@router.get("/health")
async def health_check() -> Dict[str, Any]:
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
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "service": "data_cleaning_api",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.post("/save-field-mappings")
async def save_field_mappings(request: FieldMappingRequest) -> Dict[str, Any]:
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
            "field_mappings": request.field_mappings
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/field-mappings/{source_id}")
async def get_field_mappings(source_id: str) -> Dict[str, Any]:
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
            "source_name": source.metadata.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取字段映射失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")
