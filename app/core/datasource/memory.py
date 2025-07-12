from typing import Any, override

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
        self._data = df

    @override
    def _load(self, n_rows: int | None = None) -> pd.DataFrame:
        """从内存加载数据"""
        if n_rows is None:
            return self._data
        return self._data.head(n_rows)

    @override
    def copy(self) -> "InMemoryDataSource":
        """创建内存数据源的副本"""
        return InMemoryDataSource(df=self._data.copy(), metadata=self.metadata.copy())

    @property
    @override
    def unique_id(self) -> str:
        return f"memory:{id(self._full_data)}"

    @override
    def serialize(self) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError("InMemoryDataSource does not support serialization")

    @classmethod
    @override
    def deserialize(cls, data: dict[str, Any]) -> "InMemoryDataSource":
        raise NotImplementedError("InMemoryDataSource does not support deserialization")
