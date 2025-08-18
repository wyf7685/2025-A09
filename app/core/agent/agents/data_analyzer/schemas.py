from pathlib import Path
from typing import NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from pydantic import BaseModel


class AgentValues(TypedDict):
    messages: NotRequired[list[AnyMessage]]


class DataAnalyzerAgentState(BaseModel):
    values: AgentValues
    models: dict[str, Path]
    sources_random_state: int

    def colorize(self) -> str:
        return (
            f"消息数=<y>{len(self.values.get('messages', []))}</>, "
            f"模型数=<y>{len(self.models)}</>, "
            f"随机状态=<y>{self.sources_random_state}</>"
        )
