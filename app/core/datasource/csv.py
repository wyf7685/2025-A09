from pathlib import Path
from typing import override

import pandas as pd

from .source import DataSource


class CsvDataSource(DataSource):
    def __init__(self, file_path: str | Path) -> None:
        """
        初始化CSV数据源。

        Args:
            file_path (str | Path): CSV文件的路径。
        """
        self.file_path = Path(file_path)

    @override
    def _load(self, n_rows: int | None) -> pd.DataFrame:
        if n_rows is None:
            return pd.read_csv(self.file_path)
        return pd.read_csv(self.file_path, nrows=n_rows)
