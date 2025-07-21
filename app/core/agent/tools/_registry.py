from collections.abc import Callable

TOOL_NAMES: dict[str, str] = {}


def register_tool[T: Callable](name: str) -> Callable[[T], T]:
    def decorator(func: T) -> T:
        TOOL_NAMES[func.__name__] = name
        return func

    return decorator
