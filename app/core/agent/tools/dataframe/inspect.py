from typing import Any, TypedDict, cast

import pandas as pd

from app.log import logger


class InspectDataframeOptions(TypedDict, total=False):
    show_columns: bool  # 是否显示完整列列表
    show_dtypes: bool  # 是否显示每列的数据类型
    show_null_counts: bool  # 是否显示每列的空值数量
    show_summary_stats: bool  # 是否显示数值列的统计摘要
    show_unique_counts: bool  # 是否显示分类列唯一值数量
    n_rows_preview: int  # 预览的行数
    include_columns: list[str]  # 仅包含指定列
    exclude_columns: list[str]  # 排除指定列


class InspectDataframeResult(TypedDict, total=False):
    shape: tuple[int, int]  # 数据框的形状(行数、列数)
    columns: list[str]  # 所有列的名称
    dtypes: dict[str, str]  # 每列的数据类型
    preview: str  # 数据预览(前n行)
    null_counts: dict[str, int]  # 每列的空值数量
    memory_usage: str  # 内存使用量
    summary_stats: dict[str, Any]  # 数值列的统计摘要
    unique_counts: dict[str, int]  # 分类列唯一值数量


def inspect_dataframe(
    df: pd.DataFrame,
    options: InspectDataframeOptions | None = None,
) -> InspectDataframeResult:
    """
    全面查看当前数据框的状态，包括数据结构、预览和统计摘要。
    这个工具特别适合在进行数据修改后使用，例如使用create_column_tool创建新列、
    或进行其他数据转换操作后，检查数据的最新状态。

    Args:
        options (dict, optional): 查看选项，可包含：
            - show_columns (bool): 是否显示完整列列表，默认True
            - show_dtypes (bool): 是否显示每列的数据类型，默认True
            - show_null_counts (bool): 是否显示每列的空值数量，默认True
            - show_summary_stats (bool): 是否显示数值列的统计摘要，默认True
            - show_unique_counts (bool): 是否显示分类列唯一值数量，默认True
            - n_rows (int): 预览的行数，默认5
            - include_columns (list): 仅包含指定列
            - exclude_columns (list): 排除指定列

    Returns:
        dict: 包含数据框详细信息的结果
    """
    logger.info(f"检查数据当前状态: {options}")

    options = options or {}
    n_rows_preview = options.get("n_rows_preview", 5)
    show_columns = options.get("show_columns", True)
    show_dtypes = options.get("show_dtypes", True)
    show_null_counts = options.get("show_null_counts", True)
    show_summary_stats = options.get("show_summary_stats", True)
    show_unique_counts = options.get("show_unique_counts", True)
    include_columns = options.get("include_columns", None)
    exclude_columns = options.get("exclude_columns", None)

    # 筛选列
    columns = df.columns.tolist()
    if include_columns:
        columns = [col for col in columns if col in include_columns]
    if exclude_columns:
        columns = [col for col in columns if col not in exclude_columns]

    filtered_df = cast("pd.DataFrame", df[columns])

    # 构建结果
    result: InspectDataframeResult = {
        "shape": filtered_df.shape,
        "preview": filtered_df.head(n_rows_preview).to_string(),
        "memory_usage": f"{filtered_df.memory_usage(deep=True).sum() / 1048576:.3f} MB",
    }

    # 只有当show_columns为True时才包含列列表
    if show_columns:
        result["columns"] = columns

    # 数据类型
    if show_dtypes:
        result["dtypes"] = {col: str(filtered_df[col].dtype) for col in columns}

    # 空值数量
    if show_null_counts:
        result["null_counts"] = {col: int(filtered_df[col].isna().sum()) for col in columns}

    # 统计摘要
    if show_summary_stats:
        numeric_cols = filtered_df.select_dtypes(include="number").columns
        if not numeric_cols.empty:
            result["summary_stats"] = filtered_df[numeric_cols].describe().to_dict()

    # 唯一值数量
    if show_unique_counts:
        result["unique_counts"] = {col: int(filtered_df[col].nunique()) for col in columns}

    return result
