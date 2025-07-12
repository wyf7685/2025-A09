import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.agent.events import StreamEvent


class UserChatMessage(BaseModel):
    type: str = "user"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class AssistantToolCallArtifact(BaseModel):
    type: Literal["image"] = "image"
    base64_data: str
    caption: str | None = None


class AssistantToolCall(BaseModel):
    name: str
    args: str
    status: Literal["running", "success", "error"]
    result: Any | None = None
    artifact: AssistantToolCallArtifact | None = None
    error: str | None = None


class AssistantChatMessageText(BaseModel):
    type: Literal["text"] = "text"
    content: str


class AssistantChatMessageToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str


type AssistantChatMessageContent = AssistantChatMessageText | AssistantChatMessageToolCall


class AssistantChatMessage(BaseModel):
    type: str = "assistant"
    content: list[AssistantChatMessageContent] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: dict[str, AssistantToolCall] = Field(default_factory=dict)


class ChatEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    user_message: UserChatMessage
    assistant_response: AssistantChatMessage = Field(default_factory=AssistantChatMessage)

    def push_stream_event(self, event: StreamEvent) -> None:
        resp = self.assistant_response
        match event.type:
            case "llm_token":
                resp.content.append(AssistantChatMessageText(content=event.content))
            case "tool_call":
                resp.content.append(AssistantChatMessageToolCall(id=event.id))
                if call := resp.tool_calls.get(event.id):
                    call.name = event.name
                    call.status = "running"
                    call.args = json.dumps(event.args)
                else:
                    resp.tool_calls[event.id] = AssistantToolCall(
                        name=event.name,
                        args=json.dumps(event.args),
                        status="running",
                    )
            case "tool_result" if call := (resp.tool_calls.get(event.id)):
                call.status = "success"
                call.result = event.result
                call.artifact = AssistantToolCallArtifact(**event.artifact) if event.artifact else None
            case "tool_error" if call := (resp.tool_calls.get(event.id)):
                call.status = "error"
                call.error = event.error
