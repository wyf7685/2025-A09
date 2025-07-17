import uuid
from collections.abc import Iterable

import pandas as pd

from app.core.agent.schemas import DatasetID, SourcesDict
from app.core.datasource import DataSource, create_df_source


class Sources:
    def __init__(self, sources: SourcesDict | None = None) -> None:
        self.sources = sources or {}

    def exists(self, dataset_id: DatasetID) -> bool:
        return dataset_id in self.sources

    def get(self, dataset_id: DatasetID) -> DataSource:
        if not self.exists(dataset_id):
            raise KeyError(f"数据源 {dataset_id} 不存在")
        return self.sources[dataset_id]

    def read(self, dataset_id: DatasetID) -> pd.DataFrame:
        return self.get(dataset_id).get_full()

    def create(self, df: pd.DataFrame, new_id: DatasetID | None = None) -> DatasetID:
        dataset_id = new_id if new_id is not None else str(uuid.uuid4())
        self.sources[dataset_id] = create_df_source(df, dataset_id)
        return dataset_id

    def rename(self, old_id: DatasetID, new_id: DatasetID) -> None:
        if old_id not in self.sources:
            raise KeyError(f"数据源 {old_id} 不存在")
        if new_id in self.sources:
            raise KeyError(f"数据源 {new_id} 已存在")
        self.sources[new_id] = self.sources.pop(old_id)

    def items(self) -> Iterable[tuple[DatasetID, DataSource]]:
        return self.sources.items()
