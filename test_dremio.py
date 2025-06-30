import json
import shutil
import time
import uuid
from pathlib import Path

import pandas
import requests

DREMIO_HOST = "http://localhost:9047"  # Dremio REST API 地址
DREMIO_USER = "wyf7685"  # 登录 Dremio UI 的用户名
DREMIO_PASSWORD = "pass7685"  # 登录 Dremio UI 的密码

DREMIO_EXTERNAL_LOCAL_DIR = Path(__file__).parent / "external"
DREMIO_EXTERNAL_NAME = "external"  # 外部数据源名称


def get_temp_token() -> str:
    """
    获取临时 Token
    """
    login_url = f"{DREMIO_HOST}/apiv2/login"
    login_payload = {"userName": DREMIO_USER, "password": DREMIO_PASSWORD}
    headers = {"Content-Type": "application/json"}
    response = requests.post(login_url, headers=headers, data=json.dumps(login_payload))
    response.raise_for_status()
    return response.json()["token"]


def create_query_job(temp_token: str, sql_query: str) -> str:
    """
    使用临时 Token 创建查询任务
    """
    auth_header = {
        "Authorization": f"_dremio{temp_token}",
        "Content-Type": "application/json",
    }
    submit_url = f"{DREMIO_HOST}/api/v3/sql"
    sql_payload = {"sql": sql_query}

    response = requests.post(
        submit_url,
        headers=auth_header,
        data=json.dumps(sql_payload),
    )
    response.raise_for_status()
    return response.json()["id"]


def wait_for_job_completion(job_id: str, temp_token: str):
    """
    等待查询任务完成
    """
    auth_header = {
        "Authorization": f"_dremio{temp_token}",
        "Content-Type": "application/json",
    }
    job_status_url = f"{DREMIO_HOST}/api/v3/job/{job_id}"
    while True:
        response = requests.get(job_status_url, headers=auth_header)
        response.raise_for_status()
        job_status = response.json()
        if job_status["jobState"] == "COMPLETED":
            return job_status
        elif job_status["jobState"] in ["FAILED", "CANCELED", "INVALID"]:
            raise Exception(f"Query failed with state: {job_status['jobState']}")
        time.sleep(1)


def get_job_result(job_id: str, temp_token: str):
    """
    获取查询结果
    """
    auth_header = {
        "Authorization": f"_dremio{temp_token}",
        "Content-Type": "application/json",
    }
    result_url = f"{DREMIO_HOST}/api/v3/job/{job_id}/results"
    response = requests.get(result_url, headers=auth_header)
    response.raise_for_status()
    return response.json()


def execute_sql_query(temp_token: str, sql_query: str) -> dict:
    """
    使用临时 Token 执行 SQL 查询
    """
    job_id = create_query_job(temp_token, sql_query)
    print(f"查询提交成功，Job ID: {job_id}")

    job_status = wait_for_job_completion(job_id, temp_token)
    print("\n查询完成，状态:", job_status["jobState"])

    return get_job_result(job_id, temp_token)


def add_data_source_csv(temp_token: str, file: Path) -> str:
    """
    添加 CSV 数据源到 Dremio 外部目录
    """
    source_name = f"{uuid.uuid4()}.csv"
    shutil.copyfile(file, DREMIO_EXTERNAL_LOCAL_DIR / source_name)
    # source_name = "ec01299a-4853-4987-849c-6d0d8f2a960f.csv"

    # 设置 "external"."{source_name}" 的属性: 自动读取文件首行作为列名
    auth_header = {
        "Authorization": f"_dremio{temp_token}",
        "Content-Type": "application/json",
    }
    url = f"{DREMIO_HOST}/apiv2/source/{DREMIO_EXTERNAL_NAME}/file_format/{source_name}"
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

    response = requests.put(url, headers=auth_header, data=json.dumps(payload))
    response.raise_for_status()

    return source_name


