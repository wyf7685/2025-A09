from datetime import timedelta
from pathlib import Path
from typing import Any, Literal, TypedDict

from pydantic import BaseModel


class StdioConnection(TypedDict):
    transport: Literal["stdio"]
    command: str
    """The executable to run to start the server."""
    args: list[str]
    """Command line arguments to pass to the executable."""
    env: dict[str, str] | None
    """The environment to use when spawning the process."""
    cwd: str | Path | None
    """The working directory to use when spawning the process."""
    encoding: str
    """The text encoding used when sending/receiving messages to the server."""


class SSEConnection(TypedDict):
    transport: Literal["sse"]
    url: str
    """The URL of the SSE endpoint to connect to."""
    headers: dict[str, Any] | None
    """HTTP headers to send to the SSE endpoint"""
    timeout: float
    """HTTP timeout"""
    sse_read_timeout: float
    """SSE read timeout"""


class StreamableHttpConnection(TypedDict):
    transport: Literal["streamable_http"]
    url: str
    """The URL of the endpoint to connect to."""
    headers: dict[str, Any] | None
    """HTTP headers to send to the endpoint."""
    timeout: timedelta
    """HTTP timeout."""
    sse_read_timeout: timedelta
    """How long (in seconds) the client will wait for a new event before disconnecting.
    All other HTTP operations are controlled by `timeout`."""
    terminate_on_close: bool
    """Whether to terminate the session on close"""


class WebsocketConnection(TypedDict):
    transport: Literal["websocket"]
    url: str
    """The URL of the Websocket endpoint to connect to."""


Connection = StdioConnection | SSEConnection | StreamableHttpConnection | WebsocketConnection


class MCPConnection(BaseModel):
    id: str
    connection: Connection
    name: str
    description: str | None = None
