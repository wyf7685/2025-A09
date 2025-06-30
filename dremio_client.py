import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import pandas
import requests


class DremioClient:
    """Dremio REST API 客户端"""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        external_dir: Path | None = None,
        external_name: str = "external",
    ):
        """
        初始化 Dremio 客户端

        Args:
            base_url: Dremio REST API 地址
            username: 登录 Dremio UI 的用户名
            password: 登录 Dremio UI 的密码
            external_dir: 外部数据源本地目录路径
            external_name: 外部数据源名称
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.external_dir = external_dir
        self.external_name = external_name
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

    def _get_auth_header(self) -> dict[str, str]:
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
            headers=self._get_auth_header(),
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
            response = requests.get(job_status_url, headers=self._get_auth_header())
            response.raise_for_status()
            job_status = response.json()
            if job_status["jobState"] == "COMPLETED":
                return job_status
            elif job_status["jobState"] in ["FAILED", "CANCELED", "INVALID"]:
                raise Exception(f"Query failed with state: {job_status['jobState']}")
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
        response = requests.get(result_url, headers=self._get_auth_header())
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
        print(f"查询提交成功，Job ID: {job_id}")

        job_status = self.wait_for_job_completion(job_id)
        print("\n查询完成，状态:", job_status["jobState"])

        return self.get_job_result(job_id)

    def execute_sql_to_dataframe(self, sql_query: str) -> pandas.DataFrame:
        """
        执行 SQL 查询并返回 DataFrame

        Args:
            sql_query: SQL 查询语句
            token: 可选的认证 token

        Returns:
            pandas.DataFrame: 查询结果的 DataFrame
        """
        results = self.execute_sql_query(sql_query)
        return pandas.DataFrame(results["rows"])

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
            headers=self._get_auth_header(),
            data=json.dumps(payload),
        )
        response.raise_for_status()

        return [self.external_name, source_name]

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
            headers=self._get_auth_header(),
            data=json.dumps(payload),
        )
        response.raise_for_status()
        return source_name

    def query_source_tables(self, source_name: str) -> list[list[str]]:
        """
        查询指定数据源的所有表

        Args:
            source_name: 数据源名称

        Returns:
            list[list[str]]: 表路径列表
        """
        url = f"{self.base_url}/api/v3/catalog/by-path/{source_name}"
        print(f"查询数据源 {source_name} 的子项...")
        response = requests.get(url, headers=self._get_auth_header())
        response.raise_for_status()

        tables: list[list[str]] = []
        for child in response.json()["children"]:
            path: list[str] = child["path"]
            if child["type"] == "DATASET":
                tables.append(path)
            elif child["type"] == "CONTAINER" and child["containerType"] == "FOLDER":
                sub_tables = self.query_source_tables("/".join(path))
                tables.extend(sub_tables)

        return tables

    def peek_source(
        self, source_name: str | list[str], limit: int = 5
    ) -> pandas.DataFrame:
        """
        快速查看数据源的前几行数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制

        Returns:
            pandas.DataFrame: 数据源的前几行数据
        """
        source_name = self._format_source_name_table(source_name)
        sql_query = f"SELECT * FROM {source_name} LIMIT {limit}"
        return self.execute_sql_to_dataframe(sql_query)

    def read_source(
        self, source_name: str | list[str], limit: int | None = None
    ) -> pandas.DataFrame:
        """
        读取数据源的前几行数据

        Args:
            source_name: 数据源名称
            limit: 返回的行数限制

        Returns:
            pandas.DataFrame: 数据源的前几行数据
        """
        source_name = self._format_source_name_table(source_name)
        sql_query = f"SELECT * FROM {source_name}"
        if limit is not None:
            sql_query += f" LIMIT {limit}"
        return self.execute_sql_to_dataframe(sql_query)


if __name__ == "__main__":
    # 创建客户端
    client = DremioClient(
        base_url="http://localhost:9047",
        username="wyf7685",
        password="pass7685",
        # external_dir=Path(__file__).parent / "external",
        # external_name="external",
    )

    try:
        # 添加 PostgreSQL 数据源
        print("正在添加 PostgreSQL 数据源到 Dremio...")
        source_name = client.add_data_source_postgres(
            host="postgres",
            port=5432,
            database="database",
            user="user",
            password="password",
        )

        print(f"PostgreSQL 数据源添加成功，源名称: {source_name}")
        print("正在查询 PostgreSQL 数据源的所有表...")
        tables = client.query_source_tables(source_name)
        print("查询到的表:")
        for table_path in tables:
            print(table_path)
            full_name = ".".join(f'"{part}"' for part in table_path)
            sql_query = f"SELECT * FROM {full_name} LIMIT 5"
            print(f"查询 SQL: {sql_query}")

            df = client.execute_sql_to_dataframe(sql_query)
            print("\n查询结果数据:")
            print(df)

    except requests.exceptions.HTTPError as err:
        print(f"❌ 请求失败: {err.response.status_code}")
        print(f"错误信息: {err.response.text}")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