def add_data_source_postgres(
    temp_token: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
) -> str:
    """
    添加 PostgreSQL 数据源到 Dremio
    """
    source_name = str(uuid.uuid4())
    auth_header = {
        "Authorization": f"_dremio{temp_token}",
        "Content-Type": "application/json",
    }
    url = f"{DREMIO_HOST}/api/v3/catalog"
    payload = {
        "entityType": "source",
        "name": source_name,
        "type": "POSTGRES",
        "config": {
            "hostname": host,
            "port": str(port),  # 确保端口是字符串类型
            "databaseName": database,
            "username": user,
            "password": password,
            # "encryptConnection": False,
            "maxIdleConns": 8,
            # "maxOpenConns": 100,
            # "sslMode": "disable",  # 根据数据库配置选择 'disable', 'allow', 'prefer', 'require', 'verify-ca', or 'verify-full'
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

    response = requests.post(url, headers=auth_header, data=json.dumps(payload))
    response.raise_for_status()
    return source_name


def query_source_tables(temp_token: str, source_name: str):
    """
    查询指定数据源的所有表
    """
    auth_header = {
        "Authorization": f"_dremio{temp_token}",
        "Content-Type": "application/json",
    }
    url = f"{DREMIO_HOST}/api/v3/catalog/by-path/{source_name}"
    print(f"查询数据源 {source_name} 的子项...")
    response = requests.get(url, headers=auth_header)
    response.raise_for_status()

    tables: list[list[str]] = []
    for child in response.json()["children"]:
        path: list[str] = child["path"]
        if child["type"] == "DATASET":
            tables.append(path)
        elif child["type"] == "CONTAINER" and child["containerType"] == "FOLDER":
            sub_tables = query_source_tables(temp_token, "/".join(path))
            tables.extend(sub_tables)

    return tables


def main():
    # try:
    #     print("正在获取临时 Token...")
    #     temp_token = get_temp_token()
    #     print("✅ 获取临时 Token 成功:", temp_token)

    #     print("正在添加 CSV 数据源到 Dremio 外部目录...")
    #     source_name = add_data_source_csv(temp_token, Path("test.csv"))

    #     sql_query = f'SELECT * FROM "external"."{source_name}" LIMIT 5'
    #     print(f"\n正在使用临时 Token 执行查询: {sql_query}")
    #     job_id = create_query_job(temp_token, sql_query)
    #     print(f"查询提交成功，Job ID: {job_id}")

    #     job_status = wait_for_job_completion(job_id, temp_token)
    #     print("\n查询完成，状态:", job_status["jobState"])

    #     results = get_job_result(job_id, temp_token)
    #     print("\n查询结果数据:")
    #     for row in results["rows"]:
    #         print(row)

    #     df = pandas.DataFrame(results["rows"])
    #     print("\n查询结果 DataFrame:")
    #     print(df)

    # except requests.exceptions.HTTPError as err:
    #     print(f"❌ 请求失败: {err.response.status_code}")
    #     print(f"错误信息: {err.response.text}")
    # except Exception as e:
    #     print(f"❌ 发生未知错误: {e}")

    try:
        print("正在获取临时 Token...")
        temp_token = get_temp_token()
        print("✅ 获取临时 Token 成功:", temp_token)

        print("正在添加 PostgreSQL 数据源到 Dremio...")
        # source_name = "48643fdf-8a4f-4d68-b0c4-17897563d377"
        source_name = add_data_source_postgres(
            temp_token,
            host="postgres",
            port=5432,
            database="database",
            user="user",
            password="password",
        )

        print(f"PostgreSQL 数据源添加成功，源名称: {source_name}")
        print("正在查询 PostgreSQL 数据源的所有表...")
        tables = query_source_tables(temp_token, source_name)
        print("查询到的表:")
        for table_path in tables:
            print(table_path)
            full_name = ".".join(f'"{part}"' for part in table_path)
            sql_query = f"SELECT * FROM {full_name} LIMIT 5"
            print(f"查询 SQL: {sql_query}")

            results = execute_sql_query(temp_token, sql_query)
            df = pandas.DataFrame(results["rows"])
            print("\n查询结果数据:")
            print(df)

    except requests.exceptions.HTTPError as err:
        print(f"❌ 请求失败: {err.response.status_code}")
        print(f"错误信息: {err.response.text}")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")


if __name__ == "__main__":
    main()
