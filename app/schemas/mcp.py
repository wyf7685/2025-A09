from langchain_mcp_adapters.sessions import Connection as Connection
from pydantic import BaseModel


class MCPConnection(BaseModel):
    id: str
    connection: Connection
    name: str
    description: str | None = None
