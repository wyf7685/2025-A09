from pathlib import Path
from typing import Any, override

import pandas as pd

from .source import DataSource, DataSourceMetadata


class CSVDataSource(DataSource):
    """CSV 文件数据源实现"""

    def __init__(self, file_path: Path, metadata: DataSourceMetadata | None = None, **pandas_kwargs: Any) -> None:
        """
        初始化 CSV 数据源

        Args:
            file_path: CSV 文件路径
            metadata: 数据源元数据，如果为None则自动创建
            **pandas_kwargs: 传递给 pandas.read_csv 的参数
        """
        if metadata is None:
            # 创建基本元数据
            metadata = DataSourceMetadata(
                id=f"csv_{file_path.stem}",
                name=file_path.name,
                source_type="csv",
            )

        super().__init__(metadata)
        self.file_path = file_path
        self.pandas_kwargs = pandas_kwargs

    @override
    def _load(self, n_rows: int | None = None) -> pd.DataFrame:
        """加载 CSV 文件数据"""
        kwargs = self.pandas_kwargs.copy()
        if n_rows is not None:
            kwargs["nrows"] = n_rows

        return pd.read_csv(self.file_path, **kwargs)

    @override
    def copy(self) -> "CSVDataSource":
        return CSVDataSource(file_path=self.file_path, metadata=self.metadata.copy(), **self.pandas_kwargs)
