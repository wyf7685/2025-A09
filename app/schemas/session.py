from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field

from .chat import ChatEntry
from .custom_model import LLModelID

type SessionID = str


class AgentModelConfigFixed(BaseModel):
    default: LLModelID
    chat: LLModelID
    create_title: LLModelID
    summary: LLModelID
    code_generation: LLModelID


class AgentModelConfig(BaseModel):
    default: LLModelID
    chat: LLModelID | None = None
    create_title: LLModelID | None = None
    summary: LLModelID | None = None
    code_generation: LLModelID | None = None

    @classmethod
    def default_config(cls) -> Self:
        from app.services.custom_model import custom_model_manager

        first_model_id = custom_model_manager.select_first_model_id()
        if first_model_id is None:
            raise ValueError("没有可用的模型，请先添加自定义模型")
        return cls(default=first_model_id)

    @property
    def hash(self) -> int:
        return hash("$".join(f"{name}:{getattr(self, name)}" for name in sorted(type(self).model_fields)))

    @property
    def fixed(self) -> AgentModelConfigFixed:
        return AgentModelConfigFixed(
            default=self.default,
            chat=self.chat or self.default,
            create_title=self.create_title or self.default,
            summary=self.summary or self.default,
            code_generation=self.code_generation or self.default,
        )


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
