from __future__ import annotations

import contextlib
import dataclasses
import functools
import operator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

import anyio
import anyio.lowlevel
import anyio.to_thread
from langchain_core.messages import BaseMessage, SystemMessage, ToolCall
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import _list_all_tools, convert_mcp_tool_to_langchain_tool
from langgraph.prebuilt import ToolNode
from mcp.types import Implementation as MCPImplementation

from app.const import STATE_DIR, VERSION
from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.schemas import AgentRuntimeContext, format_sources_overview
from app.core.agent.tools import builtin_tools
from app.core.agent.tools.registry import register_tool_name
from app.core.chain import get_chat_model_async
from app.core.lifespan import Lifespan
from app.log import logger
from app.schemas.session import AgentModelConfig, AgentModelConfigFixed, SessionID
from app.utils import escape_tag

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
    from pathlib import Path

    from langchain_core.language_models import LanguageModelInput
    from langchain_core.runnables import Runnable, RunnableConfig
    from langchain_core.tools import BaseTool
    from langchain_mcp_adapters.sessions import Connection as LangChainMCPConnection
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.prebuilt.chat_agent_executor import AgentState
    from langgraph.runtime import Runtime
    from langgraph.store.base import BaseStore

    from app.core.agent.sources import Sources
    from app.schemas.ml_model import MLModelInfo

    type AgentGraph = CompiledStateGraph[AgentState, AgentRuntimeContext, Any, Any]


def _handle_tool_errors(error: Exception) -> str:
    logger.exception("工具调用时发生错误")
    return f"工具调用错误: {error!r}\n请修复后重试。"


class AgentToolNode(ToolNode):
    def __init__(
        self,
        lifespan: Lifespan,
        tools: Sequence[BaseTool],
        load_extra_tools: Callable[[], Awaitable[Sequence[BaseTool]]],
        emit_tool_call: Callable[[ToolCall], object],
    ) -> None:
        super().__init__(
            tools,
            name="tools",
            handle_tool_errors=_handle_tool_errors,
            messages_key="messages",
        )
        self._lifespan = lifespan
        self._initial_tools = tools
        self._load_extra_tools = load_extra_tools
        self._emit_tool_call = emit_tool_call

    async def load_tools(self) -> None:
        extra_tools = await self._load_extra_tools()
        logger.opt(colors=True).info(f"加载额外工具数: <y>{len(extra_tools)}</>")
        for name in set(self.tools_by_name.keys()) - {tool.name for tool in self._initial_tools}:
            self.tools_by_name.pop(name, None)
            self.tool_to_state_args.pop(name, None)
            self.tool_to_store_arg.pop(name, None)
        for tool in extra_tools:
            self.tools_by_name[tool.name] = tool
            self.tool_to_state_args[tool.name] = {}
            self.tool_to_store_arg[tool.name] = None

    def _func(
        self,
        input: Any,
        config: RunnableConfig,
        *,
        store: BaseStore | None = None,
    ) -> Any:
        self._lifespan.from_thread(self.load_tools)
        for tc in self._parse_input(input, store)[0]:
            self._emit_tool_call(tc)
        return super()._func(input, config, store=store)

    async def _afunc(
        self,
        input: Any,
        config: RunnableConfig,
        *,
        store: BaseStore | None = None,
    ) -> Any:
        await self.load_tools()
        for tc in self._parse_input(input, store)[0]:
            self._emit_tool_call(tc)
        return await super()._afunc(input, config, store=store)


