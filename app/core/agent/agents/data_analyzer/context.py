from __future__ import annotations

import contextlib
import dataclasses
import functools
import threading
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

import anyio
import anyio.to_thread
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import _list_all_tools, convert_mcp_tool_to_langchain_tool
from mcp.types import Implementation as MCPImplementation

from app.const import STATE_DIR, VERSION
from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.schemas import format_sources_overview
from app.core.agent.tools import analyzer_tool, dataframe_tools, scikit_tools, sources_tools
from app.core.agent.tools._registry import register_tool_name
from app.core.chain import get_chat_model_async, get_llm
from app.core.lifespan import Lifespan
from app.log import logger
from app.schemas.session import AgentModelConfig, AgentModelConfigFixed, SessionID
from app.utils import escape_tag

if TYPE_CHECKING:
    from pathlib import Path

    from langchain_core.language_models import LanguageModelInput
    from langchain_core.runnables import Runnable, RunnableConfig
    from langchain_core.tools import BaseTool
    from langchain_mcp_adapters.sessions import Connection as LangChainMCPConnection
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.prebuilt import ToolNode

    from app.core.agent.sources import Sources
    from app.schemas.mcp import Connection
    from app.schemas.ml_model import MLModelInfo


@dataclasses.dataclass
class AgentContext:
    session_id: SessionID
    sources: Sources
    mcp_connections: list[tuple[str, Connection]] | None
    pre_model_hook: Runnable | None
    lifespan: Lifespan | None = None

    # private
    _tool_node: ToolNode | None = None
    _graph: CompiledStateGraph | None = None
    _saved_models: dict[str, Path] | None = None
    _mcp_instructions: str | None = None
    _tool_sources: dict[str, str] = dataclasses.field(default_factory=dict)

    @functools.cached_property
    def runnable_config(self) -> RunnableConfig:
        from langchain_core.runnables import ensure_config

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

    @property
    def tool_sources(self) -> dict[str, str]:
        return self._tool_sources.copy()

    @property
    def state_file(self) -> Path:
        return STATE_DIR / f"{self.session_id}.json"

    def lookup_tool_source(self, tool_name: str) -> str | None:
        return self._tool_sources.get(tool_name)

    async def get_model_config(self) -> AgentModelConfigFixed:
        from app.services.session import session_service

        if (session := await session_service.get(self.session_id)) is None:
            return AgentModelConfig.default_config().fixed

        return session.agent_model_config.model_copy().fixed

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

    async def _load_builtin_tools(self) -> list[BaseTool]:
        model_config = await self.get_model_config()
        analyzer = analyzer_tool(self.sources, lambda: get_llm(model_config.code_generation))
        df_tools = dataframe_tools(self.sources)
        sk_tools, self._saved_models = scikit_tools(self.sources, self.session_id)
        await self._load_saved_models()
        sc_tools = sources_tools(self.sources)
        builtin_tools = [analyzer, *df_tools, *sk_tools, *sc_tools]

        for tool in builtin_tools:
            self._tool_sources[tool.name] = "内置工具"
        return builtin_tools

    async def _load_mcp_tools(self) -> list[BaseTool]:
        if self.mcp_connections is None:
            self._mcp_instructions = ""
            return []

        assert self.lifespan is not None
        from app.services.agent import daa_service

        async def delete_mcp_source_tokens() -> None:
            for token in tokens:
                daa_service.delete_source_token(token)

        instructions: list[str] = []
        mcp_tools: list[BaseTool] = []
        tokens: list[str] = []
        self.lifespan.on_shutdown(delete_mcp_source_tokens)

        for idx, (server_name, conn) in enumerate(self.mcp_connections, 1):
            token = daa_service.create_source_token(self.session_id)
            tokens.append(token)
            connection = cast("LangChainMCPConnection", deepcopy(conn))
            connection["session_kwargs"] = {"client_info": MCPImplementation(name=token, version=VERSION)}
            async with create_session(connection) as session:
                init = await session.initialize()
                tools = await _list_all_tools(session)
            instruction = PROMPTS.mcp_server.format(
                idx=idx,
                server_instructions=init.instructions or "无",
                tool_instructions="\n".join(
                    f"- {t.name}" + (f": {t.description}" if t.description else "") for t in tools
                ),
            )
            instructions.append(instruction)
            for mcp_tool in tools:
                lc_tool = convert_mcp_tool_to_langchain_tool(None, mcp_tool, connection=connection)
                self._tool_sources[lc_tool.name] = f"{server_name} (MCP)"
                if mcp_tool.title:
                    register_tool_name(lc_tool.name, mcp_tool.title)
                mcp_tools.append(lc_tool)

        self._mcp_instructions = PROMPTS.mcp_tools_instruction.format(server_list="\n\n".join(instructions))
        return mcp_tools

    def _handle_tool_errors(self, error: Exception) -> str:
        logger.exception("工具调用时发生错误")
        return f"工具调用错误: {error!r}\n请修复后重试。"

    async def build_graph(self) -> None:
        from langchain_core.runnables import RunnableLambda
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.prebuilt import ToolNode, create_react_agent

        if self.lifespan is not None:
            with contextlib.suppress(BaseException):
                await self.lifespan.shutdown()
            self.lifespan = None

        self.lifespan = Lifespan(f"Agent<white>[<c>{escape_tag(self.session_id)}</>]</>")
        await self.lifespan.startup()

        # Load Tools
        builtin_tools = await self._load_builtin_tools()
        mcp_tools = await self._load_mcp_tools()
        self._tool_node = ToolNode(builtin_tools + mcp_tools, handle_tool_errors=self._handle_tool_errors)

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
