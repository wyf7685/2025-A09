from pathlib import Path


class PromptLoader:
    def __init__(self, file: str) -> None:
        self.directory = Path(file).resolve().parent

    def __getattr__(self, name: str) -> str:
        fp = self.directory / f"{name}.md"
        if not fp.exists():
            raise AttributeError(f"Prompt '{name}' not found in {self.directory}")
        content = fp.read_text(encoding="utf-8")
        setattr(self, name, content)
        return content
