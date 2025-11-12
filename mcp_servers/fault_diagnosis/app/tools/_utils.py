from typing import cast

import pandas as pd


def filter_fault_samples(df: pd.DataFrame, target_col: str = "fail") -> pd.DataFrame:
    """
    工具: 过滤故障样本

    从数据框中提取标记为故障的样本。

    Args:
        df: 包含故障标签的数据框
        target_col: 故障标签列名，默认为"fail"

    Returns:
        仅包含故障样本的数据框
    """
    target = cast("pd.Series", df[target_col])
    if pd.api.types.is_integer_dtype(target):
        fault_samples = df[target == 1]
    elif pd.api.types.is_bool_dtype(target):
        fault_samples = df[target == True]  # noqa: E712
    else:
        fault_samples = df[target.astype(str).str.lower() == "true"]
    return cast("pd.DataFrame", fault_samples)


def filter_normal_samples(df: pd.DataFrame, target_col: str = "fail") -> pd.DataFrame:
    """
    工具: 过滤正常样本

    从数据框中提取标记为正常的样本。

    Args:
        df: 包含故障标签的数据框
        target_col: 故障标签列名，默认为"fail"

    Returns:
        仅包含正常样本的数据框
    """
    target = cast("pd.Series", df[target_col])
    if pd.api.types.is_integer_dtype(target):
        normal_samples = df[target == 0]
    elif pd.api.types.is_bool_dtype(target):
        normal_samples = df[target == False]  # noqa: E712
    else:
        normal_samples = df[target.astype(str).str.lower() == "false"]
    return cast("pd.DataFrame", normal_samples)
