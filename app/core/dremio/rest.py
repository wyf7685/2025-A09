# ruff: noqa: S608, S113
import json
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from app.log import logger

from .tmp_source import TemporaryDataSource


@dataclass
class DremioSource:
    id: str
    path: list[str]
    type: str


@dataclass
class DremioContainer:
    id: str
    path: list[str]


class DremioClient:
    """Dremio REST API 客户端"""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        external_dir: Path | None = None,
        external_name: str | None = None,
    ) -> None:
        """
        初始化 Dremio 客户端

        Args:
            base_url: Dremio REST API 地址
            username: 登录 Dremio UI 的用户名
            password: 登录 Dremio UI 的密码
            external_dir: 外部数据源本地目录路径
            external_name: 外部数据源名称
        """
        self.base_url = base_url or os.environ.get("DREMIO_BASE_URL", "http://localhost:9047")
        self.username = username or os.environ.get("DREMIO_USERNAME")
        self.password = password or os.environ.get("DREMIO_PASSWORD")
        self.external_dir = external_dir or Path(os.environ.get("DREMIO_EXTERNAL_DIR", "external"))
        self.external_name = external_name or os.environ.get("DREMIO_EXTERNAL_NAME", "external")
        assert self.base_url, "Dremio base URL is required"
        assert self.username, "Dremio username is required"
        assert self.password, "Dremio password is required"
        self._token = None

    def get_token(self) -> str:
        """
        获取临时 Token，如果已存在则直接返回

        Returns:
            str: 认证 token
        """
        if self._token is None:
            self._token = self._get_temp_token()
        return self._token

    def _get_temp_token(self) -> str:
        """
        获取临时 Token

        Returns:
            str: 认证 token
        """
        login_url = f"{self.base_url}/apiv2/login"
        login_payload = {"userName": self.username, "password": self.password}
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            login_url,
            headers=headers,
            data=json.dumps(login_payload),
        )
        response.raise_for_status()
        return response.json()["token"]

    def get_auth_header(self) -> dict[str, str]:
        """
        获取认证头部

        Returns:
            dict[str, str]: 包含认证信息的请求头
        """

        return {
            "Authorization": f"_dremio{self.get_token()}",
            "Content-Type": "application/json",
        }

    def create_query_job(self, sql_query: str) -> str:
        """
        创建查询任务

        Args:
            sql_query: SQL 查询语句

        Returns:
            str: 查询任务 ID
        """
        submit_url = f"{self.base_url}/api/v3/sql"
        sql_payload = {"sql": sql_query}

        response = requests.post(
            submit_url,
            headers=self.get_auth_header(),
            data=json.dumps(sql_payload),
        )
        response.raise_for_status()
        return response.json()["id"]

    def wait_for_job_completion(self, job_id: str) -> dict[str, Any]:
        """
        等待查询任务完成

        Args:
            job_id: 查询任务 ID

        Returns:
            dict[str, Any]: 任务状态信息

        Raises:
            Exception: 任务失败时抛出异常
        """
        job_status_url = f"{self.base_url}/api/v3/job/{job_id}"
        while True:
            response = requests.get(job_status_url, headers=self.get_auth_header())
            response.raise_for_status()
            job_status = response.json()
            if job_status["jobState"] == "COMPLETED":
                return job_status
            if job_status["jobState"] in ["FAILED", "CANCELED", "INVALID"]:
                logger.warning(f"查询任务失败\n{job_status}")
                raise Exception(f"Query failed with state: {job_status['jobState']}")  # noqa: TRY002
            time.sleep(1)

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        """
        获取查询结果

        Args:
            job_id: 查询任务 ID

        Returns:
            dict[str, Any]: 查询结果
        """
        result_url = f"{self.base_url}/api/v3/job/{job_id}/results"
        response = requests.get(result_url, headers=self.get_auth_header())
        response.raise_for_status()
        return response.json()

    def execute_sql_query(self, sql_query: str) -> dict[str, Any]:
        """
        执行 SQL 查询

        Args:
            sql_query: SQL 查询语句

        Returns:
            dict[str, Any]: 查询结果
        """
        job_id = self.create_query_job(sql_query)
        logger.opt(colors=True).info(f"查询提交成功，Job ID: <c>{job_id}</>")

        self.wait_for_job_completion(job_id)
        logger.opt(colors=True).success(f"查询完成: <c>{job_id}</>")

        return self.get_job_result(job_id)

    def execute_sql_to_dataframe(self, sql_query: str) -> pd.DataFrame:
        """
        执行 SQL 查询并返回 DataFrame

        Args:
            sql_query: SQL 查询语句
            token: 可选的认证 token

        Returns:
            pandas.DataFrame: 查询结果的 DataFrame
        """
        results = self.execute_sql_query(sql_query)
        return pd.DataFrame(results["rows"])

    def _format_source_name_table(self, source_name: str | list[str]) -> str:
        if isinstance(source_name, list):
            return ".".join(f'"{part}"' for part in source_name)
        return f'"{source_name}"'

    def add_data_source_csv(self, file: Path) -> list[str]:
        """
        添加 CSV 数据源到 Dremio 外部目录

        Args:
            file: CSV 文件路径
            token: 可选的认证 token

        Returns:
            str: 生成的源文件名

        Raises:
            ValueError: 如果未设置 external_dir
        """
        if self.external_dir is None:
            raise ValueError("外部数据源目录未设置")

        source_name = f"{uuid.uuid4()}.csv"
        shutil.copyfile(file, self.external_dir / source_name)

        # 设置 "external"."{source_name}" 的属性: 自动读取文件首行作为列名
        url = f"{self.base_url}/apiv2/source/{self.external_name}/file_format/{source_name}"
        payload = {
            "fieldDelimiter": ",",
            "quote": '"',
            "comment": "#",
            "lineDelimiter": "\r\n",
            "escape": '"',
            "extractHeader": True,
            "trimHeader": True,
            "skipFirstLine": False,
            "type": "Text",
        }

        response = requests.put(
            url,
            headers=self.get_auth_header(),
            data=json.dumps(payload),
        )
        response.raise_for_status()

        return [self.external_name, source_name]

    # TODO: 改写为通用数据库连接
    def add_data_source_postgres(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
    ) -> str:
        """
        添加 PostgreSQL 数据源到 Dremio

        Args:
            host: PostgreSQL 主机地址
            port: PostgreSQL 端口
            database: 数据库名
            user: 数据库用户名
            password: 数据库密码

        Returns:
            str: 数据源名称
        """
        source_name = str(uuid.uuid4())
        url = f"{self.base_url}/api/v3/catalog"
        payload = {
            "entityType": "source",
            "name": source_name,
            "type": "POSTGRES",
            "config": {
                "hostname": host,
                "port": str(port),
                "databaseName": database,
                "username": user,
                "password": password,
                "maxIdleConns": 8,
            },
            "metadataPolicy": {
                "authTTLMs": 86400000,
                "datasetExpireAfterMs": 10800000,
                "namesRefreshMs": 3600000,
                "datasetUpdateMode": "PREFETCH_QUERIED",
                "deleteUnavailableDatasets": True,
                "autoPromoteDatasets": True,
            },
        }

        response = requests.post(
            url,
            headers=self.get_auth_header(),
            data=json.dumps(payload),
        )
        response.raise_for_status()
        return source_name

    def query_source_tables(self, source_name: str | list[str]) -> list[DremioSource]:
        """
        查询指定数据源的所有表

        Args:
            source_name: 数据源名称

        Returns:
            list[list[str]]: 表路径列表
        """
        logger.info(f"查询数据源 {source_name} 的子项...")
        if isinstance(source_name, list):
            source_name = "/".join(source_name)
        url = f"{self.base_url}/api/v3/catalog/by-path/{source_name}"
        response = requests.get(url, headers=self.get_auth_header())
        response.raise_for_status()

        sources: list[DremioSource] = []
        for child in response.json()["children"]:
            path: list[str] = child["path"]
            if child["type"] in {"DATASET", "FILE"}:
                sources.append(DremioSource(id=child["id"], path=path, type=child["type"]))
            elif child["type"] == "CONTAINER" and child["containerType"] == "FOLDER":
                sources.extend(self.query_source_tables("/".join(path)))

        return sources

    def read_source(
        self,
        source_name: str | list[str],
        limit: int | None = None,
        *,
        fetch_all: bool = False,
        max_workers: int = 5,
    ) -> pd.DataFrame:
        """
        读取数据源的数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制
            fetch_all: 是否获取全部数据（会忽略limit参数）
            max_workers: 分批查询时的最大线程数

        Returns:
            pandas.DataFrame: 数据源数据
        """
        source_name = self._format_source_name_table(source_name)

        if limit is None:
            fetch_all = True

        if not fetch_all and limit is not None and limit <= 100:
            sql_query = f"SELECT * FROM {source_name} FETCH FIRST {limit} ROWS ONLY"
            return self.execute_sql_to_dataframe(sql_query)

        try:
            # 首先获取计数
            count_query = f"SELECT COUNT(*) as row_count FROM {source_name}"
            count_df = self.execute_sql_to_dataframe(count_query)
            total_rows = int(count_df.iloc[0]["row_count"])
            logger.info(f"表 {source_name} 中共有 {total_rows} 条数据")

            batch_size = 100  # Dremio REST api 单次查询最大数据量
            total_rows = total_rows if fetch_all or limit is None else min(total_rows, limit)
            batch_ranges = (
                (offset, min(batch_size, total_rows - offset)) for offset in range(0, total_rows, batch_size)
            )
            all_data: dict[int, pd.DataFrame] = {}

            def fetch(idx: int, offset: int, size: int) -> None:
                logger.info(f"正在获取第 {offset + 1}-{offset + size} 条数据...")
                batch_query = f"SELECT * FROM {source_name} OFFSET {offset} ROWS FETCH NEXT {size} ROWS ONLY"
                data = self.execute_sql_to_dataframe(batch_query)
                all_data[idx] = data

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, (offset, size) in enumerate(batch_ranges):
                    executor.submit(fetch, idx, offset, size)

            if dfs := [all_data[idx] for idx in sorted(all_data.keys())]:
                result = pd.concat(dfs, ignore_index=True)
                logger.info(f"通过分批查询共获取 {len(result)} 条数据")
                return result

            return pd.DataFrame()

        except Exception:
            logger.exception("分批查询失败")

        logger.warning("警告: 无法获取全部数据，返回最多可获取的数据")
        return self.execute_sql_to_dataframe(f"SELECT * FROM {source_name} FETCH FIRST 1000 ROWS ONLY")

    def shape(self, source_name: str | list[str]) -> tuple[int, int]:
        """
        获取数据源的形状（行数和列数）

        Args:
            source_name: 数据源名称

        Returns:
            tuple[int, int]: (行数, 列数)
        """

        sql_query = f"SELECT COUNT(*) as row_count FROM {self._format_source_name_table(source_name)}"
        result = self.execute_sql_to_dataframe(sql_query)
        row_count = int(result.iloc[0]["row_count"])

        first_line = self.read_source(source_name, limit=1)
        col_count = len(first_line.columns) if not first_line.empty else 0

        return row_count, col_count

    def data_source_csv(self, file: Path) -> TemporaryDataSource:
        source_name = self.add_data_source_csv(file)
        return TemporaryDataSource(self, "csv", source_name)

    def data_source_postgres(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        table: str | None = None,
    ) -> TemporaryDataSource:
        source_name = self.add_data_source_postgres(host, port, database, user, password)
        tables = self.query_source_tables(source_name)
        if not tables:
            raise ValueError(f"数据源 {source_name} 中没有可用的表")

        if table is None:
            source_name = tables[0].path
        else:
            for t in tables:
                if t.path[-1] == table:
                    source_name = t.path
                    break
            else:
                raise ValueError(f"数据源 {source_name} 中没有找到表 {table}")

        return TemporaryDataSource(self, "database", source_name)

    def list_containers(self) -> list[DremioContainer]:
        logger.info("查询 Dremio 中的所有容器...")
        url = f"{self.base_url}/api/v3/catalog"
        response = requests.get(url, headers=self.get_auth_header())
        response.raise_for_status()

        return [
            DremioContainer(id=item["id"], path=item["path"])
            for item in response.json()["data"]
            if item["type"] == "CONTAINER" and item["containerType"] == "SOURCE"
        ]

    def list_sources(self) -> list[DremioSource]:
        logger.info("查询 Dremio 中的所有数据源...")
        sources: list[DremioSource] = []
        for container in self.list_containers():
            sources.extend(self.query_source_tables(container.path))
        return sources
