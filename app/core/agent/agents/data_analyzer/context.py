import contextlib
import dataclasses
import functools
import threading
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, cast

import anyio
import anyio.to_thread
from langchain_core.runnables import Runnable, RunnableConfig, ensure_config
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.schemas import format_sources_overview
from app.core.agent.sources import Sources
from app.core.agent.tools import analyzer_tool, dataframe_tools, scikit_tools, sources_tools
from app.core.chain.llm import get_chat_model_async, get_llm_async
from app.core.lifespan import Lifespan
from app.log import logger
from app.schemas.mcp import Connection
from app.schemas.session import AgentModelConfig, SessionID
from app.utils import escape_tag

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langchain_mcp_adapters.sessions import Connection as LangChainMCPConnection


def get_runnable_config() -> RunnableConfig:
    """获取默认的 Runnable 配置"""
    return ensure_config({"recursion_limit": 200, "configurable": {"thread_id": threading.get_ident()}})


@dataclasses.dataclass
class AgentContext:
    session_id: SessionID
    sources: Sources
    model_config: AgentModelConfig
    mcp_connections: list[Connection] | None
    pre_model_hook: Runnable | None
    lifespan: Lifespan | None = None

    # private
    _graph: CompiledStateGraph | None = None
    _saved_models: dict[str, Path] | None = None

    @functools.cached_property
    def runnable_config(self) -> RunnableConfig:
        return ensure_config({"recursion_limit": 200, "configurable": {"thread_id": threading.get_ident()}})

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("Agent graph has not been built yet. Call `build_graph` first.")
        return self._graph

    @property
    def saved_models(self) -> dict[str, Path]:
        if self._saved_models is None:
            raise RuntimeError("Agent graph has not been built yet. Call `build_graph` first.")
        return self._saved_models

    async def build_graph(self) -> None:
        if self.lifespan is not None:
            with contextlib.suppress(BaseException):
                await self.lifespan.shutdown()
            self.lifespan = None

        self.lifespan = Lifespan(f"Agent<white>[<c>{escape_tag(self.session_id)}</>]</>")
        await self.lifespan.startup()

        # Builtin Tools
        analyzer = analyzer_tool(self.sources, await get_llm_async(self.model_config.code_generation))
        df_tools = dataframe_tools(self.sources)
        sk_tools, self._saved_models = scikit_tools(self.sources, self.session_id)
        sc_tools = sources_tools(self.sources)
        builtin_tools = [analyzer, *df_tools, *sk_tools, *sc_tools]

        # MCP Tools
        mcp_tools: list[BaseTool] = []
        if self.mcp_connections is not None:
            for connection in self.mcp_connections:
                conn = cast("LangChainMCPConnection", deepcopy(connection))
                mcp_tools.extend(await load_mcp_tools(None, connection=conn))

        # All Tools
        all_tools = builtin_tools + mcp_tools

        # Prompt
        system_prompt = PROMPTS.system.format(
            overview=format_sources_overview(self.sources.sources),
            tool_intro=PROMPTS.tool_intro,
        )

        # Create Agent
        _fn = functools.partial(
            create_react_agent,
            model=await get_chat_model_async(self.model_config.chat),
            tools=all_tools,
            prompt=system_prompt,
            checkpointer=InMemorySaver(),
            pre_model_hook=self.pre_model_hook,
        )
        self._graph = await anyio.to_thread.run_sync(_fn)
        logger.opt(colors=True).info(
            f"创建数据分析 Agent: <c>{self.session_id}</>, 使用工具数: <y>{len(builtin_tools)}</>"
            + (f", MCP 工具数: <y>{len(mcp_tools)}</>" if mcp_tools else "")
        )
