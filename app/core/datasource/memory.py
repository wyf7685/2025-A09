from typing import override

import pandas as pd

from .source import DataSource, DataSourceMetadata


class InMemoryDataSource(DataSource):
    """内存数据源实现，用于包装已有的 DataFrame"""

    def __init__(self, df: pd.DataFrame, metadata: DataSourceMetadata | None = None) -> None:
        """
        初始化内存数据源

        Args:
            df: 数据 DataFrame
            metadata: 数据源元数据，如果为None则自动创建
        """
        if metadata is None:
            metadata = DataSourceMetadata(
                id="memory_data",
                name="Memory Data",
                source_type="memory",
                row_count=len(df),
                column_count=len(df.columns),
                columns=df.columns.tolist(),
                dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
            )

        super().__init__(metadata)
        self._full_data: pd.DataFrame = df  # pyright: ignore[reportIncompatibleVariableOverride]

    @override
    def _load(self, n_rows: int | None = None) -> pd.DataFrame:
        """从内存加载数据"""
        if n_rows is None:
            return self._full_data
        return self._full_data.head(n_rows)

    @override
    def copy(self) -> "InMemoryDataSource":
        """创建内存数据源的副本"""
        return InMemoryDataSource(df=self._full_data.copy(), metadata=self.metadata.copy())
