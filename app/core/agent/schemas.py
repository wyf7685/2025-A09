import contextlib
import dataclasses
from collections.abc import Generator, MutableMapping
from contextvars import Context
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, TypeGuard

from pydantic import BaseModel

from app.core.datasource import DataSource
from app.schemas.session import SessionID

if TYPE_CHECKING:
    from app.core.agent.sources import Sources
    from app.core.agent.tools.scikit.model import ModelInstanceInfo, TrainModelResult
    from app.schemas.session import AgentModelConfigFixed
else:
    Sources = ModelInstanceInfo = TrainModelResult = AgentModelConfigFixed = Any

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
    sources: Sources
    model_config: AgentModelConfigFixed
    model_instance_cache: dict[str, ModelInstanceInfo]
    train_model_cache: dict[str, TrainModelResult]
    saved_models: dict[str, Path]

    @classmethod
    def get(cls) -> "AgentRuntimeContext":
        from langgraph.runtime import get_runtime

        return get_runtime(AgentRuntimeContext).context

    @contextlib.contextmanager
    def set(self) -> Generator[Context]:
        from langchain_core.runnables import ensure_config
        from langchain_core.runnables.config import set_config_context
        from langgraph._internal._constants import CONF, CONFIG_KEY_RUNTIME
        from langgraph.runtime import DEFAULT_RUNTIME, Runtime

        config = ensure_config()
        parent_runtime: Runtime[Any] = config.get(CONF, {}).get(CONFIG_KEY_RUNTIME, DEFAULT_RUNTIME)
        runtime = parent_runtime.merge(Runtime(context=self))
        config.setdefault(CONF, {})[CONFIG_KEY_RUNTIME] = runtime

        with set_config_context(config) as ctx:
            yield ctx

    def copy_with(self, **overrides: Any) -> "AgentRuntimeContext":
        return dataclasses.replace(self, **overrides)
