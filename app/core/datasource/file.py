from pathlib import Path
from typing import Any, override

import pandas as pd
from pydantic import BaseModel

from .source import DataSource, DataSourceMetadata


class CSVDataSourceModel(BaseModel):
    file_path: Path
    metadata: DataSourceMetadata
    pandas_kwargs: dict[str, Any] = {}


class FileDataSource(DataSource):
    """CSV/Excel 文件数据源实现"""

    def __init__(self, file_path: Path, metadata: DataSourceMetadata | None = None, **pandas_kwargs: Any) -> None:
        """
        初始化 CSV 数据源

        Args:
            file_path: CSV/Excel 文件路径
            metadata: 数据源元数据，如果为None则自动创建
            **pandas_kwargs: 传递给 read_csv/read_excel 的参数
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件 {file_path} 不存在")

        if file_path.suffix not in {".csv", ".xlsx", ".xls"}:
            raise ValueError(f"不支持的文件类型: {file_path.suffix}. 仅支持 .csv, .xlsx, .xls 文件")

        if metadata is None:
            # 创建基本元数据
            metadata = DataSourceMetadata(
                id=f"csv_{file_path.stem}",
                name=file_path.name,
                source_type="csv",
            )

        super().__init__(metadata)
        self.file_path = file_path
        self.pandas_kwargs = pandas_kwargs

    @override
    def _load(self, n_rows: int | None = None) -> pd.DataFrame:
        """加载 CSV 文件数据"""
        kwargs = self.pandas_kwargs.copy()
        if n_rows is not None:
            kwargs["nrows"] = n_rows

        return (pd.read_csv if self.file_path.suffix == ".csv" else pd.read_excel)(self.file_path, **kwargs)

    @override
    def _shape(self) -> tuple[int, int]:
        return self._load().shape

    @override
    def copy(self) -> "FileDataSource":
        return FileDataSource(file_path=self.file_path, metadata=self.metadata.model_copy(), **self.pandas_kwargs)

    @property
    @override
    def unique_id(self) -> str:
        return f"csv:{self.file_path.stem}"

    @override
    def serialize(self) -> tuple[str, dict[str, Any]]:
        """序列化 CSV 数据源"""
        return "csv", CSVDataSourceModel(
            file_path=self.file_path,
            metadata=self.metadata,
            pandas_kwargs=self.pandas_kwargs,
        ).model_dump(mode="json")

    @classmethod
    @override
    def deserialize(cls, data: dict[str, Any]) -> "FileDataSource":
        """反序列化 CSV 数据源"""
        model = CSVDataSourceModel.model_validate(data)
        return cls(file_path=Path(model.file_path), metadata=model.metadata, **model.pandas_kwargs)
