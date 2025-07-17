from datetime import datetime

from pydantic import BaseModel, Field

from .chat import ChatEntry

type SessionID = str


class Session(BaseModel):
    id: SessionID
    dataset_ids: list[str]
    name: str | None = None
    chat_history: list[ChatEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SessionListItem(BaseModel):
    id: SessionID
    name: str
    created_at: str
    chat_count: int
