# ruff: noqa: S608

from pathlib import Path
from typing import override

import pandas as pd
from dremio import Dremio, JobResult, path_to_dotted

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
        formatted = path_to_dotted(source_name)
        try:
            count_query = f"SELECT COUNT(*) as row_count FROM {formatted}"
            count_df = self.execute_sql_to_dataframe(count_query)
            total_rows = int(count_df.iloc[0]["row_count"])
            logger.info(f"表 {source_name} 中共有 {total_rows} 条数据")

            n_rows = total_rows if fetch_all or limit is None else min(limit, total_rows)
            query = f"SELECT * FROM {formatted} FETCH NEXT {n_rows} ROWS ONLY"
            return self.execute_sql_to_dataframe(query)
        except Exception:
            logger.opt(exception=True).warning(f"读取数据源 {source_name} 时出错")

        logger.warning("回退到使用 REST API 读取数据源")
        return self._rest.read_source(source_name, limit=limit, fetch_all=fetch_all)

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

        sql_query = f"SELECT COUNT(*) as row_count FROM {path_to_dotted(source_name)}"
        result = self.execute_sql_to_dataframe(sql_query)
        row_count = int(result.iloc[0]["row_count"])

        first_line = self.read_source(source_name, limit=1)
        col_count = len(first_line.columns) if not first_line.empty else 0

        return row_count, col_count

    @override
    def list_sources(self) -> list[DremioSource]:
        return self._rest.list_sources()
