import contextlib
import dataclasses
import functools
import threading
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import anyio
import anyio.to_thread
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda, ensure_config
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import _list_all_tools, convert_mcp_tool_to_langchain_tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, create_react_agent

from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.schemas import format_sources_overview
from app.core.agent.sources import Sources
from app.core.agent.tools import analyzer_tool, dataframe_tools, scikit_tools, sources_tools
from app.core.chain.llm import get_chat_model_async, get_llm_async
from app.core.lifespan import Lifespan
from app.log import logger
from app.schemas.mcp import Connection
from app.schemas.ml_model import MLModelInfo
from app.schemas.session import AgentModelConfig, SessionID
from app.utils import escape_tag

if TYPE_CHECKING:
    from langchain_mcp_adapters.sessions import Connection as LangChainMCPConnection


def get_runnable_config() -> RunnableConfig:
    """获取默认的 Runnable 配置"""
    return ensure_config({"recursion_limit": 200, "configurable": {"thread_id": threading.get_ident()}})


@dataclasses.dataclass
class AgentContext:
    session_id: SessionID
    sources: Sources
    mcp_connections: list[Connection] | None
    pre_model_hook: Runnable | None
    lifespan: Lifespan | None = None

    # private
    _tool_node: ToolNode | None = None
    _graph: CompiledStateGraph | None = None
    _saved_models: dict[str, Path] | None = None
    _mcp_instructions: str | None = None

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

    async def get_model_config(self) -> AgentModelConfig:
        from app.services.session import session_service

        if (session := await session_service.get(self.session_id)) is None:
            return AgentModelConfig.default_config()

        config = session.agent_model_config.model_copy()
        for attr in ("chat", "create_title", "summary", "code_generation"):
            if getattr(config, attr) is None:
                setattr(config, attr, config.default)

        return config

    async def _load_external_models(self) -> list[MLModelInfo]:
        from app.services.model_registry import model_registry
        from app.services.session import session_service

        if (session := await session_service.get(self.session_id)) is None:
            return []

        return [
            model_info
            for model_id in (session.model_ids or [])
            if (model_info := model_registry.get_model(model_id)) is not None
        ]

    async def _load_saved_models(self) -> None:
        for model_info in await self._load_external_models():
            if model_info.model_path.exists():
                self.saved_models[model_info.id] = model_info.model_path

    async def _format_system_prompt(self) -> str:
        ml_model_instructions = ""
        if model_infos := await self._load_external_models():
            ml_model_instructions = PROMPTS.external_ml_model.format(
                model_list="\n".join(
                    f"- {model_info.name or model_info.type} (ID: {model_info.id})" for model_info in model_infos
                )
            )

        return PROMPTS.system.format(
            overview=format_sources_overview(self.sources.sources),
            tool_intro=PROMPTS.tool_intro,
            ml_model_instructions=ml_model_instructions,
            mcp_tools_instructions=self._mcp_instructions or "",
        )

    async def _generate_model_prompt(self, state: dict[str, Any]) -> list[BaseMessage]:
        system_message = SystemMessage(content=await self._format_system_prompt())
        return [system_message, *state.get("messages", [])]

    async def _get_chat_model(self, _state: object, _runtime: object) -> Runnable[LanguageModelInput, BaseMessage]:
        cfg = await self.get_model_config()
        model = await get_chat_model_async(cfg.chat)
        if self._tool_node:
            model = model.bind_tools(list(self._tool_node.tools_by_name.values()))
        return model

    async def _load_mcp_tools(self) -> list[BaseTool]:
        if self.mcp_connections is None:
            self._mcp_instructions = ""
            return []

        instructions: list[str] = []
        mcp_tools: list[BaseTool] = []
        for idx, connection in enumerate(self.mcp_connections, 1):
            conn = cast("LangChainMCPConnection", deepcopy(connection))
            async with create_session(conn) as tool_session:
                init = await tool_session.initialize()
                tools = await _list_all_tools(tool_session)
            instruction = PROMPTS.mcp_server.format(
                idx=idx,
                server_instructions=init.instructions or "无",
                tool_instructions="\n".join(
                    f"- {t.name}" + (f": {t.description}" if t.description else "") for t in tools
                ),
            )
            instructions.append(instruction)
            mcp_tools.extend(convert_mcp_tool_to_langchain_tool(None, tool, connection=conn) for tool in tools)

        self._mcp_instructions = PROMPTS.mcp_tools_instruction.format(server_list="\n".join(instructions))
        return mcp_tools

    async def build_graph(self) -> None:
        if self.lifespan is not None:
            with contextlib.suppress(BaseException):
                await self.lifespan.shutdown()
            self.lifespan = None

        self.lifespan = Lifespan(f"Agent<white>[<c>{escape_tag(self.session_id)}</>]</>")
        await self.lifespan.startup()

        # Builtin Tools
        model_config = await self.get_model_config()
        analyzer = analyzer_tool(self.sources, await get_llm_async(model_config.code_generation))
        df_tools = dataframe_tools(self.sources)
        sk_tools, self._saved_models = scikit_tools(self.sources, self.session_id)
        await self._load_saved_models()
        sc_tools = sources_tools(self.sources)
        builtin_tools = [analyzer, *df_tools, *sk_tools, *sc_tools]

        # MCP Tools
        mcp_tools = await self._load_mcp_tools()

        # All Tools
        self._tool_node = ToolNode(builtin_tools + mcp_tools)

        # Prompt
        prompt = RunnableLambda(
            self._generate_model_prompt,
            name="Prompt",
        )

        # Create Agent
        _fn = functools.partial(
            create_react_agent,
            model=self._get_chat_model,
            tools=self._tool_node,
            prompt=prompt,
            checkpointer=InMemorySaver(),
            pre_model_hook=self.pre_model_hook,
        )
        self._graph = await anyio.to_thread.run_sync(_fn)
        logger.opt(colors=True).info(
            f"创建数据分析 Agent: <c>{self.session_id}</>, 使用工具数: <y>{len(builtin_tools)}</>"
            + (f", MCP 工具数: <y>{len(mcp_tools)}</>" if mcp_tools else "")
        )
