import uuid
from collections.abc import Iterable

import pandas as pd

from app.core.agent.schemas import DatasetID, SourcesDict
from app.core.datasource import DataSource, create_df_source
from app.log import logger
from app.utils import escape_tag


class Sources:
    def __init__(self, sources: SourcesDict) -> None:
        self.sources = sources

    def exists(self, dataset_id: DatasetID) -> bool:
        return dataset_id in self.sources

    def get(self, dataset_id: DatasetID) -> DataSource:
        if not self.exists(dataset_id):
            raise KeyError(f"数据源 {dataset_id} 不存在")
        return self.sources[dataset_id]

    def read(self, dataset_id: DatasetID) -> pd.DataFrame:
        logger.opt(colors=True).info(f"读取数据源: <c>{escape_tag(dataset_id)}</>")
        return self.get(dataset_id).get_full()

    def create(self, df: pd.DataFrame, new_id: DatasetID | None = None) -> DatasetID:
        dataset_id = new_id if new_id is not None else str(uuid.uuid4())
        self.sources[dataset_id] = create_df_source(df, dataset_id)
        logger.opt(colors=True).info(f"创建数据源: <c>{escape_tag(dataset_id)}</>")
        return dataset_id

    def rename(self, old_id: DatasetID, new_id: DatasetID) -> None:
        if old_id not in self.sources:
            raise KeyError(f"旧数据源 {old_id} 不存在")
        if old_id == new_id:
            return
        self.sources[new_id] = self.sources.pop(old_id)
        logger.opt(colors=True).info(f"重命名数据源: <c>{escape_tag(old_id)}</> -> <c>{escape_tag(new_id)}</>")

    def items(self) -> Iterable[tuple[DatasetID, DataSource]]:
        return self.sources.items()
