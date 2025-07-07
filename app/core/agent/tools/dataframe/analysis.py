from typing import Any, cast

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


def corr_analys(df: pd.DataFrame, col1: str, col2: str, method: str = "pearson") -> dict[str, Any]:
    """
    执行两个指定列之间的相关性分析。
    支持 Pearson (默认) 和 Spearman 方法。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        col1 (str): 第一个要分析的列名。
        col2 (str): 第二个要分析的列名。
        method (str): 相关性计算方法，可以是 'pearson' 或 'spearman'。

    Returns:
        dict: 包含相关系数和p值的结果字典。
    """
    # 相关性检测，增强健壮性
    # 检查列是否存在
    if col1 not in df.columns or col2 not in df.columns:
        raise ValueError(f"列 {col1} 或 {col2} 不存在")

    # 转为数值型，非数值型自动转为NaN
    x = cast("pd.Series", pd.to_numeric(df[col1], errors="coerce"))
    y = cast("pd.Series", pd.to_numeric(df[col2], errors="coerce"))

    # 检查有效数据量
    valid = x.notna() & y.notna()
    if valid.sum() < 3:
        raise ValueError(f"用于相关性分析的有效数据太少（仅{valid.sum()}行）")

    x = x[valid]
    y = y[valid]

    if method == "pearson":
        corr, p = pearsonr(x, y)
    else:
        corr, p = spearmanr(x, y)
    return {"correlation": corr, "p_value": p}


def lag_analys(df: pd.DataFrame, time_col1: str, time_col2: str) -> dict[str, Any]:
    """
    计算两个时间字段之间的时滞（单位：秒），并返回分布统计、异常点等信息。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        time_col1 (str): 第一个时间列的名称。
        time_col2 (str): 第二个时间列的名称。

    Returns:
        dict: 包含平均时滞、最大时滞、最小时滞、标准差、时滞异常点和时滞分布描述的结果字典。
    """
    # 转换为datetime
    t1 = pd.to_datetime(df[time_col1])
    t2 = pd.to_datetime(df[time_col2])
    lag = (t2 - t1).dt.total_seconds()
    df1 = df[(lag > lag.mean() + 3 * lag.std()) | (lag < lag.mean() - 3 * lag.std())][[time_col1, time_col2]]
    return {
        "mean_lag_seconds": lag.mean(),
        "max_lag_seconds": lag.max(),
        "min_lag_seconds": lag.min(),
        "std_lag_seconds": lag.std(),
        "lag_outliers": cast("pd.DataFrame", df1).to_dict(orient="records"),
        "lag_distribution": lag.describe().to_dict(),
    }


def detect_outliers(df: pd.DataFrame, column: str, method: str = "zscore", threshold: int = 3) -> pd.DataFrame:
    """
    在指定列中检测异常值。
    支持 'zscore' (默认) 和 'iqr' 方法。

    Args:
        df (pd.DataFrame): 输入的DataFrame。
        column (str): 要检测异常值的列名。
        method (str): 异常值检测方法，可以是 'zscore' 或 'iqr'。
        threshold (int): 检测阈值。对于zscore，是标准差倍数；对于iqr，是IQR倍数。

    Returns:
        pd.DataFrame: 包含检测到的异常值的DataFrame。
    """
    # 只对数值型列做异常值检测
    if column not in df.columns:
        raise ValueError(f"列 {column} 不存在")
    series = cast("pd.Series", pd.to_numeric(df[column], errors="coerce"))
    if method == "zscore":
        mean = series.mean()
        std = series.std()
        mask = np.abs(series - mean) > threshold * std
    elif method == "iqr":
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        mask = (series < q1 - threshold * iqr) | (series > q3 + threshold * iqr)
    else:
        raise ValueError("不支持的异常值检测方法")
    return cast("pd.DataFrame", df[mask])
