import pandas as pd


def format_overview(df: pd.DataFrame) -> str:
    return (
        f"数据规模: {df.shape[0]} 行 × {df.shape[1]} 列\n列数据类型:\n{df.dtypes}\n数据预览:\n{df.head().to_string()}"
    )
