# ruff: noqa: PD008

import re
from typing import Any, Literal, NotRequired, TypedDict, cast

import numpy as np
import pandas as pd

from app.core.agent.schemas import OperationFailed
from app.log import logger
from app.utils import escape_tag


class ConvertDtypesResult(TypedDict):
    """数据类型转换的结果"""

    success: Literal[True]
    message: str
    new_dataset_id: str
    converted_columns: list[str]  # 成功转换的列
    conversion_details: dict[str, dict[str, str]]  # 每列的转换详情，包含原类型和新类型
    failed_columns: list[str]  # 转换失败的列
    failed_reasons: dict[str, str]  # 转换失败的原因
    statistics: NotRequired[dict[str, Any]]  # 转换后的数据统计信息


def infer_and_convert_dtypes(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    to_numeric: bool = True,
    to_datetime: bool = True,
    to_category: bool = True,
    category_threshold: float = 0.05,
    datetime_format: str | None = None,
) -> tuple[pd.DataFrame, ConvertDtypesResult]:
    """
    自动推断并转换数据框中的列类型，修复常见的类型错误。

    Args:
        df (pd.DataFrame): 要处理的数据框
        columns (list[str], optional): 要转换的列名列表。如果为None，则尝试转换所有可能的列。
        to_numeric (bool): 是否尝试将列转换为数值型，默认为True
        to_datetime (bool): 是否尝试将列转换为日期时间类型，默认为True
        to_category (bool): 是否尝试将唯一值比例低的列转换为分类类型，默认为True
        category_threshold (float): 将列转换为分类类型的唯一值比例阈值，默认为0.05
                                  当唯一值数量/总行数 < category_threshold时，将转换为分类类型
        datetime_format (str, optional): 日期时间格式字符串，如'%Y-%m-%d'。如果为None，则尝试自动推断。

    Returns:
        tuple[pd.DataFrame, ConvertDtypesResult]: 修改后的数据框和转换结果信息
    """
    logger.opt(colors=True).info(
        f"<g>推断并转换数据类型</>: "
        f"数值={to_numeric}, 日期时间={to_datetime}, 分类={to_category}, "
        f"分类阈值={category_threshold}"
    )

    # 创建DataFrame的副本以避免修改原始数据
    df_copy = df.copy()

    # 如果未指定列，则处理所有列
    if columns is None:
        columns = cast("list[str]", df_copy.columns.tolist())

    # 初始化结果跟踪
    converted_columns = []
    conversion_details = {}
    failed_columns = []
    failed_reasons = {}

    # 数值型转换模式
    numeric_pattern = r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?$"

    for column in columns:
        if column not in df_copy.columns:
            failed_columns.append(column)
            failed_reasons[column] = "列不存在"
            continue

        original_dtype = str(df_copy[column].dtype)

        # 跳过已经是适当类型的列
        if pd.api.types.is_numeric_dtype(df_copy[column]) and not to_numeric:
            continue
        if pd.api.types.is_datetime64_dtype(df_copy[column]) and not to_datetime:
            continue
        if pd.api.types.is_categorical_dtype(df_copy[column]) and not to_category:
            continue

        try:
            # 处理可能的数值型列
            if to_numeric and df_copy[column].dtype == "object":
                # 检查列值是否符合数值模式
                numeric_values = df_copy[column].dropna().astype(str).str.match(numeric_pattern).mean() > 0.9

                if numeric_values:
                    # 将字符串转换为数值，错误时强制为NaN
                    df_copy[column] = pd.to_numeric(df_copy[column], errors="coerce")
                    converted_columns.append(column)
                    conversion_details[column] = {
                        "original_dtype": original_dtype,
                        "new_dtype": str(df_copy[column].dtype),
                    }

            # 处理可能的日期时间列
            elif to_datetime and df_copy[column].dtype == "object":
                # 检查是否看起来像日期
                datetime_pattern = r"\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}"
                possible_dates = df_copy[column].dropna().astype(str).str.match(datetime_pattern).mean() > 0.9

                if possible_dates:
                    try:
                        # 尝试转换为日期时间
                        df_copy[column] = pd.to_datetime(df_copy[column], format=datetime_format, errors="coerce")
                        converted_columns.append(column)
                        conversion_details[column] = {
                            "original_dtype": original_dtype,
                            "new_dtype": str(df_copy[column].dtype),
                        }
                    except Exception:
                        failed_columns.append(column)
                        failed_reasons[column] = "日期时间转换失败"

            # 处理可能的分类列
            elif to_category:
                # 检查唯一值比例，如果较低则可能是分类变量
                unique_ratio = df_copy[column].nunique() / len(df_copy)

                if unique_ratio < category_threshold and not pd.api.types.is_numeric_dtype(df_copy[column]):
                    df_copy[column] = df_copy[column].astype("category")
                    converted_columns.append(column)
                    conversion_details[column] = {
                        "original_dtype": original_dtype,
                        "new_dtype": str(df_copy[column].dtype),
                    }

        except Exception as e:
            failed_columns.append(column)
            failed_reasons[column] = str(e)

    # 准备统计信息
    memory_usage_before = cast("pd.Series", df[columns].memory_usage(deep=True)).sum() / 1048576  # MB
    memory_usage_after = cast("pd.Series", df_copy[columns].memory_usage(deep=True)).sum() / 1048576  # MB
    statistics = {
        "memory_usage_before": f"{memory_usage_before:.3f} MB",
        "memory_usage_after": f"{memory_usage_after:.3f} MB",
        "null_counts": {col: int(df_copy[col].isna().sum()) for col in columns},
    }

    # 生成结果
    result: ConvertDtypesResult = {
        "success": True,
        "message": f"完成数据类型转换。成功转换{len(converted_columns)}列，失败{len(failed_columns)}列。",
        "new_dataset_id": "{{UNSET}}",
        "converted_columns": converted_columns,
        "conversion_details": conversion_details,
        "failed_columns": failed_columns,
        "failed_reasons": failed_reasons,
        "statistics": statistics,
    }

    return df_copy, result


