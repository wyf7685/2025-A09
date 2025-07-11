from pathlib import Path
from typing import Any

import pandas as pd

from app.core.dremio.rest import DremioSource

from .csv import CSVDataSource
from .dremio import DremioDataSource
from .memory import InMemoryDataSource
from .source import DataSource as DataSource
from .source import DataSourceMetadata


def create_csv_source(file_path: Path, name: str | None = None, **pandas_kwargs: Any) -> CSVDataSource:
    """
    创建 CSV 数据源

    Args:
        file_path: CSV 文件路径
        name: 数据源名称，默认使用文件名
        **pandas_kwargs: 传递给 pandas.read_csv 的参数

    Returns:
        CSVDataSource: CSV 数据源
    """
    metadata = DataSourceMetadata(
        id=f"csv_{file_path.stem}",
        name=name or file_path.name,
        source_type="csv",
    )

    return CSVDataSource(file_path, metadata, **pandas_kwargs)


def create_dremio_source(
    dremio_source: DremioSource,
    name: str | None = None,
) -> DremioDataSource:
    """
    创建 Dremio 数据源

    Args:
        dremio_source: Dremio 数据源
        name: 数据源名称，默认使用 Dremio 路径

    Returns:
        DremioDataSource: Dremio 数据源
    """
    source_path = dremio_source.path
    source_name = ".".join(source_path) if isinstance(source_path, list) else source_path

    metadata = DataSourceMetadata(
        id=f"dremio_{source_name.replace('.', '_')}",
        name=name or source_name,
        source_type=f"dremio:{dremio_source.type}",
        description=getattr(dremio_source, "description", ""),
    )

    return DremioDataSource(dremio_source, metadata)


def create_df_source(
    df: pd.DataFrame,
    name: str,
    description: str = "",
) -> DataSource:
    """
    从 DataFrame 创建数据源

    Args:
        df: DataFrame 对象
        name: 数据源名称
        description: 数据源描述

    Returns:
        DataSource: 数据源
    """

    metadata = DataSourceMetadata(
        id=f"df_{name}",
        name=name,
        source_type="dataframe",
        description=description,
        row_count=len(df),
        column_count=len(df.columns),
        columns=df.columns.tolist(),
        dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
    )

    return InMemoryDataSource(df, metadata)


__all__  = [
    "DataSource",
    "DataSourceMetadata",
    "create_csv_source",
    "create_df_source",
    "create_dremio_source",
]
