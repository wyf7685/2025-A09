from pathlib import Path
from typing import NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from pydantic import BaseModel, Field


class AgentValues(TypedDict):
    messages: NotRequired[list[AnyMessage]]


class WorkflowCallMeta(BaseModel):
    random_state: int
    mapping: dict[str, str]


class WorkflowData(BaseModel):
    call_meta: dict[str, WorkflowCallMeta] = Field(default_factory=dict)
    tool_calls: dict[str, str] = Field(default_factory=dict)  # tool_call_id -> call_meta_id


class DataAnalyzerAgentState(BaseModel):
    values: AgentValues
    models: dict[str, Path]
    sources_random_state: int
    workflow_data: WorkflowData = Field(default_factory=WorkflowData)

    def colorize(self) -> str:
        return (
            f"消息数=<y>{len(self.values.get('messages', []))}</>, "
            f"模型数=<y>{len(self.models)}</>, "
            f"随机状态=<y>{self.sources_random_state}</>"
        )