class CleanMisalignedDataResult(TypedDict):
    """修复数据错位的结果"""

    success: Literal[True]
    message: str
    new_dataset_id: str
    fixed_rows: int  # 修复的行数
    sample_before: dict[str, Any]  # 修复前的数据样本
    sample_after: dict[str, Any]  # 修复后的数据样本


def fix_misaligned_data(
    df: pd.DataFrame,
    suspected_columns: list[str] | None = None,
    alignment_pattern: str | None = None,
) -> tuple[pd.DataFrame, CleanMisalignedDataResult] | tuple[None, OperationFailed]:
    """
    修复数据错位问题，常见于导入CSV文件时分隔符识别错误。

    Args:
        df (pd.DataFrame): 要处理的数据框
        suspected_columns (list[str], optional): 疑似包含错位数据的列
        alignment_pattern (str, optional): 用于检测错位的正则表达式模式

    Returns:
        tuple[pd.DataFrame, CleanMisalignedDataResult | OperationFailed]: 修复后的数据框和操作结果
    """
    logger.opt(colors=True).info(f"<g>修复数据错位</>: 分析 <y>{escape_tag(str(suspected_columns or '所有列'))}</>")

    try:
        # 创建数据框副本
        df_copy = df.copy()

        # 如果未指定列，则检查所有对象类型列
        if suspected_columns is None:
            suspected_columns = cast("list[str]", df_copy.select_dtypes(include=["object"]).columns.tolist())
        # 验证指定的列是否存在
        elif missing_columns := [col for col in suspected_columns if col not in df_copy.columns]:
            return None, {
                "success": False,
                "message": f"错误: 以下列不存在: {', '.join(missing_columns)}",
                "error_type": "ColumnNotFound",
            }

        # 保存修复前的样本数据
        sample_before = df_copy.head(3).to_dict()

        # 计数修复的行
        fixed_rows = 0

        # 默认的分隔符模式（逗号、分号、制表符）
        if alignment_pattern is None:
            alignment_pattern = r"[,;\t]"

        # 对每列进行检查和修复
        for column in suspected_columns:
            if df_copy[column].dtype != "object":
                continue

            # 检测该列中包含分隔符的行
            has_separators = df_copy[column].astype(str).str.contains(alignment_pattern).sum()

            # 如果存在可能错位的数据
            if has_separators > 0:
                # 获取包含分隔符的行索引
                problem_indices = df_copy[df_copy[column].astype(str).str.contains(alignment_pattern)].index

                for idx in problem_indices:
                    value = str(df_copy.at[idx, column])
                    # 尝试将错位的数据拆分到各列
                    parts = re.split(alignment_pattern, value)

                    # 如果拆分后的部分与剩余列数量匹配
                    if len(parts) <= len(df_copy.columns) - list(df_copy.columns).index(column):
                        # 更新当前列的值为拆分后的第一部分
                        df_copy.at[idx, column] = parts[0]

                        # 将剩余部分分配到后续列
                        for i, part in enumerate(parts[1:], 1):
                            col_idx = list(df_copy.columns).index(column) + i
                            if col_idx < len(df_copy.columns):
                                next_col = df_copy.columns[col_idx]
                                df_copy.at[idx, next_col] = part

                        fixed_rows += 1

        # 保存修复后的样本
        sample_after = df_copy.head(3).to_dict()

        # 生成结果
        result: CleanMisalignedDataResult = {
            "success": True,
            "message": f"完成数据错位修复，共处理{fixed_rows}行数据。",
            "new_dataset_id": "{{UNSET}}",
            "fixed_rows": fixed_rows,
            "sample_before": sample_before,
            "sample_after": sample_after,
        }

        return df_copy, result

    except Exception as e:
        logger.opt(colors=True).exception("<r>修复数据错位时出错</r>")
        return None, {
            "success": False,
            "message": f"修复数据错位时出错: {e}",
            "error_type": type(e).__name__,
        }


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
