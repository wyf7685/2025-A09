from collections.abc import Sequence
from typing import cast

import anyio
from langchain_mcp_adapters.sessions import Connection as LangChainMCPConnection
from langchain_mcp_adapters.sessions import create_session
from pydantic import TypeAdapter

from app.const import DATA_DIR
from app.core.lifespan import lifespan
from app.exception import MCPServerAlreadyExists, MCPServerConnectionError, MCPServerNotFound
from app.log import logger
from app.schemas.mcp import Connection, MCPConnection

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
            raise MCPServerAlreadyExists(connection.id)

        try:
            async with create_session(cast("LangChainMCPConnection", connection.connection)) as session:
                await session.initialize()
                await session.send_ping()
        except Exception as e:
            logger.opt(exception=True).warning(f"连接到 MCP 服务器 {connection.id} 失败")
            raise MCPServerConnectionError(connection.id, e) from e

        self.servers[connection.id] = connection
        await self.save()

    async def delete(self, id: str) -> None:
        if id not in self.servers:
            raise MCPServerNotFound(id)
        del self.servers[id]
        await self.save()

    def all(self) -> dict[str, MCPConnection]:
        """Get all registered MCP servers."""
        return self.servers

    def get(self, id: str) -> MCPConnection:
        """Get a specific MCP server by ID."""
        if id not in self.servers:
            raise MCPServerNotFound(id)
        return self.servers[id]

    def gets(self, *ids: str) -> Sequence[MCPConnection]:
        """Get multiple MCP servers by IDs."""
        return [self.get(id) for id in ids]

    def get_all(self) -> Sequence[MCPConnection]:
        """Get all registered MCP servers."""
        return list(self.servers.values())

    async def test_connection(self, connection: Connection) -> tuple[str, str | None]:
        """Test connection to an MCP server."""
        try:
            async with create_session(cast("LangChainMCPConnection", connection)) as session:
                init_resp = await session.initialize()
                await session.send_ping()
            impl = init_resp.serverInfo
            title = impl.title or impl.name
            description = init_resp.instructions
            return title, description
        except Exception as e:
            logger.opt(exception=True).warning("测试连接到 MCP 服务器失败")
            raise MCPServerConnectionError("", e) from e


mcp_service = MCPService()
