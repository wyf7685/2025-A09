import abc
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from app.log import logger


@dataclass
class DataSourceMetadata:
    """数据源元数据"""

    id: str
    name: str
    source_type: str  # 'csv', 'postgres', 'dremio' 等
    created_at: datetime = field(default_factory=datetime.now)
    description: str = ""
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] | None = None
    dtypes: dict[str, str] | None = None
    preview_rows: int = 5

    def copy(self) -> "DataSourceMetadata":
        return DataSourceMetadata(**dataclasses.asdict(self))


class DataSource(abc.ABC):
    """数据源抽象基类"""

    def __init__(self, metadata: DataSourceMetadata) -> None:
        """
        初始化数据源

        Args:
            metadata: 数据源元数据
        """
        self.metadata = metadata
        self._full_data: pd.DataFrame | None = None
        self._preview_data: pd.DataFrame | None = None

    @abc.abstractmethod
    def _load(self, n_rows: int | None = None) -> pd.DataFrame:
        """
        加载数据源，返回一个DataFrame

        Args:
            n_rows: 读取的行数，为None表示读取全部数据

        Returns:
            pd.DataFrame: 数据源的DataFrame
        """
        raise NotImplementedError("子类必须实现_load方法")

    def get_preview(self, n_rows: int = 5, force_reload: bool = False) -> pd.DataFrame:
        """
        获取数据源的预览数据

        Args:
            n_rows: 预览行数，默认为5行
            force_reload: 是否强制重新加载

        Returns:
            pd.DataFrame: 数据源的预览数据
        """
        if self._preview_data is None or force_reload or n_rows > self.metadata.preview_rows:
            logger.debug(f"读取数据源预览数据: {n_rows=}")
            self._preview_data = self._load(n_rows)
            self.metadata.preview_rows = n_rows

            # 更新元数据
            if self.metadata.columns is None:
                self.metadata.columns = self._preview_data.columns.tolist()
            if self.metadata.column_count is None:
                self.metadata.column_count = len(self._preview_data.columns)
            if self.metadata.dtypes is None:
                self.metadata.dtypes = {col: str(dtype) for col, dtype in self._preview_data.dtypes.items()}

            return self._preview_data

        return self._preview_data.head(n_rows)

    def get_data(self, n_rows: int | None = None) -> pd.DataFrame:
        """
        获取数据源的数据，支持部分加载

        Args:
            n_rows: 读取的行数，为None表示读取全部数据

        Returns:
            pd.DataFrame: 数据源的数据
        """
        if n_rows is None:
            return self.get_full()

        if self._full_data is not None:
            return self._full_data.head(n_rows)

        if self._preview_data is not None and n_rows <= self.metadata.preview_rows:
            return self._preview_data.head(n_rows)

        return self._load(n_rows)

    def get_full(self) -> pd.DataFrame:
        """
        获取数据源的完整数据

        Returns:
            pd.DataFrame: 数据源的完整数据
        """
        logger.debug("获取数据源完整数据")
        if self._full_data is None:
            self._full_data = self._load(None)

            # 更新元数据
            if self.metadata.row_count is None:
                self.metadata.row_count = len(self._full_data)

        return self._full_data

    def clear_cache(self) -> None:
        """清除数据缓存"""
        self._full_data = None
        self._preview_data = None

    def set_full_data(self, data: pd.DataFrame) -> None:
        """
        设置完整数据

        Args:
            data: 完整数据的DataFrame
        """
        self._full_data = data
        self.metadata.row_count = len(data)
        self.metadata.column_count = len(data.columns)
        self.metadata.columns = data.columns.tolist()
        self.metadata.dtypes = {col: str(dtype) for col, dtype in data.dtypes.items()}

    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示"""
        return dataclasses.asdict(self.metadata)

    @abc.abstractmethod
    def copy[S](self: S) -> S:
        raise NotImplementedError("子类必须实现copy方法")

    @property
    @abc.abstractmethod
    def unique_id(self) -> str:
        """
        获取数据源的唯一标识符

        Returns:
            str: 数据源的唯一ID
        """
        raise NotImplementedError("子类必须实现unique_id方法")

    @abc.abstractmethod
    def serialize(self) -> tuple[str, dict[str, Any]]:
        """
        序列化数据源为字典

        Returns:
            tuple[str, dict[str, Any]]: 序列化后的数据源信息
        """
        raise NotImplementedError("子类必须实现serialize方法")

    @classmethod
    @abc.abstractmethod
    def deserialize[S](cls: type[S], data: dict[str, Any]) -> S:
        """
        从字典反序列化数据源

        Args:
            data: 数据源的字典表示

        Returns:
            DataSource: 反序列化后的数据源对象
        """
        raise NotImplementedError("子类必须实现deserialize方法")
