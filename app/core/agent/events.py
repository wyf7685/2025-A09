import contextlib
import json
from collections.abc import AsyncIterable, Callable, Iterable
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from mcp.types import ImageContent
from pydantic import BaseModel, Field, Tag

from .tools._registry import tool_name_human_repr


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
    human_repr: str
    source: str | None = None
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


type StreamEvent = Annotated[
    Annotated[LlmTokenEvent, Tag("llm_token")]
    | Annotated[ToolCallEvent, Tag("tool_call")]
    | Annotated[ToolResultEvent, Tag("tool_result")]
    | Annotated[ToolErrorEvent, Tag("tool_error")],
    Field(discriminator="type"),
]


def fix_message_content(content: str | list[Any]) -> str:
    """修复消息内容，确保是字符串格式"""
    if isinstance(content, list):
        return "\n".join(str(item) for item in content)
    return str(content) if content else ""


def process_stream_event(
    message: BaseMessage,
    *,
    lookup_tool_source: Callable[[str], str | None] | None = None,
) -> Iterable[StreamEvent]:
    """处理从 stream/astream 方法返回的事件，将其转换为 StreamEvent 对象"""
    match message:
        case AIMessage(content=content, tool_calls=tool_calls):
            yield LlmTokenEvent(content=fix_message_content(content))
            for tool_call in tool_calls:
                if tool_call["id"] is None:
                    continue
                yield ToolCallEvent(
                    id=tool_call["id"],
                    name=tool_call["name"],
                    human_repr=tool_name_human_repr(tool_call["name"]),
                    source=lookup_tool_source and lookup_tool_source(tool_call["name"]),
                    args=tool_call["args"],
                )
        case ToolMessage(status="success", tool_call_id=tool_call_id, content=content, artifact=artifact):
            with contextlib.suppress(Exception):
                success = json.loads(fix_message_content(content))["success"]
                if not success:
                    yield ToolErrorEvent(id=tool_call_id, error=(str(content) or "Unknown error"))
                    return
            if isinstance(artifact, list):  # from MCP
                image = next((item for item in artifact if isinstance(item, ImageContent)), None)
                artifact = {"type": "image", "base64_data": image.data} if image else None
            yield ToolResultEvent(id=tool_call_id, result=content, artifact=artifact)
        case ToolMessage(status="error", content=content, tool_call_id=tool_call_id):
            yield ToolErrorEvent(id=tool_call_id, error=str(content))


class BufferedStreamEventReader:
    def __init__(self) -> None:
        self.tokens: list[LlmTokenEvent] = []

    def push(self, event: StreamEvent) -> Iterable[StreamEvent]:
        if isinstance(event, LlmTokenEvent):
            self.tokens.append(event)
        else:
            if msg := self.flush():
                yield msg
            yield event

    def flush(self) -> StreamEvent | None:
        if not self.tokens:
            return None

        content = "".join(event.content for event in self.tokens)
        if not content:
            return None

        metadata = {k: v for event in self.tokens for k, v in event.metadata.items()}
        self.tokens.clear()
        return LlmTokenEvent(content=content, metadata=metadata)

    def read(self, stream: Iterable[StreamEvent]) -> Iterable[StreamEvent]:
        for event in stream:
            yield from self.push(event)
        if msg := self.flush():
            yield msg

    async def aread(self, stream: AsyncIterable[StreamEvent]) -> AsyncIterable[StreamEvent]:
        async for event in stream:
            for e in self.push(event):
                yield e
        if msg := self.flush():
            yield msg
