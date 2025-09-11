from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field

from .chat import ChatEntry
from .custom_model import LLModelID

type SessionID = str


class AgentModelConfig(BaseModel):
    default: LLModelID
    chat: LLModelID | None = None
    create_title: LLModelID | None = None
    summary: LLModelID | None = None
    code_generation: LLModelID | None = None

    @classmethod
    def default_config(cls) -> Self:
        from app.core.config import settings

        return cls(default=settings.TEST_MODEL_NAME)

    @property
    def hash(self) -> int:
        return hash("$".join(f"{name}:{getattr(self, name)}" for name in sorted(type(self).model_fields)))


class Session(BaseModel):
    id: SessionID
    dataset_ids: list[str] = Field(default_factory=list)
    mcp_ids: list[str] | None = Field(default=None)
    model_ids: list[str] | None = Field(default=None)  # 关联的ML模型ID列表
    name: str | None = Field(default=None)
    chat_history: list[ChatEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent_model_config: AgentModelConfig = Field(default_factory=AgentModelConfig.default_config)


class SessionListItem(BaseModel):
    id: SessionID
    name: str
    created_at: str
    chat_count: int
