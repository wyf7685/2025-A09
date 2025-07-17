import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, overload

from langchain_core.messages import ToolCall

type ResumeCall = Callable[..., object]


@dataclass
class ResumableTool:
    name: str
    fn: ResumeCall
    params: list[str]


_RESUME_TOOL_REGISTRY: dict[str, ResumableTool] = {}


@overload
def resumable[C: ResumeCall](tool_name: str, /) -> Callable[[C], C]: ...
@overload
def resumable[C: ResumeCall](tool_name: str, fn: C, /) -> C: ...


def resumable(tool_name: str, fn: ResumeCall | None = None, /) -> Callable[[ResumeCall], ResumeCall] | ResumeCall:
    """
    装饰器，用于注册可恢复的工具函数
    """

    def decorator(fn: ResumeCall) -> ResumeCall:
        _RESUME_TOOL_REGISTRY[tool_name] = ResumableTool(
            name=tool_name,
            fn=fn,
            params=list(inspect.signature(fn).parameters),
        )
        return fn

    return decorator if fn is None else decorator(fn)


def resume_tool_call(tool_call: ToolCall, extra: dict[str, Any]) -> None:
    """
    恢复工具调用
    """
    if r := _RESUME_TOOL_REGISTRY.get(tool_call["name"]):
        args = {**tool_call["args"], **extra}
        r.fn(**{k: v for k, v in args.items() if k in r.params})
