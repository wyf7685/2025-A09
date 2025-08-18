from collections.abc import Callable
from pathlib import Path
from typing import cast


class _PromptLoader:
    def __init__(self, file: str) -> None:
        self.__directory = Path(file).resolve().parent

    def __getattr__(self, name: str) -> str:
        fp = self.__directory / f"{name}.md"
        if not fp.exists():
            raise AttributeError(f"Prompt '{name}' not found in {self.__directory}")
        content = fp.read_text(encoding="utf-8")
        setattr(self, name, content)
        return content


def make_loader[T](file: str, /) -> Callable[[type[T]], T]:
    return lambda _: cast("T", _PromptLoader(file))
