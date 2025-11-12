from collections.abc import Callable
from typing import Any

from app.core.lifespan import lifespan

TOOL_NAMES: dict[str, str] = {}


def register_tool_name(tool_name: str, human_repr: str) -> None:
    TOOL_NAMES[tool_name] = human_repr


def register_tool[T: Callable](name: str) -> Callable[[T], T]:
    def decorator(func: T) -> T:
        register_tool_name(func.__name__, name)
        return func

    return decorator


def tool_name_human_repr(name: str) -> str:
    return TOOL_NAMES.get(name, name)


@lifespan.on_startup
def _() -> None:
    from .analyzer import analyzer_tool
    from .dataframe import dataframe_tools
    from .scikit import scikit_tools
    from .sources import sources_tools

    obj: Any = object()
    analyzer_tool(obj, obj)
    dataframe_tools(obj)
    scikit_tools(obj, obj)
    sources_tools(obj)
