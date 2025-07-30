import abc
from pathlib import Path
from typing import Literal

import pandas as pd

from app.schemas.dremio import BaseDatabaseConnection, DremioDatabaseType, DremioSource


class AbstractDremioClient(abc.ABC):
    @abc.abstractmethod
    def _add_data_source_csv(self, file: Path) -> DremioSource:
        """
        添加 CSV 数据源到 Dremio 外部目录

        Args:
            file: CSV 文件路径

        Returns:
            DremioSource: 生成的 DremioSource 对象

        Raises:
            ValueError: 如果未设置 external_dir
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    def _add_data_source_excel(self, file: Path) -> DremioSource:
        """
        添加 Excel 数据源到 Dremio 外部目录

        Args:
            file: Excel 文件路径

        Returns:
            DremioSource: 生成的 DremioSource 对象
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    def add_data_source_file(self, file: Path, format: Literal["csv", "excel"] | None = None) -> DremioSource:
        """
        添加文件数据源到 Dremio 外部目录

        Args:
            file: 文件路径
            format: 文件格式，支持 "csv" 或 "excel"，如果为 None 则根据文件扩展名自动判断

        Returns:
            DremioSource: 生成的 DremioSource 对象
        """
        if format is None:
            suffix = file.suffix.lower()
            if suffix == ".csv":
                format = "csv"
            elif suffix in {".xlsx", ".xls"}:
                format = "excel"
            else:
                raise ValueError("Unsupported file format. Please specify 'csv' or 'excel'.")

        if format == "csv":
            return self._add_data_source_csv(file)
        if format == "excel":
            return self._add_data_source_excel(file)
        raise ValueError(f"Unsupported format: {format}. Supported formats are 'csv' and 'excel'.")

    @abc.abstractmethod
    def add_data_source_database(
        self,
        database_type: DremioDatabaseType,
        connection: BaseDatabaseConnection,
    ) -> DremioSource:
        """
        添加数据库数据源到 Dremio

        Args:
            database_type: 数据库类型
            connection: 数据库连接信息

        Returns:
            DremioSource: 生成的 DremioSource 对象
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    def read_source(
        self,
        source_name: str | list[str],
        limit: int | None = None,
        *,
        fetch_all: bool = False,
    ) -> pd.DataFrame:
        """
        读取数据源的数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制
            fetch_all: 是否获取全部数据（会忽略limit参数）

        Returns:
            pandas.DataFrame: 数据源数据
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    def shape(self, source_name: str | list[str]) -> tuple[int, int]:
        """
        获取数据源的形状（行数和列数）

        Args:
            source_name: 数据源名称

        Returns:
            tuple[int, int]: (行数, 列数)
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    def list_sources(self) -> list[DremioSource]:
        """
        列出 Dremio 中的所有数据源

        Returns:
            list[DremioSource]: DremioSource 对象列表
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    def delete_data_source(self, source_path: list[str]) -> bool:
        """
        删除Dremio中的数据源

        Args:
            source_path: 数据源路径，例如 ["external", "filename.csv"]

        Returns:
            bool: 是否删除成功
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    def refresh_external_source(self) -> bool:
        """
        刷新external数据源，让Dremio重新扫描external目录

        Returns:
            bool: 是否刷新成功
        """
        raise NotImplementedError("This method should be implemented by subclasses.")


class AbstractAsyncDremioClient(abc.ABC):
    @abc.abstractmethod
    async def _add_data_source_csv(self, file: Path) -> DremioSource:
        """
        添加 CSV 数据源到 Dremio 外部目录

        Args:
            file: CSV 文件路径

        Returns:
            DremioSource: 生成的 DremioSource 对象

        Raises:
            ValueError: 如果未设置 external_dir
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    async def _add_data_source_excel(self, file: Path) -> DremioSource:
        """
        添加 Excel 数据源到 Dremio 外部目录

        Args:
            file: Excel 文件路径

        Returns:
            DremioSource: 生成的 DremioSource 对象
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    async def add_data_source_file(self, file: Path, format: Literal["csv", "excel"] | None = None) -> DremioSource:
        """
        添加文件数据源到 Dremio 外部目录

        Args:
            file: 文件路径
            format: 文件格式，支持 "csv" 或 "excel"，如果为 None 则根据文件扩展名自动判断

        Returns:
            DremioSource: 生成的 DremioSource 对象
        """
        if format is None:
            suffix = file.suffix.lower()
            if suffix == ".csv":
                format = "csv"
            elif suffix in {".xlsx", ".xls"}:
                format = "excel"
            else:
                raise ValueError("Unsupported file format. Please specify 'csv' or 'excel'.")

        if format == "csv":
            return await self._add_data_source_csv(file)
        if format == "excel":
            return await self._add_data_source_excel(file)
        raise ValueError(f"Unsupported format: {format}. Supported formats are 'csv' and 'excel'.")

    @abc.abstractmethod
    async def add_data_source_database(
        self,
        database_type: DremioDatabaseType,
        connection: BaseDatabaseConnection,
    ) -> DremioSource:
        """
        添加数据库数据源到 Dremio

        Args:
            database_type: 数据库类型
            connection: 数据库连接信息

        Returns:
            DremioSource: 生成的 DremioSource 对象
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    async def read_source(
        self,
        source_name: str | list[str],
        limit: int | None = None,
        *,
        fetch_all: bool = False,
    ) -> pd.DataFrame:
        """
        读取数据源的数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制
            fetch_all: 是否获取全部数据（会忽略limit参数）

        Returns:
            pandas.DataFrame: 数据源数据
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    async def shape(self, source_name: str | list[str]) -> tuple[int, int]:
        """
        获取数据源的形状（行数和列数）

        Args:
            source_name: 数据源名称

        Returns:
            tuple[int, int]: (行数, 列数)
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    async def list_sources(self) -> list[DremioSource]:
        """
        列出 Dremio 中的所有数据源

        Returns:
            list[DremioSource]: DremioSource 对象列表
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    async def delete_data_source(self, source_path: list[str]) -> bool:
        """
        删除Dremio中的数据源

        Args:
            source_path: 数据源路径，例如 ["external", "filename.csv"]

        Returns:
            bool: 是否删除成功
        """
        raise NotImplementedError("This method should be implemented by subclasses.")

    @abc.abstractmethod
    async def refresh_external_source(self) -> bool:
        """
        刷新external数据源，让Dremio重新扫描external目录

        Returns:
            bool: 是否刷新成功
        """
        raise NotImplementedError("This method should be implemented by subclasses.")
