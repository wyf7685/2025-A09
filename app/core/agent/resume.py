import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, overload

from langchain_core.messages import ToolCall

from app.log import logger

type ResumeCall = Callable[..., object]


@dataclass
class ResumableTool:
    name: str
    fn: ResumeCall
    params: list[str]


_RESUME_TOOL_REGISTRY: dict[str, ResumableTool] = {}


@overload
def resumable[C: ResumeCall](name: str, /) -> Callable[[C], C]: ...
@overload
def resumable[C: ResumeCall](fn: C, /) -> C: ...
@overload
def resumable[C: ResumeCall](tool_name: str, fn: C, /) -> C: ...


def resumable(
    name: str | ResumeCall, fn: ResumeCall | None = None, /
) -> Callable[[ResumeCall], ResumeCall] | ResumeCall:
    """
    装饰器，用于注册可恢复的工具函数
    """
    if isinstance(name, str):
        tool_name = name
    else:
        tool_name = name.__name__
        fn = name

    def decorator(fn: ResumeCall) -> ResumeCall:
        tool = ResumableTool(name=tool_name, fn=fn, params=list(inspect.signature(fn).parameters))
        _RESUME_TOOL_REGISTRY[tool_name] = tool
        return fn

    return decorator if fn is None else decorator(fn)


def is_resumable_tool(name: str) -> bool:
    return name in _RESUME_TOOL_REGISTRY


def get_resumable_tools() -> list[str]:
    """获取所有已注册的可恢复工具名称"""
    return list(_RESUME_TOOL_REGISTRY.keys())


def resume_tool_call(tool_call: ToolCall, extra: dict[str, Any]) -> Any:
    """
    恢复工具调用

    参数:
        tool_call: 工具调用对象或字典
        extra: 额外参数

    返回:
        工具执行结果
    """
    # 获取工具名称
    name = tool_call["name"]

    # 尝试直接匹配
    if r := _RESUME_TOOL_REGISTRY.get(name):
        logger.info(f"找到直接匹配的工具: {name}")
        args = {**tool_call["args"], **extra} if isinstance(tool_call, dict) else {**tool_call.args, **extra}
        return r.fn(**{k: v for k, v in args.items() if k in r.params})

    raise ValueError(f"工具 '{name}' 未在可恢复工具注册表中找到。已注册的工具: {list(_RESUME_TOOL_REGISTRY)}")
