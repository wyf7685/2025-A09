from collections.abc import Callable

TOOL_NAMES: dict[str, str] = {}


def register_tool_name(tool_name: str, human_repr: str) -> None:
    TOOL_NAMES[tool_name] = human_repr


def register_tool[T: Callable](human_repr: str) -> Callable[[T], T]:
    def decorator(func: T) -> T:
        register_tool_name(func.__name__, human_repr)
        return func

    return decorator


def tool_name_human_repr(name: str) -> str:
    return TOOL_NAMES.get(name, name)
