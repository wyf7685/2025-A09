from pathlib import Path
from typing import Any, Literal, TypedDict

import pandas as pd
from pydantic import BaseModel, Field


class CleaningState(TypedDict):
    """数据清洗状态"""

    file_path: Path
    df_data: dict[str, Any] | None  # 存储DataFrame的序列化数据而不是DataFrame本身
    user_requirements: str | None
    quality_issues: list[dict[str, Any]]
    field_mappings: dict[str, str]
    cleaning_suggestions: list[dict[str, Any]]
    cleaned_df_data: dict[str, Any] | None  # 存储清洗后DataFrame的序列化数据
    cleaning_summary: str
    error_message: str | None


class DataQualityReport(BaseModel):
    """数据质量报告模型"""

    overall_score: float = Field(description="总体质量分数", ge=0.0, le=100.0)
    total_rows: int = Field(description="总行数")
    total_columns: int = Field(description="总列数")
    missing_values_count: int = Field(description="缺失值总数")
    duplicate_rows_count: int = Field(description="重复行数")
    issues: list[dict[str, Any]] = Field(description="质量问题列表")
    recommendations: list[str] = Field(description="建议列表")


class ProcessFileResult(BaseModel):
    """处理文件的结果"""

    success: Literal[True] = True
    quality_report: DataQualityReport
    field_mappings: dict[str, str]  # 字段映射
    cleaning_suggestions: list[dict[str, Any]]  # 清洗建议
    summary: str  # 清洗总结信息


class ApplyCleaningSummary(BaseModel):
    original_shape: tuple[int, int]
    final_shape: tuple[int, int]
    rows_changed: int
    columns_changed: int
    successful_operations: int
    failed_operations: int
    applied_field_mappings: bool
    field_mappings_count: int


class ApplyCleaningResult(BaseModel):
    """应用清洗建议的结果"""

    success: Literal[True] = True
    cleaned_data: pd.DataFrame  # 清洗后的数据
    summary: ApplyCleaningSummary  # 清洗总结信息
    applied_operations: list[dict[str, Any]]  # 应用的清洗操作
    final_columns: list[str]  # 最终的列名列表
    field_mappings_applied: dict[str, str]  # 应用的字段映射
    generated_code: str


class ProcessCleanFileSummary(BaseModel):
    analysis: str
    cleaning: ApplyCleaningSummary


class ProcessCleanFileResult(BaseModel):
    """处理和清洗文件的结果"""

    success: Literal[True] = True
    analysis_result: ProcessFileResult
    cleaning_result: ApplyCleaningResult  # 清洗结果
    final_data: pd.DataFrame  # 清洗后的数据
    field_mappings: dict[str, str]  # 字段映射
    applied_operations: list[dict[str, Any]]  # 应用的清洗操作
    summary: ProcessCleanFileSummary  # 包含分析和清洗的总结信息
