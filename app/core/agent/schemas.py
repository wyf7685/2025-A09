import dataclasses
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, TypeGuard

from langgraph.runtime import get_runtime
from pydantic import BaseModel

from app.core.datasource import DataSource
from app.schemas.session import SessionID

if TYPE_CHECKING:
    from app.core.agent.sources import Sources
    from app.core.agent.tools.scikit.model import ModelInstanceInfo, TrainModelResult
    from app.schemas.session import AgentModelConfigFixed
else:
    ModelInstanceInfo = TrainModelResult = Any

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
    return "\n\n".join(f"- 数据集ID: {source_id}\n{source.format_overview()}" for source_id, source in sources.items())


class OperationFailed(TypedDict):
    """操作失败的结果"""

    success: Literal[False]
    message: str  # 错误信息
    error_type: NotRequired[str]  # 错误类型


class OperationFailedModel(BaseModel):
    """操作失败的结果模型"""

    success: Literal[False] = False
    message: str  # 错误信息
    error_type: str | None = None  # 错误类型

    @classmethod
    def from_err(cls, err: Exception) -> "OperationFailedModel":
        """从异常创建操作失败模型"""
        return cls(message=str(err), error_type=type(err).__name__)


class _Checkable(Protocol):
    success: Literal[True]


def is_failed(result: _Checkable | OperationFailedModel, /) -> TypeGuard[OperationFailedModel]:
    return not result.success


def is_success[T: _Checkable](result: T | OperationFailedModel, /) -> TypeGuard[T]:
    return result.success


@dataclasses.dataclass
class AgentRuntimeContext:
    session_id: SessionID

    if TYPE_CHECKING:
        sources: Sources
        model_config: AgentModelConfigFixed

    else:
        sources: Any
        model_config: Any

    model_instance_cache: dict[str, ModelInstanceInfo]
    train_model_cache: dict[str, TrainModelResult]
    saved_models: dict[str, Path]

    @classmethod
    def get(cls) -> "AgentRuntimeContext":
        return get_runtime(AgentRuntimeContext).context
