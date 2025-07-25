import abc
from datetime import datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.log import logger


class DataSourceMetadata(BaseModel):
    """数据源元数据"""

    id: str
    name: str
    source_type: str
    created_at: datetime = Field(default_factory=datetime.now)
    description: str = ""
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] | None = None
    dtypes: dict[str, str] | None = None
    preview_rows: int = 5
    column_description: dict[str, str] | None = None


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

    @abc.abstractmethod
    def _shape(self) -> tuple[int, int]:
        """
        获取数据源的形状

        Returns:
            tuple[int, int]: (行数, 列数)
        """
        raise NotImplementedError("子类必须实现get_shape方法")

    def get_shape(self) -> tuple[int, int]:
        """
        获取数据源的形状

        Returns:
            tuple[int, int]: (行数, 列数)
        """
        shape = self._full_data.shape if self._full_data is not None else self._shape()
        self.metadata.row_count = shape[0]
        self.metadata.column_count = shape[1]
        return shape

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
            self.set_full_data(self._load())
            assert self._full_data is not None

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

    def format_overview(self) -> str:
        df = self.get_preview(self.metadata.preview_rows)
        w, h = self.get_shape()

        # 处理字段映射和描述
        original_columns = df.columns.tolist()

        # 构建显示用的列名信息
        if aliases := (self.metadata.column_description or {}):
            # 如果有字段映射，显示原始名称 -> 清洗后名称
            mapped_columns = [aliases.get(col, col) for col in original_columns]
            column_info = (
                f"- 原始列名: {original_columns}\n"
                f"- 清洗后列名: {mapped_columns}\n"
                f"- 字段映射:\n{''.join(f'  - {orig} -> {aliases.get(orig, orig)}\n' for orig in original_columns)}\n"
            )

            # 为数据预览重命名列（仅用于显示）
            display_df = df.copy()
            display_df.columns = mapped_columns
        else:
            # 没有字段映射时的默认显示
            column_info = f"- 列名: {original_columns}\n"
            display_df = df

        return (
            f"- 数据源名称: {self.metadata.name}\n"
            f"- 数据源描述: {self.metadata.description or '无'}\n"
            f"- 数据规模: {w} 行 × {h} 列\n"
            f"- 列数据类型:\n<dtypes>\n{display_df.dtypes}\n</dtypes>\n"
            f"<column_info>\n{column_info}</column_info>\n"
            f"- 数据预览:\n<preview>\n{display_df.to_string()}\n</preview>\n"
        )

    @abc.abstractmethod
    def copy[S](self: S) -> S:
        raise NotImplementedError("子类必须实现copy方法")

    def copy_with_data(self) -> "DataSource":
        from . import create_df_source

        return create_df_source(self.get_full(), self.metadata.name, self.metadata.description)

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
