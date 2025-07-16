"""
缺失值处理工具
"""

from typing import Any, NotRequired, TypedDict

import numpy as np
import pandas as pd

from app.log import logger


class HandleMissingValuesResult(TypedDict):
    success: bool
    message: str
    affected_rows: int
    method: NotRequired[str]
    original_shape: NotRequired[tuple[int, int]]
    new_shape: NotRequired[tuple[int, int]]
    error: NotRequired[str]


def handle_missing_values(
    df: pd.DataFrame,
    column: str | None = None,
    method: str = "drop",
) -> HandleMissingValuesResult:
    """
    处理数据框中的缺失值

    Args:
        df: 数据框
        column: 目标列名，如果为 None 则处理所有列
        method: 处理方法 ('drop', 'fill_mean', 'fill_median',
        'fill_mode', 'fill_forward', 'fill_backward', 'interpolate')

    Returns:
        处理结果字典
    """
    try:
        return _handle_missing_values_column(df, column, method) if column else _handle_missing_values_all(df, method)
    except Exception as e:
        logger.error(f"处理缺失值失败: {e}")
        return {"success": False, "message": f"处理缺失值失败: {e}", "affected_rows": 0, "error": str(e)}


def _handle_missing_values_column(
    df: pd.DataFrame,
    column: str,
    method: str = "drop",
) -> HandleMissingValuesResult:
    original_shape = df.shape

    if column not in df.columns:
        return {"success": False, "message": f'列 "{column}" 不存在', "affected_rows": 0}

    missing_count = df[column].isna().sum()
    if missing_count == 0:
        return {"success": True, "message": f'列 "{column}" 没有缺失值', "affected_rows": 0}

    if method == "drop":
        df_cleaned = df.dropna(subset=[column])
        affected_rows = original_shape[0] - df_cleaned.shape[0]
    elif method == "fill_mean":
        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].fillna(df[column].mean())
            affected_rows = missing_count
        else:
            return {
                "success": False,
                "message": f'列 "{column}" 不是数值类型，无法使用均值填充',
                "affected_rows": 0,
            }
    elif method == "fill_median":
        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].fillna(df[column].median())
            affected_rows = missing_count
        else:
            return {
                "success": False,
                "message": f'列 "{column}" 不是数值类型，无法使用中位数填充',
                "affected_rows": 0,
            }
    elif method == "fill_mode":
        mode_value = df[column].mode()
        if len(mode_value) > 0:
            df[column] = df[column].fillna(mode_value[0])  # pyright: ignore[reportCallIssue, reportArgumentType]
            affected_rows = missing_count
        else:
            return {"success": False, "message": f'列 "{column}" 无法计算众数', "affected_rows": 0}
    elif method == "fill_forward":
        df[column] = df[column].ffill()
        affected_rows = missing_count
    elif method == "fill_backward":
        df[column] = df[column].bfill()
        affected_rows = missing_count
    elif method == "interpolate":
        if pd.api.types.is_numeric_dtype(df[column]):
            df[column] = df[column].interpolate()
            affected_rows = missing_count
        else:
            return {
                "success": False,
                "message": f'列 "{column}" 不是数值类型，无法使用插值填充',
                "affected_rows": 0,
            }
    else:
        return {"success": False, "message": f"不支持的处理方法: {method}", "affected_rows": 0}

    return {
        "success": True,
        "message": f"成功处理缺失值，影响 {affected_rows} 行数据",
        "affected_rows": affected_rows,
        "method": method,
        "original_shape": original_shape,
        "new_shape": df.shape,
    }


def _handle_missing_values_all(
    df: pd.DataFrame,
    method: str = "drop",
) -> HandleMissingValuesResult:
    original_shape = df.shape
    total_missing = df.isna().sum().sum()
    if total_missing == 0:
        return {"success": True, "message": "数据框中没有缺失值", "affected_rows": 0}

    if method == "drop":
        df_cleaned = df.dropna()
        affected_rows = original_shape[0] - df_cleaned.shape[0]
    elif method == "fill_mean":
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].mean())
        affected_rows = df[numeric_columns].isna().sum().sum()
    elif method == "fill_median":
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].fillna(df[numeric_columns].median())
        affected_rows = df[numeric_columns].isna().sum().sum()
    elif method == "fill_mode":
        for col in df.columns:
            mode_value = df[col].mode()
            if len(mode_value) > 0:
                df[col] = df[col].fillna(mode_value[0])  # pyright: ignore[reportCallIssue, reportArgumentType]
        affected_rows = total_missing
    elif method == "fill_forward":
        df = df.ffill()
        affected_rows = total_missing
    elif method == "fill_backward":
        df = df.bfill()
        affected_rows = total_missing
    elif method == "interpolate":
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].interpolate()
        affected_rows = df[numeric_columns].isna().sum().sum()
    else:
        return {"success": False, "message": f"不支持的处理方法: {method}", "affected_rows": 0}

    return {
        "success": True,
        "message": f"成功处理缺失值，影响 {affected_rows} 行数据",
        "affected_rows": affected_rows,
        "method": method,
        "original_shape": original_shape,
        "new_shape": df.shape,
    }


class MissingValuesSummary(TypedDict):
    total_missing: int
    total_cells: int
    missing_percentage: float
    columns_with_missing: int
    column_details: dict[str, dict[str, Any]]


def get_missing_values_summary(df: pd.DataFrame) -> MissingValuesSummary:
    """
    获取缺失值摘要信息

    Args:
        df: 数据框

    Returns:
        缺失值摘要
    """
    try:
        missing_summary = {}
        total_missing = 0

        for column in df.columns:
            missing_count = df[column].isna().sum()
            missing_percentage = (missing_count / len(df)) * 100

            missing_summary[column] = {
                "count": int(missing_count),
                "percentage": round(missing_percentage, 2),
                "data_type": str(df[column].dtype),
            }

            total_missing += missing_count

        return {
            "total_missing": int(total_missing),
            "total_cells": len(df) * len(df.columns),
            "missing_percentage": round((total_missing / (len(df) * len(df.columns))) * 100, 2),
            "columns_with_missing": sum(1 for info in missing_summary.values() if info["count"] > 0),
            "column_details": missing_summary,
        }

    except Exception as e:
        logger.exception("获取缺失值摘要失败")
        raise RuntimeError(f"获取缺失值摘要失败: {e!r}") from e
