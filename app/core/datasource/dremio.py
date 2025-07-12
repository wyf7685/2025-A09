from typing import override

import pandas as pd

from app.core.dremio import get_dremio_client
from app.core.dremio.rest import DremioClient, DremioSource

from .source import DataSource, DataSourceMetadata


class DremioDataSource(DataSource):
    """Dremio 数据源实现"""

    def __init__(self, source: DremioSource, metadata: DataSourceMetadata | None = None) -> None:
        """
        初始化 Dremio 数据源

        Args:
            source: Dremio 数据源
            metadata: 数据源元数据，如果为None则自动创建
        """
        if metadata is None:
            # 从 DremioSource 创建元数据
            source_name = ".".join(source.path) if isinstance(source.path, list) else source.path
            metadata = DataSourceMetadata(
                id=f"dremio_{source_name}",
                name=source_name,
                source_type=f"dremio:{source.type}",
                description=getattr(source, "description", ""),
            )

        super().__init__(metadata)
        self.source = source
        self._client: DremioClient | None = None

    @property
    def client(self) -> DremioClient:
        """获取 Dremio 客户端"""
        if self._client is None:
            self._client = get_dremio_client()
        return self._client

    @override
    def _load(self, n_rows: int | None = None) -> pd.DataFrame:
        """加载 Dremio 数据源数据"""
        return self.client.read_source(self.source.path, n_rows)

    def get_source(self) -> DremioSource:
        """获取 Dremio 源"""
        return self.source

    @override
    def copy(self) -> "DremioDataSource":
        """创建 Dremio 数据源的副本"""
        return DremioDataSource(source=self.source, metadata=self.metadata.copy())
