# ruff: noqa: S608

from pathlib import Path
from typing import override

import pandas as pd
from dremio import Dremio, FlightConfig, JobResult, path_to_dotted

from app.core.config import settings
from app.core.dremio.abstract import AbstractDremioClient
from app.core.dremio.rest import DremioRestClient
from app.log import logger
from app.schemas.dremio import BaseDatabaseConnection, DremioDatabaseType, DremioSource


class DremioFlightClient(AbstractDremioClient):
    def __init__(self) -> None:
        self._client = Dremio(
            hostname=settings.DREMIO_BASE_URL,
            username=settings.DREMIO_USERNAME,
            password=settings.DREMIO_PASSWORD.get_secret_value(),
            flight_config=FlightConfig(port=settings.DREMIO_FLIGHT_PORT),
        )
        self._rest = DremioRestClient()
        self.external_dir = settings.DREMIO_EXTERNAL_DIR
        self.external_name = settings.DREMIO_EXTERNAL_NAME

    @override
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
        return self._rest.add_data_source_file(file, "csv")

    @override
    def _add_data_source_excel(self, file: Path) -> DremioSource:
        return self._rest.add_data_source_file(file, "excel")

    @override
    def add_data_source_database(
        self,
        database_type: DremioDatabaseType,
        connection: BaseDatabaseConnection,
    ) -> DremioSource:
        return self._rest.add_data_source_database(database_type, connection)

    @override
    def read_source(
        self,
        source_name: str | list[str],
        limit: int | None = None,
        skip: int | None = None,
    ) -> pd.DataFrame:
        """
        读取数据源的数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制
            skip: 跳过的行数，为None表示不跳过

        Returns:
            pandas.DataFrame: 数据源数据
        """
        formatted = path_to_dotted(source_name)
        skip = skip or 0

        try:
            count_query = f"SELECT COUNT(*) as row_count FROM {formatted}"
            count_df = self.execute_sql_to_dataframe(count_query)
            total_rows = int(count_df.iloc[0]["row_count"])
            logger.info(f"表 {source_name} 中共有 {total_rows} 条数据")

            total_rows -= skip
            n_rows = total_rows if limit is None else min(limit, total_rows)
            if n_rows <= 0:
                return pd.DataFrame()  # 如果没有数据，返回空 DataFrame

            query = f"SELECT * FROM {formatted} OFFSET {skip} ROWS FETCH NEXT {n_rows} ROWS ONLY"
            return self.execute_sql_to_dataframe(query)
        except Exception:
            logger.opt(exception=True).warning(f"读取数据源 {source_name} 时出错")

        logger.warning("回退到使用 REST API 读取数据源")
        return self._rest.read_source(source_name, limit=limit, skip=skip)

    def execute_sql_to_dataframe(self, sql_query: str) -> pd.DataFrame:
        """
        执行 SQL 查询并返回 DataFrame

        Args:
            sql_query: SQL 查询语句

        Returns:
            pandas.DataFrame: 查询结果的 DataFrame
        """
        logger.info(f"执行 SQL 查询: {sql_query}")
        table = self._client.flight.query(sql_query, flight_config=self._client.flight_config)
        return JobResult.from_arrow_table(table).to_pandas()

    @override
    def shape(self, source_name: str | list[str]) -> tuple[int, int]:
        """
        获取数据源的形状（行数和列数）

        Args:
            source_name: 数据源名称

        Returns:
            tuple[int, int]: (行数, 列数)
        """
        try:
            formatted = path_to_dotted(source_name)
            sql_query = f"SELECT COUNT(*) as row_count FROM {formatted}"
            result = self.execute_sql_to_dataframe(sql_query)
            row_count = int(result.iloc[0]["row_count"])

            first_line = self.read_source(source_name, limit=1)
            col_count = len(first_line.columns) if not first_line.empty else 0

            return row_count, col_count
        except Exception as e:
            logger.warning(f"Flight客户端获取形状失败: {e}")
            logger.info("回退到使用REST API获取形状")
            return self._rest.shape(source_name)

    @override
    def list_sources(self) -> list[DremioSource]:
        return self._rest.list_sources()

    @override
    def delete_data_source(self, source_path: list[str]) -> bool:
        """
        删除Dremio中的数据源，委托给REST客户端

        Args:
            source_path: 数据源路径，例如 ["external", "filename.csv"]

        Returns:
            bool: 是否删除成功
        """
        return self._rest.delete_data_source(source_path)

    @override
    def refresh_external_source(self) -> bool:
        """
        刷新external数据源，委托给REST客户端

        Returns:
            bool: 是否刷新成功
        """
        return self._rest.refresh_external_source()
