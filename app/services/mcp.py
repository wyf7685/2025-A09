from collections.abc import Sequence
from typing import overload

import anyio
from pydantic import TypeAdapter

from app.const import DATA_DIR
from app.core.lifespan import lifespan
from app.schemas.mcp import MCPConnection

_mcp_servers_ta = TypeAdapter(dict[str, MCPConnection])
_MCP_SERVERS_FILE = anyio.Path(DATA_DIR / "mcp_servers.json")


class MCPService:
    def __init__(self) -> None:
        self.servers: dict[str, MCPConnection] = {}

        lifespan.on_startup(self.load)
        lifespan.on_shutdown(self.save)

    async def save(self) -> None:
        await _MCP_SERVERS_FILE.write_bytes(_mcp_servers_ta.dump_json(self.servers))

    async def load(self) -> None:
        if await _MCP_SERVERS_FILE.exists():
            self.servers = _mcp_servers_ta.validate_json(await _MCP_SERVERS_FILE.read_bytes())
        else:
            self.servers = {}

    async def register(self, connection: MCPConnection) -> None:
        if connection.id in self.servers:
            raise ValueError(f"MCP Server with id '{connection.id}' already exists.")
        self.servers[connection.id] = connection
        await self.save()

    async def delete(self, id: str) -> None:
        if id not in self.servers:
            raise ValueError(f"MCP Server with id '{id}' does not exist.")
        del self.servers[id]
        await self.save()

    def all(self) -> dict[str, MCPConnection]:
        """Get all registered MCP servers."""
        return self.servers

    @overload
    def get(self, /) -> Sequence[MCPConnection]: ...
    @overload
    def get(self, id: str, /) -> MCPConnection: ...
    @overload
    def get(self, id1: str, id2: str, /, *ids: str) -> Sequence[MCPConnection]: ...

    def get(self, *ids: str) -> MCPConnection | Sequence[MCPConnection]:
        """Get a specific MCP server by ID."""
        if not ids:
            return list(self.servers.values())
        for id in ids:
            if id not in self.servers:
                raise ValueError(f"MCP Server with ID '{id}' does not exist.")
        conns = [self.servers[id] for id in ids]
        return conns[0] if len(conns) == 1 else conns


mcp_service = MCPService()
