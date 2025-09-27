import io
import types
from dataclasses import dataclass
from typing import Any, Self

import httpx
import pandas as pd

API_BASE_URL = "http://localhost:8081/api"


@dataclass
class DataSourceInfo:
    """数据源信息"""

    id: str
    name: str
    source_type: str
    description: str
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] | None = None
    dtypes: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=data["id"],
            name=data["name"],
            source_type=data["source_type"],
            description=data["description"],
            row_count=data.get("row_count"),
            column_count=data.get("column_count"),
            columns=data.get("columns"),
            dtypes=data.get("dtypes"),
        )


class AsyncAgentSourceClient:
    """Agent 数据源异步客户端"""

    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def close(self) -> None:
        """关闭客户端连接"""
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.close()

    async def list_sources(self, session_id: str) -> list[DataSourceInfo]:
        """列出指定会话Agent中的所有可用数据源

        Args:
            session_id: 会话ID

        Returns:
            数据源信息列表
        """
        url = f"{self.base_url}/agent_source/list"
        params = {"session_id": session_id}

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        return [DataSourceInfo.from_dict(source) for source in data["sources"]]

    async def get_source_info(self, session_id: str, source_id: str) -> DataSourceInfo:
        """获取指定数据源的详细信息

        Args:
            session_id: 会话ID
            source_id: 数据源ID

        Returns:
            数据源详细信息
        """
        url = f"{self.base_url}/agent_source/info/{source_id}"
        params = {"session_id": session_id}

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        return DataSourceInfo.from_dict(response.json())

    async def read_source_data(self, session_id: str, source_id: str) -> pd.DataFrame:
        """读取指定数据源的数据（以pickle文件形式返回）

        Args:
            session_id: 会话ID
            source_id: 数据源ID

        Returns:
            DataFrame数据
        """
        url = f"{self.base_url}/agent_source/data/{source_id}"
        params = {"session_id": session_id}

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        pickle_data = response.content
        df = pd.read_pickle(io.BytesIO(pickle_data))  # noqa: S301
        assert isinstance(df, pd.DataFrame)
        return df

    async def create_source_from_dataframe(
        self,
        session_id: str,
        df: pd.DataFrame,
        new_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, str]:
        """在指定会话的Agent中创建新的数据源

        Args:
            session_id: 会话ID
            df: DataFrame数据
            new_id: 新数据源ID（可选）
            description: 数据源描述（可选）

        Returns:
            创建结果，包含dataset_id和message
        """
        url = f"{self.base_url}/agent_source/create"
        params = {"session_id": session_id}

        if new_id:
            params["new_id"] = new_id
        if description:
            params["description"] = description

        # 将DataFrame序列化为pickle
        buffer = io.BytesIO()
        df.to_pickle(buffer)
        buffer.seek(0)

        files = {"file": ("data.pkl", buffer.getvalue(), "application/octet-stream")}

        response = await self.client.post(url, params=params, files=files)
        response.raise_for_status()

        return response.json()


async def list_agent_sources(session_id: str) -> list[DataSourceInfo]:
    """列出Agent数据源"""
    async with AsyncAgentSourceClient() as client:
        return await client.list_sources(session_id)


async def get_agent_source_info(session_id: str, source_id: str) -> DataSourceInfo:
    """获取Agent数据源信息"""
    async with AsyncAgentSourceClient() as client:
        return await client.get_source_info(session_id, source_id)


async def read_agent_source_data(session_id: str, source_id: str) -> pd.DataFrame:
    """读取Agent数据源数据"""
    async with AsyncAgentSourceClient() as client:
        return await client.read_source_data(session_id, source_id)


async def create_agent_source(
    session_id: str,
    df: pd.DataFrame,
    new_id: str | None = None,
    description: str | None = None,
) -> str:
    """创建Agent数据源，返回数据源ID"""
    async with AsyncAgentSourceClient() as client:
        result = await client.create_source_from_dataframe(session_id, df, new_id, description)
        return result["dataset_id"]
