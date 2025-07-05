def correlation_analysis(df, col1, col2, method="pearson"):
    # 相关性检测，增强健壮性
    from scipy.stats import pearsonr, spearmanr
    import pandas as pd

    # 检查列是否存在
    if col1 not in df.columns or col2 not in df.columns:
        raise ValueError(f"列 {col1} 或 {col2} 不存在")

    # 转为数值型，非数值型自动转为NaN
    x = pd.to_numeric(df[col1], errors="coerce")
    y = pd.to_numeric(df[col2], errors="coerce")

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

def lag_analysis(df, time_col1, time_col2):
    """
    计算两个时间字段的时滞（单位：秒），并返回分布统计、异常点等信息。
    """
    import pandas as pd
    # 转换为datetime
    t1 = pd.to_datetime(df[time_col1])
    t2 = pd.to_datetime(df[time_col2])
    lag = (t2 - t1).dt.total_seconds()
    result = {
        "mean_lag_seconds": lag.mean(),
        "max_lag_seconds": lag.max(),
        "min_lag_seconds": lag.min(),
        "std_lag_seconds": lag.std(),
        "lag_outliers": df[(lag > lag.mean() + 3 * lag.std()) | (lag < lag.mean() - 3 * lag.std())][[time_col1, time_col2]].to_dict(orient="records"),
        "lag_distribution": lag.describe().to_dict()
    }
    return result

def detect_outliers(df, column, method="zscore", threshold=3):
    import numpy as np
    import pandas as pd

    # 只对数值型列做异常值检测
    if column not in df.columns:
        raise ValueError(f"列 {column} 不存在")
    series = pd.to_numeric(df[column], errors="coerce")
    if method == "zscore":
        mean = series.mean()
        std = series.std()
        mask = (np.abs(series - mean) > threshold * std)
    elif method == "iqr":
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        mask = (series < q1 - threshold * iqr) | (series > q3 + threshold * iqr)
    else:
        raise ValueError("不支持的异常值检测方法")
    return df[mask]