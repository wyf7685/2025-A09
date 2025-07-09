import pandas as pd

from .source import DataSource


class PandasDataSource(DataSource):
    def __init__(self, data: pd.DataFrame) -> None:
        """
        初始化Pandas数据源。

        Args:
            data (pd.DataFrame): Pandas DataFrame对象。
        """
        self._full_data = data

    def _load(self, n_rows: int | None) -> pd.DataFrame:
        assert self._full_data is not None, "Data source is not initialized"
        if n_rows is None:
            return self._full_data
        return self._full_data.head(n_rows)
