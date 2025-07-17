import contextlib
import json
from collections.abc import Iterable
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field


class LlmTokenEvent(BaseModel):
    """LLM 生成的单个 token"""

    type: Literal["llm_token"] = "llm_token"
    content: str
    metadata: dict = Field(default_factory=dict)


class ToolCallEvent(BaseModel):
    """工具调用事件"""

    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    args: dict = Field(default_factory=dict)


class ToolResultEvent(BaseModel):
    """工具调用结果"""

    type: Literal["tool_result"] = "tool_result"
    id: str
    result: Any
    artifact: dict | None = None


class ToolErrorEvent(BaseModel):
    """工具调用错误"""

    type: Literal["tool_error"] = "tool_error"
    id: str
    error: str


type StreamEvent = LlmTokenEvent | ToolCallEvent | ToolResultEvent | ToolErrorEvent


def fix_message_content(content: str | list[Any]) -> str:
    """修复消息内容，确保是字符串格式"""
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content) if content else ""


def process_stream_event(event: Any) -> Iterable[StreamEvent]:
    """处理从 stream/astream 方法返回的事件，将其转换为 StreamEvent 对象"""
    if not isinstance(event, tuple) or len(event) != 2:
        return

    message, metadata = event

    match message:
        case AIMessage():
            yield LlmTokenEvent(content=fix_message_content(message.content), metadata=metadata or {})
            for tool_call in message.tool_calls or []:
                if tool_call["id"] is None:
                    continue
                yield ToolCallEvent(name=tool_call["name"], id=tool_call["id"], args=tool_call["args"])
        case ToolMessage() if message.status == "success":
            with contextlib.suppress(Exception):
                success = json.loads(fix_message_content(message.content))["success"]
                if not success:
                    yield ToolErrorEvent(id=message.tool_call_id, error=(str(message.content) or "Unknown error"))
                    return
            yield ToolResultEvent(id=message.tool_call_id, result=message.content, artifact=message.artifact)
        case ToolMessage() if message.status == "error":
            yield ToolErrorEvent(id=message.tool_call_id, error=str(message.content))


class BufferedStreamEventReader:
    def __init__(self) -> None:
        self.tokens: list[LlmTokenEvent] = []

    def push(self, event: Any) -> Iterable[StreamEvent]:
        if isinstance(event, LlmTokenEvent):
            self.tokens.append(event)
        else:
            if msg := self.flush():
                yield msg
            yield event

    def flush(self) -> LlmTokenEvent | None:
        if not self.tokens:
            return None

        content = "".join(event.content for event in self.tokens)
        if not content:
            return None

        metadata = {k: v for event in self.tokens for k, v in event.metadata.items()}
        self.tokens.clear()
        return LlmTokenEvent(content=content, metadata=metadata)
