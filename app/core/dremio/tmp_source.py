# ruff: noqa: S113
from typing import TYPE_CHECKING, Literal, Self

import pandas as pd
import requests

if TYPE_CHECKING:
    from .rest import DremioClient


class TemporaryDataSource:
    """
    临时数据源，用于在 Dremio 中创建和删除临时数据源
    """

    def __init__(
        self,
        client: "DremioClient",
        type_: Literal["csv", "database"],
        source_name: list[str],
    ) -> None:
        self.client = client
        self.type_ = type_
        self.source_name = source_name

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self.type_ == "csv":
            (self.client.external_dir / self.source_name[1]).unlink(missing_ok=True)
            return

        url = f"{self.client.base_url}/api/v3/catalog/{self.source_name[0]}"
        response = requests.delete(url, headers=self.client.get_auth_header())
        response.raise_for_status()

    def read(self, limit: int | None = None, *, fetch_all: bool = False) -> pd.DataFrame:
        """
        读取临时数据源的数据

        Args:
            limit: 返回的行数限制
            fetch_all: 是否获取全部数据

        Returns:
            pandas.DataFrame: 数据源数据
        """
        return self.client.read_source(self.source_name, limit, fetch_all=fetch_all)

    def shape(self) -> tuple[int, int]:
        """
        获取临时数据源的形状（行数和列数）

        Returns:
            tuple[int, int]: (行数, 列数)
        """
        return self.client.shape(self.source_name)
