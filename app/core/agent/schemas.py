import uuid
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

import pandas as pd
from langchain_core.messages import AnyMessage
from pydantic import BaseModel

from app.core.datasource import DataSource, create_df_source


class AgentValues(TypedDict):
    messages: list[AnyMessage]


class DataAnalyzerAgentState(BaseModel):
    values: AgentValues
    models: dict[str, Path]


type DatasetID = str
type Sources = MutableMapping[DatasetID, DataSource]
type DatasetGetter = Callable[[DatasetID], pd.DataFrame]
type DatasetCreator = Callable[[pd.DataFrame], DatasetID]


def sources_fn(sources: Sources) -> tuple[DatasetGetter, DatasetCreator]:
    def get_df(dataset_id: DatasetID) -> pd.DataFrame:
        if dataset_id not in sources:
            raise ValueError(f"数据源 {dataset_id} 不存在")
        return sources[dataset_id].get_full()

    def create_df(df: pd.DataFrame) -> DatasetID:
        source_id = str(uuid.uuid4())
        sources[source_id] = create_df_source(df, source_id)
        return source_id

    return get_df, create_df


def format_sources_overview(sources: Sources) -> str:
    """
    格式化数据源的概览信息。

    Args:
        sources (Sources): 数据源字典，键为源ID，值为DataSource对象。

    Returns:
        str: 格式化后的概览信息。
    """
    return "\n\n".join(f"数据集ID: {source_id}\n{source.format_overview()}" for source_id, source in sources.items())


class OperationFailed(TypedDict):
    """操作失败的结果"""

    success: Literal[False]
    message: str  # 错误信息
    error_type: NotRequired[str]  # 错误类型
