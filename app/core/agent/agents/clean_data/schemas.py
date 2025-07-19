from pathlib import Path
from typing import Any, TypedDict

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
