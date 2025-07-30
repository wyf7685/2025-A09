from collections.abc import Sequence

import anyio
from langchain_mcp_adapters.sessions import Connection
from pydantic import TypeAdapter

from app.const import DATA_DIR
from app.core.lifespan import lifespan

_mcp_servers_ta = TypeAdapter(dict[str, Connection])

_MCP_SERVERS_FILE = anyio.Path(DATA_DIR / "mcp_servers.json")


class MCPService:
    def __init__(self) -> None:
        self.servers: dict[str, Connection] = {}

    async def save(self) -> None:
        await _MCP_SERVERS_FILE.write_bytes(_mcp_servers_ta.dump_json(self.servers))

    async def load(self) -> None:
        if await _MCP_SERVERS_FILE.exists():
            self.servers = _mcp_servers_ta.validate_json(await _MCP_SERVERS_FILE.read_bytes())
        else:
            self.servers = {}

    async def register(self, name: str, connection: Connection) -> None:
        if name in self.servers:
            raise ValueError(f"Server with name '{name}' already exists.")
        self.servers[name] = connection
        await self.save()

    async def delete(self, name: str) -> None:
        if name not in self.servers:
            raise ValueError(f"Server with name '{name}' does not exist.")
        del self.servers[name]
        await self.save()

    def all(self) -> dict[str, Connection]:
        """Get all registered MCP servers."""
        return self.servers

    def get(self, *names: str) -> Sequence[Connection]:
        """Get a specific MCP server by name."""
        if not names:
            return list(self.servers.values())
        for name in names:
            if name not in self.servers:
                raise ValueError(f"Server with name '{name}' does not exist.")
        return [self.servers[name] for name in names]


mcp_service = MCPService()

lifespan.on_startup(mcp_service.load)
lifespan.on_shutdown(mcp_service.save)
