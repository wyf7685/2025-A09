import anyio
from mcp.server import FastMCP

mcp = FastMCP(
    name="greet mcp server",
    instructions="提供一个简单的问候工具",
)


@mcp.tool(
    title="Greet a person",
    description="A simple tool to greet a person by their name.",
)
def greet(name: str) -> str:
    """
    Greet a person with their name.
    """
    return f"Hello, {name}!"


if __name__ == "__main__":
    anyio.run(mcp.run_sse_async)
