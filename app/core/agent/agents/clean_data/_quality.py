import re
from typing import Any

import pandas as pd

from app.log import logger

from .schemas import CleaningState, load_source

PATTERN_EMAIL = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PATTERN_PHONE = re.compile(r"^[\+]?[1-9]?\d{1,14}$")
PATTERN_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATTERN_TIME = re.compile(r"^\d{2}:\d{2}:\d{2}$")
PATTERN_URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
PATTERN_NUMERIC = re.compile(r"^-?\d+\.?\d*$")


def calculate_quality_score(issues: list[dict[str, Any]]) -> float:
    """计算数据质量分数"""
    if not issues:
        return 100.0

    penalty = 0
    for issue in issues:
        severity = issue.get("severity", "low")
        if severity == "high":
            penalty += 20
        elif severity == "medium":
            penalty += 10
        else:
            penalty += 5

    return max(0, 100 - penalty)


def _check_column_names(df: pd.DataFrame) -> list[dict[str, Any]]:
    """检查列名规范性"""
    issues = []

    for col in df.columns:
        col_issues = []

        # 检查空格
        if " " in col:
            col_issues.append("包含空格")

        # 检查特殊字符
        if re.search(r"[^\w\u4e00-\u9fff]", col):
            col_issues.append("包含特殊字符")

        # 检查长度
        if len(col) > 50:
            col_issues.append("名称过长")

        if col_issues:
            issues.append(
                {
                    "type": "column_name",
                    "column": col,
                    "severity": "low",
                    "description": f"列名 '{col}' 存在问题: {', '.join(col_issues)}",
                    "issues": col_issues,
                }
            )

    return issues


def _check_missing_values(df: pd.DataFrame) -> list[dict[str, Any]]:
    """检查缺失值"""
    issues = []

    for col in df.columns:
        missing_count = df[col].isna().sum()
        if missing_count > 0:
            missing_rate = missing_count / len(df)
            severity = "high" if missing_rate > 0.5 else "medium" if missing_rate > 0.1 else "low"

            issues.append(
                {
                    "type": "missing_values",
                    "column": col,
                    "severity": severity,
                    "description": f"列 '{col}' 有 {missing_count} 个缺失值 ({missing_rate:.2%})",
                    "count": int(missing_count),
                    "rate": float(missing_rate),
                }
            )

    return issues


def _check_data_types(df: pd.DataFrame) -> list[dict[str, Any]]:
    """检查数据类型一致性"""
    issues = []

    for col in df.columns:
        if df[col].dtype == "object":
            # 检查是否应该是数值型
            non_null_values = df[col].dropna()
            if len(non_null_values) > 0:
                numeric_count = sum(1 for val in non_null_values if PATTERN_NUMERIC.match(str(val)))
                if numeric_count / len(non_null_values) > 0.8:
                    issues.append(
                        {
                            "type": "data_type",
                            "column": col,
                            "severity": "medium",
                            "description": f"列 '{col}' 可能应该是数值型",
                            "suggested_type": "numeric",
                        }
                    )

    return issues


def _check_outliers(df: pd.DataFrame) -> list[dict[str, Any]]:
    """检查异常值"""
    issues = []

    numeric_columns = df.select_dtypes(include=["number"]).columns

    for col in numeric_columns:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
        if len(outliers) > 0:
            issues.append(
                {
                    "type": "outliers",
                    "column": col,
                    "severity": "low",
                    "description": f"列 '{col}' 有 {len(outliers)} 个异常值",
                    "count": len(outliers),
                    "bounds": {"lower": float(lower_bound), "upper": float(upper_bound)},
                }
            )

    return issues


def analyze_quality(state: CleaningState) -> CleaningState:
    """分析数据质量"""
    try:
        df = load_source(state, "source_id").get_full()

        logger.info("开始分析数据质量")

        # 分析各种质量问题
        issues = []

        # 1. 检查列名问题
        issues.extend(_check_column_names(df))

        # 2. 检查缺失值
        issues.extend(_check_missing_values(df))

        # 3. 检查重复行
        if (duplicate_rows_count := int(df.duplicated().sum())) > 0:
            issues.append(
                {
                    "type": "duplicate_rows",
                    "severity": "medium",
                    "description": f"发现 {duplicate_rows_count} 行重复数据",
                    "count": duplicate_rows_count,
                }
            )

        # 4. 检查数据类型
        issues.extend(_check_data_types(df))

        # 5. 检查异常值
        issues.extend(_check_outliers(df))

        # 计算质量分数
        quality_score = calculate_quality_score(issues)

        state["quality_issues"] = issues
        logger.info(f"数据质量分析完成，质量分数: {quality_score:.2f}")
        return state

    except Exception as e:
        logger.error(f"数据质量分析失败: {e}")
        state["error_message"] = str(e)
        return state
