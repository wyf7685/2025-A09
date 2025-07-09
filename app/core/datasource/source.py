import abc

import pandas as pd


class DataSource(abc.ABC):
    _full_data: pd.DataFrame | None = None

    @abc.abstractmethod
    def _load(self, n_rows: int | None) -> pd.DataFrame:
        """
        加载数据源，返回一个DataFrame

        Args:
            n_rows (int | None): 读取的行数，为None表示读取全部数据

        Returns:
            pd.DataFrame: 数据源的DataFrame
        """

    def set_full_data(self, data: pd.DataFrame) -> None:
        """
        设置数据源的完整数据

        Args:
            data (pd.DataFrame): 数据源的完整数据
        """
        self._full_data = data

    def get_preview(self, n_rows: int = 5) -> pd.DataFrame:
        """
        获取数据源的预览数据，默认返回前5行

        Args:
            n_rows (int): 预览行数，默认为5行

        Returns:
            pd.DataFrame: 数据源的预览数据
        """
        if self._full_data is not None:
            return self._full_data.head(n_rows)
        return self._load(n_rows)

    def get_full(self) -> pd.DataFrame:
        """
        获取数据源的完整数据

        Returns:
            pd.DataFrame: 数据源的完整数据
        """
        if self._full_data is None:
            self._full_data = self._load(None)
        return self._full_data
