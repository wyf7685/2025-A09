from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.dremio.rest import DremioSource

from .dremio import DremioDataSource
from .file import FileDataSource
from .memory import InMemoryDataSource
from .source import DataSource as DataSource
from .source import DataSourceMetadata


def create_file_source(file_path: Path, name: str | None = None, **pandas_kwargs: Any) -> DataSource:
    """
    创建 CSV/Excel 数据源

    Args:
        file_path: CSV/Excel 文件路径
        name: 数据源名称，默认使用文件名
        **pandas_kwargs: 传递给 read_csv/read_excel 的参数

    Returns:
        FileDataSource: 文件数据源
    """
    file_type = file_path.suffix.lower().removeprefix(".")
    if file_type not in {"csv", "xlsx", "xls"}:
        raise ValueError(f"不支持的文件类型: {file_type}. 仅支持 csv, xlsx, xls 文件")
    source_type = "csv" if file_type == "csv" else "excel"

    metadata = DataSourceMetadata(
        id=f"{source_type}_{file_path.stem}",
        name=name or file_path.name,
        source_type=source_type,
    )

    return FileDataSource(file_path, metadata, **pandas_kwargs)


def create_dremio_source(
    dremio_source: DremioSource,
    name: str | None = None,
    description: str | None = None,
) -> DataSource:
    """
    创建 Dremio 数据源

    Args:
        dremio_source: Dremio 数据源
        name: 数据源名称，默认使用 Dremio 路径
        description: 数据源描述

    Returns:
        DremioDataSource: Dremio 数据源
    """
    if (
        len(dremio_source.path) == 2
        and dremio_source.path[0] == settings.DREMIO_EXTERNAL_NAME
        and dremio_source.path[1].endswith(".csv")
    ):
        file_path = settings.DREMIO_EXTERNAL_DIR / Path(*dremio_source.path[1:])
        metadata = DataSourceMetadata(
            id=f"csv_{file_path.stem}",
            name=name or file_path.name,
            source_type="csv",
        )
        return FileDataSource(file_path, metadata)

    source_name = ".".join(dremio_source.path)

    metadata = DataSourceMetadata(
        id=f"dremio_{source_name.replace('.', '_')}",
        name=name or source_name,
        source_type=f"dremio:{dremio_source.type}",
        description=description or "",
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


def deserialize_data_source(type: str, data: dict[str, Any]) -> DataSource:  # noqa: A002
    match type:
        case "csv":
            return FileDataSource.deserialize(data)
        case "dremio":
            return DremioDataSource.deserialize(data)
        case _:
            raise ValueError(f"Unsupported data source type: {type}")


__all__ = [
    "DataSource",
    "DataSourceMetadata",
    "create_df_source",
    "create_dremio_source",
    "create_file_source",
]
