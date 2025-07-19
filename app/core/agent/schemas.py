from collections.abc import MutableMapping
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from pydantic import BaseModel

from app.core.datasource import DataSource


class AgentValues(TypedDict):
    messages: list[AnyMessage]


class DataAnalyzerAgentState(BaseModel):
    values: AgentValues
    models: dict[str, Path]


type DatasetID = str
type SourcesDict = MutableMapping[DatasetID, DataSource]


def format_sources_overview(sources: SourcesDict) -> str:
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
