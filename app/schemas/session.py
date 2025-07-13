from datetime import datetime

from pydantic import BaseModel, Field

from .chat import ChatEntry


class Session(BaseModel):
    id: str
    dataset_id: str
    name: str | None = None
    chat_history: list[ChatEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class SessionListItem(BaseModel):
    id: str
    name: str
    created_at: str
    chat_count: int