@dataclasses.dataclass
class AgentContext:
    session_id: SessionID
    sources: Sources
    pre_model_hook: Runnable | None
    lifespan: Lifespan | None = None
    saved_models: dict[str, Path] = dataclasses.field(default_factory=dict)

    # private
    _tool_node: ToolNode | None = None
    _graph: AgentGraph | None = None
    _mcp_instructions: str | None = None
    _tool_sources: dict[str, str] = dataclasses.field(default_factory=dict)
    _buffered_tool_calls: list[ToolCall] = dataclasses.field(default_factory=list)
    _model_instance_cache: dict[str, Any] = dataclasses.field(default_factory=dict)
    _train_model_cache: dict[str, Any] = dataclasses.field(default_factory=dict)
    _agent_source_tokens: set[str] = dataclasses.field(default_factory=set)
    _mcp_tool_cache: dict[str, list[BaseTool]] = dataclasses.field(default_factory=dict)

    @functools.cached_property
    def runnable_config(self) -> RunnableConfig:
        from langchain_core.runnables import ensure_config

        return ensure_config({"recursion_limit": 200, "configurable": {"thread_id": self.session_id}})

    @property
    def graph(self) -> AgentGraph:
        if self._graph is None:
            raise RuntimeError("Agent graph has not been built yet. Call `build_graph` first.")
        return self._graph

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
        await self._load_mcp_tools()
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

    async def _generate_model_prompt(self, state: AgentState) -> list[BaseMessage]:
        system_message = SystemMessage(content=await self._format_system_prompt())
        return [system_message, *state.get("messages", [])]

    async def _get_chat_model(
        self,
        _state: AgentState,
        runtime: Runtime[AgentRuntimeContext],
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        model = await get_chat_model_async(runtime.context.model_config.chat)
        if self._tool_node:
            model = model.bind_tools(list(self._tool_node.tools_by_name.values()))
        return model

    async def _delete_mcp_source_tokens(self) -> None:
        from app.services.agent import daa_service

        for token in self._agent_source_tokens:
            daa_service.delete_source_token(token)

    async def _load_mcp_tools(self) -> list[BaseTool]:
        from app.services.agent import daa_service
        from app.services.mcp import mcp_service
        from app.services.session import session_service

        if (chat_session := await session_service.get(self.session_id)) is None or (
            not (mcp_ids := set(chat_session.mcp_ids or []))
        ):
            self._mcp_instructions = ""
            return []

        cached_ids = set(self._mcp_tool_cache.keys())
        if mcp_ids == cached_ids:
            return functools.reduce(operator.add, self._mcp_tool_cache.values(), [])

        for mcp_id in cached_ids - mcp_ids:
            del self._mcp_tool_cache[mcp_id]

        mcps = {mcp_id: mcp_service.get(mcp_id) for mcp_id in mcp_ids}
        assert self.lifespan is not None

        instructions: list[str] = []
        mcp_tools: list[BaseTool] = []

        for idx, (mcp_id, mcp) in enumerate(mcps.items(), 1):
            token = daa_service.create_source_token(self.session_id)
            self._agent_source_tokens.add(token)
            connection = cast("LangChainMCPConnection", deepcopy(mcp.connection))
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
            lc_tools = []
            for mcp_tool in tools:
                lc_tool = convert_mcp_tool_to_langchain_tool(None, mcp_tool, connection=connection)
                self._tool_sources[lc_tool.name] = f"{mcp.name} (MCP)"
                if mcp_tool.title:
                    register_tool_name(lc_tool.name, mcp_tool.title)
                lc_tools.append(lc_tool)
            self._mcp_tool_cache[mcp_id] = lc_tools
            mcp_tools.extend(lc_tools)
            logger.opt(colors=True).info(
                f"从 MCP 服务器 <c>{escape_tag(mcp.name)}</> 加载工具数: <y>{len(lc_tools)}</>"
            )

        self._mcp_instructions = PROMPTS.mcp_tools_instruction.format(server_list="\n\n".join(instructions))
        return mcp_tools

    async def _build_tool_node(self, lifespan: Lifespan) -> ToolNode:
        # Load Tools
        await self._load_saved_models()
        tools = builtin_tools.copy()
        for tool in tools:
            self._tool_sources[tool.name] = "内置工具"

        self._tool_node = AgentToolNode(
            lifespan,
            tools,
            load_extra_tools=self._load_mcp_tools,
            emit_tool_call=self._buffered_tool_calls.append,
        )

        logger.opt(colors=True).info(f"使用工具数: <y>{len(builtin_tools)}</>")
        return self._tool_node

    async def flush_buffered_tool_calls(self) -> AsyncIterator[ToolCall]:
        while self._buffered_tool_calls:
            yield self._buffered_tool_calls.pop(0)
            await anyio.lowlevel.checkpoint()
        await anyio.lowlevel.checkpoint()

    async def build_graph(self) -> None:
        from langchain_core.runnables import RunnableLambda
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.prebuilt import create_react_agent

        if self.lifespan is not None:
            with contextlib.suppress(BaseException):
                await self.lifespan.shutdown()
            self.lifespan = None

        self.lifespan = Lifespan(f"Agent<white>[<c>{escape_tag(self.session_id)}</>]</>")
        await self.lifespan.startup()
        self.lifespan.on_shutdown(self._delete_mcp_source_tokens)

        # Load Tools
        tool_node = await self._build_tool_node(self.lifespan)

        # Prompt
        prompt = RunnableLambda(self._generate_model_prompt, name="Prompt")

        def build_graph() -> AgentGraph:
            graph = create_react_agent(
                model=self._get_chat_model,
                tools=tool_node,
                prompt=prompt,
                context_schema=AgentRuntimeContext,
                checkpointer=InMemorySaver(),
                pre_model_hook=self.pre_model_hook,
            )
            return cast("AgentGraph", graph)

        # Create Agent
        self._graph = await anyio.to_thread.run_sync(build_graph)
        logger.opt(colors=True).info(f"创建数据分析 Agent: <c>{self.session_id}</>")

    async def create_runtime_context(self) -> AgentRuntimeContext:
        return AgentRuntimeContext(
            session_id=self.session_id,
            sources=self.sources,
            model_config=await self.get_model_config(),
            saved_models=self.saved_models,
            model_instance_cache=self._model_instance_cache,
            train_model_cache=self._train_model_cache,
        )
