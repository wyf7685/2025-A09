# ruff: noqa: S608, S113

import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, override

import pandas as pd
import requests
from dremio import path_to_dotted

from app.core.config import settings
from app.log import logger
from app.schemas.dremio import BaseDatabaseConnection, DremioContainer, DremioDatabaseType, DremioSource
from app.utils import escape_tag

from ._cache import container_cache, source_cache
from .abstract import DREMIO_REST_FETCH_LIMIT, AbstractDremioClient


class DremioRestClient(AbstractDremioClient):
    """Dremio REST API 客户端"""

    def __init__(self) -> None:
        self.base_url = settings.DREMIO_REST_URL
        self.username = settings.DREMIO_USERNAME
        self.password = settings.DREMIO_PASSWORD.get_secret_value()
        self.external_dir = settings.DREMIO_EXTERNAL_DIR
        self.external_name = settings.DREMIO_EXTERNAL_NAME

        self.external_dir.mkdir(parents=True, exist_ok=True)
        self._token = None
        self._token_age = None

    def _get_token(self) -> str:
        """
        获取临时 Token，如果已存在则直接返回

        Returns:
            str: 认证 token
        """
        if self._token is None or (self._token_age and (datetime.now() - self._token_age).total_seconds() > 3600):
            self._token = self._get_temp_token()
            self._token_age = datetime.now()
        return self._token

    def _get_temp_token(self) -> str:
        """
        获取临时 Token

        Returns:
            str: 认证 token
        """
        response = self._request(
            "POST",
            "/apiv2/login",
            json={"userName": self.username, "password": self.password},
            with_auth=False,
        )
        return response.json()["token"]

    def get_auth_header(self) -> dict[str, str]:
        """
        获取认证头部

        Returns:
            dict[str, str]: 包含认证信息的请求头
        """

        return {
            "Authorization": f"_dremio{self._get_token()}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        path: str,
        *,
        with_auth: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        headers = self.get_auth_header() if with_auth else kwargs.pop("headers", {})
        url = str(self.base_url.with_path(path))
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def create_query_job(self, sql_query: str) -> str:
        """
        创建查询任务

        Args:
            sql_query: SQL 查询语句

        Returns:
            str: 查询任务 ID
        """
        response = self._request(
            "POST",
            "/api/v3/sql",
            json={"sql": sql_query},
        )
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
        while True:
            response = self._request("GET", f"/api/v3/job/{job_id}", with_auth=True)
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
        return self._request("GET", f"/api/v3/job/{job_id}/results", with_auth=True).json()

    def execute_sql_query(self, sql_query: str) -> dict[str, Any]:
        """
        执行 SQL 查询

        Args:
            sql_query: SQL 查询语句

        Returns:
            dict[str, Any]: 查询结果
        """
        job_id = self.create_query_job(sql_query)
        logger.opt(colors=True).info(f"查询提交成功: <c>{job_id}</>\n{escape_tag(sql_query)}")

        self.wait_for_job_completion(job_id)
        logger.opt(colors=True).success(f"查询完成: <c>{job_id}</>")

        return self.get_job_result(job_id)

    def execute_sql_to_dataframe(self, sql_query: str) -> pd.DataFrame:
        """
        执行 SQL 查询并返回 DataFrame

        Args:
            sql_query: SQL 查询语句

        Returns:
            pandas.DataFrame: 查询结果的 DataFrame
        """
        results = self.execute_sql_query(sql_query)
        return pd.DataFrame(results["rows"])

    @override
    def _add_data_source_csv(self, file: Path) -> DremioSource:
        """
        添加 CSV 数据源到 Dremio 外部目录

        Args:
            file: CSV 文件路径

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

        self._request(
            "PUT",
            f"/apiv2/source/{self.external_name}/file_format/{source_name}",
            json=payload,
        )

        source_cache.expire()
        return DremioSource(
            id=f"{self.external_name}.{source_name}",
            path=[self.external_name, source_name],
            type="FILE",
        )

    @override
    def _add_data_source_excel(self, file: Path) -> DremioSource:
        if self.external_dir is None:
            raise ValueError("外部数据源目录未设置")

        suffix = file.suffix.lower()
        if suffix not in {".xlsx", ".xls"}:
            suffix = ".xlsx"

        source_name = f"{uuid.uuid4()}{suffix}"
        shutil.copyfile(file, self.external_dir / source_name)

        # 设置 "external"."{source_name}" 的属性: 自动读取文件首行作为列名
        payload = {
            "extractHeader": True,
            "hasMergedCells": True,
            "type": "Excel",
        }
        self._request(
            "PUT",
            f"/apiv2/source/{self.external_name}/file_format/{source_name}",
            json=payload,
        )

        source_cache.expire()
        return DremioSource(
            id=f"{self.external_name}.{source_name}",
            path=[self.external_name, source_name],
            type="FILE",
        )

    @override
    def add_data_source_database(
        self,
        database_type: DremioDatabaseType,
        connection: BaseDatabaseConnection,
    ) -> DremioSource:
        payload = {
            "entityType": "source",
            "name": (source_name := str(uuid.uuid4())),
            "type": database_type,
            "config": {**connection.model_dump(), "port": str(connection.port)},
            "metadataPolicy": {
                "authTTLMs": 86400000,
                "datasetExpireAfterMs": 10800000,
                "namesRefreshMs": 3600000,
                "datasetUpdateMode": "PREFETCH_QUERIED",
                "deleteUnavailableDatasets": True,
                "autoPromoteDatasets": True,
            },
        }

        self._request("POST", "/api/v3/catalog", json=payload)
        container_cache.expire()
        return DremioSource(
            id=f"{source_name}",
            path=[source_name],
            type=database_type,
        )

    @override
    def read_source(
        self,
        source_name: str | list[str],
        limit: int | None = None,
        skip: int | None = None,
        *,
        max_workers: int = 10,
    ) -> pd.DataFrame:
        """
        读取数据源的数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制
            skip: 跳过的行数，为None表示不跳过
            max_workers: 分批查询时的最大线程数

        Returns:
            pandas.DataFrame: 数据源数据
        """
        source_name = path_to_dotted(source_name)
        skip = skip or 0

        if limit is not None and limit <= DREMIO_REST_FETCH_LIMIT:
            sql_query = f"SELECT * FROM {source_name} OFFSET {skip} ROWS FETCH NEXT {limit} ROWS ONLY"
            return self.execute_sql_to_dataframe(sql_query)

        try:
            # 首先获取计数
            count_query = f"SELECT COUNT(*) as row_count FROM {source_name}"
            count_df = self.execute_sql_to_dataframe(count_query)
            total_rows = int(count_df.iloc[0]["row_count"])
            logger.opt(colors=True).info(f"数据源 <c>{source_name}</> 中共有 <y>{total_rows}</> 条数据")

            total_rows = total_rows if limit is None else min(total_rows, limit)
            batch_ranges = (
                (offset, min(DREMIO_REST_FETCH_LIMIT, total_rows - offset))
                for offset in range(0, total_rows, DREMIO_REST_FETCH_LIMIT)
            )
            all_data: dict[int, pd.DataFrame] = {}

            def fetch(idx: int, offset: int, size: int) -> None:
                batch_query = f"SELECT * FROM {source_name} OFFSET {offset} ROWS FETCH NEXT {size} ROWS ONLY"
                logger.opt(colors=True).info(f"正在获取第 <y>{offset + 1}</>-<y>{offset + size}</> 条数据...")
                data = self.execute_sql_to_dataframe(batch_query)
                all_data[idx] = data

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, (offset, size) in enumerate(batch_ranges):
                    executor.submit(fetch, idx, skip + offset, size)

            if dfs := [all_data[idx] for idx in sorted(all_data.keys())]:
                result = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
                logger.opt(colors=True).info(f"通过分批查询共获取 <y>{len(result)}</> 条数据")
                return result

            return pd.DataFrame()

        except Exception:
            logger.exception("分批查询失败")

        logger.warning("警告: 无法获取全部数据，返回最多可获取的数据")
        return self.execute_sql_to_dataframe(
            f"SELECT * FROM {source_name} FETCH FIRST {DREMIO_REST_FETCH_LIMIT} ROWS ONLY"
        )

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
    def delete_data_source(self, source_path: list[str]) -> bool:
        """
        删除Dremio中的数据源

        Args:
            source_path: 数据源路径，例如 ["external", "filename.csv"]

        Returns:
            bool: 是否删除成功
        """
        try:
            # 尝试通过API删除数据源
            path_str = "/".join(source_path)
            self._request("DELETE", f"/api/v3/catalog/by-path/{path_str}")
            logger.info(f"成功从Dremio中删除数据源: {source_path}")

            # 清除缓存
            source_cache.expire()
            container_cache.expire()

            return True
        except Exception as e:
            logger.warning(f"从Dremio中删除数据源失败: {source_path}, 错误: {e}")
            # 即使API删除失败，也清除缓存，强制重新获取
            source_cache.expire()
            container_cache.expire()
            return False

    @override
    def refresh_external_source(self) -> bool:
        """
        刷新external数据源，让Dremio重新扫描external目录

        Returns:
            bool: 是否刷新成功
        """
        try:
            # 刷新external数据源
            self._request("POST", f"/api/v3/source/{self.external_name}/refresh")
            logger.info(f"成功刷新external数据源: {self.external_name}")

            # 清除缓存
            source_cache.expire()

            return True
        except Exception as e:
            logger.warning(f"刷新external数据源失败: {e}")
            # 即使刷新失败，也清除缓存
            source_cache.expire()
            container_cache.expire()
            return False

    def _list_containers(self) -> list[DremioContainer]:
        logger.info("查询 Dremio 中的所有容器...")
        if (cache := container_cache.get()) is not None:
            logger.info("使用缓存的容器列表")
            return cache

        response = self._request("GET", "/api/v3/catalog")
        containers = [
            DremioContainer(id=item["id"], path=item["path"])
            for item in response.json()["data"]
            if item["type"] == "CONTAINER" and item["containerType"] == "SOURCE"
        ]
        container_cache.set(containers, ttl=3600)
        logger.opt(colors=True).info(f"共找到 <y>{len(containers)}</> 个容器")
        return containers

    def _query_source_children(self, *paths: list[str]) -> list[DremioSource]:
        """
        查询指定数据源(数据库)的所有子项

        Args:
            paths: 数据源路径

        Returns:
            list[DremioSource]: 数据源子项列表
        """
        sources: list[DremioSource] = []

        def query(path: str | list[str]) -> None:
            colored = f"<c>{escape_tag(repr(path))}</>"
            logger.opt(colors=True).info(f"查询数据源 {colored} 的子项...")

            try:
                response = self._request("GET", f"/api/v3/catalog/by-path/{'/'.join(path)}")
            except Exception as e:
                logger.opt(colors=True).warning(f"查询数据源 {colored} 失败: {e}")
                return

            for child in response.json()["children"]:
                if child["type"] == "DATASET" and (ds_type := child.get("datasetType")):
                    sources.append(DremioSource(id=child["id"], path=child["path"], type=ds_type))
                elif child["type"] == "CONTAINER" and child["containerType"] == "FOLDER":
                    futures.append(executor.submit(query, child["path"]))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(query, path) for path in paths]
            while futures:
                fut = futures.pop(0)
                fut.result()

        return sources

    @override
    def list_sources(self) -> list[DremioSource]:
        logger.info("查询 Dremio 中的所有数据源...")
        if (cache := source_cache.get()) is not None:
            logger.info("使用缓存的数据源列表")
            return cache

        containers = self._list_containers()
        sources = self._query_source_children(*(c.path for c in containers))
        source_cache.set(sources, ttl=3600)
        logger.opt(colors=True).info(f"共找到 <y>{len(sources)}</> 个数据源")
        return sources
