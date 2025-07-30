from collections.abc import Sequence

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

    def get(self, *ids: str) -> Sequence[MCPConnection]:
        """Get a specific MCP server by name."""
        if not ids:
            return list(self.servers.values())
        for id in ids:
            if id not in self.servers:
                raise ValueError(f"MCP Server with name '{id}' does not exist.")
        return [self.servers[name] for name in ids]


mcp_service = MCPService()

lifespan.on_startup(mcp_service.load)
lifespan.on_shutdown(mcp_service.save)
