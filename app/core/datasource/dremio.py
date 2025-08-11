from typing import Any, override

import pandas as pd
from pydantic import BaseModel

from app.core.dremio import AbstractDremioClient, get_async_dremio_client, get_dremio_client
from app.core.dremio.abstract import AbstractAsyncDremioClient
from app.schemas.dremio import DremioSource

from .source import DataSource, DataSourceMetadata


class DremioDataSourceModel(BaseModel):
    source: DremioSource
    metadata: DataSourceMetadata


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

    @property
    def client(self) -> AbstractDremioClient:
        """获取 Dremio 客户端"""
        return get_dremio_client()

    @property
    def async_client(self) -> AbstractAsyncDremioClient:
        """获取异步 Dremio 客户端"""
        return get_async_dremio_client()

    @override
    def _load(self, n_rows: int | None = None, skip: int | None = None) -> pd.DataFrame:
        """加载 Dremio 数据源数据"""
        return self.client.read_source(self.source.path, n_rows, skip)

    @override
    async def _load_async(self, n_rows: int | None = None, skip: int | None = None) -> pd.DataFrame:
        """异步加载 Dremio 数据源数据"""
        return await self.async_client.read_source(self.source.path, n_rows, skip)

    @override
    def _shape(self) -> tuple[int, int]:
        """获取 Dremio 数据源的形状"""
        return self.client.shape(self.source.path)

    @override
    async def _shape_async(self) -> tuple[int, int]:
        """异步获取 Dremio 数据源的形状"""
        return await self.async_client.shape(self.source.path)

    def get_source(self) -> DremioSource:
        """获取 Dremio 源"""
        return self.source

    @override
    def copy(self) -> "DremioDataSource":
        """创建 Dremio 数据源的副本"""
        return DremioDataSource(source=self.source, metadata=self.metadata.model_copy())

    @property
    @override
    def unique_id(self) -> str:
        return f"dremio:{'$'.join(self.source.path)}"

    @override
    def serialize(self) -> tuple[str, dict[str, Any]]:
        """序列化 Dremio 数据源"""
        return "dremio", DremioDataSourceModel(source=self.source, metadata=self.metadata).model_dump(mode="json")

    @classmethod
    @override
    def deserialize(cls, data: dict[str, Any]) -> "DremioDataSource":
        """反序列化 Dremio 数据源"""
        model = DremioDataSourceModel.model_validate(data)
        return cls(source=model.source, metadata=model.metadata)
