from ._registry import TOOL_NAMES as TOOL_NAMES
from .analyzer import analyzer_tool as analyzer_tool
from .dataframe import dataframe_tools as dataframe_tools
from .scikit import scikit_tools as scikit_tools
from .sources import sources_tools as sources_tools


def __init() -> None:
    import typing

    obj: typing.Any = object()
    analyzer_tool(obj, obj)
    dataframe_tools(obj)
    scikit_tools(obj, obj)
    sources_tools(obj)


__init()
