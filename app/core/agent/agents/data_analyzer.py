import contextlib
import functools
import itertools
import threading
from collections.abc import AsyncIterator, Iterable
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

import anyio
import anyio.to_thread
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig, ensure_config
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.core.agent.events import StreamEvent, fix_message_content, process_stream_event
from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.resume import resume_tool_call
from app.core.agent.schemas import AgentValues, DataAnalyzerAgentState, SourcesDict, format_sources_overview
from app.core.agent.sources import Sources
from app.core.agent.tools import analyzer_tool, dataframe_tools, scikit_tools, sources_tools
from app.core.chain.llm import LLM
from app.core.lifespan import Lifespan
from app.log import logger
from app.schemas.mcp import Connection
from app.schemas.session import SessionID
from app.utils import escape_tag

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from langchain_mcp_adapters.sessions import Connection as LangChainMCPConnection


def resume_tool_calls(sources: Sources, messages: list[AnyMessage]) -> None:
    for tool_call in itertools.chain.from_iterable(
        m.tool_calls for m in messages if isinstance(m, AIMessage) and m.tool_calls
    ):
        try:
            resume_tool_call(tool_call, {"sources": sources})
        except Exception as e:
            logger.opt(colors=True, exception=True).warning(
                f"恢复工具调用时出错: <y>{escape_tag(tool_call['name'])}</> - {escape_tag(str(e))}"
            )


def format_conversation(messages: list[AnyMessage], *, include_figures: bool) -> tuple[str, list[str]]:
    """格式化对话记录为字符串"""
    formatted: list[str] = []
    figures: list[str] = []
    for message in messages:
        match message:
            case HumanMessage(content=content):
                formatted.append(f"用户:\n<user-content>\n{content}\n</user-content>")
            case AIMessage(content=content, tool_calls=tool_calls):
                content = fix_message_content(content)
                formatted.append(f"AI:\n<ai-content>\n{content}\n</ai-content>")
                for tool_call in tool_calls:
                    if tool_call["id"] is None:
                        continue
                    formatted.append(
                        f"工具调用请求({tool_call['id']}): {tool_call['name']}\n"
                        f"<tool-call-args>\n{tool_call['args']!r}\n</tool-call-args>"
                    )
            case ToolMessage(tool_call_id=id, status=status, content=content, artifact=artifact):
                artifact_info = ""
                if (
                    include_figures
                    and isinstance(artifact, dict)
                    and artifact.get("type") == "image"
                    and (base64_data := artifact.get("base64_data")) is not None
                ):
                    artifact_info = f"[包含图片输出, ID={len(figures)}]\n"
                    figures.append(base64_data)
                formatted.append(
                    f"工具调用结果({id}): {status=}\n"
                    f"<tool-call-result>\n{content!r}\n{artifact_info}</tool-call-result>"
                )

    conversations = f"<conversation>\n{'\n'.join(formatted) if formatted else '无对话记录'}\n</conversation>"
    return conversations, figures


def _create_title_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[object, str]:
    conversation = format_conversation(messages, include_figures=False)[0]
    prompt = PROMPTS.create_title.format(conversation=conversation)
    return (lambda _: prompt) | llm


def _summary_chain(llm: LLM, messages: list[AnyMessage]) -> Runnable[str, tuple[str, list[str]]]:
    def prompt(report_template: str) -> str:
        return PROMPTS.summary.format(
            conversation=conversation,
            tool_intro=PROMPTS.tool_intro,
            report_template=report_template,
        )

    conversation, figures = format_conversation(messages, include_figures=True)
    return prompt | llm | (lambda s: (s, figures))


class DataAnalyzerAgent:
    sources: Sources
    llm: LLM
    chat_model: BaseChatModel
    session_id: SessionID
    mcp_connections: list[Connection] | None = None
    pre_model_hook: Runnable | None = None
    agent: CompiledStateGraph[Any, Any, Any]
    config: RunnableConfig
    saved_models: dict[str, Path]
    _lifespan: Lifespan | None = None

    def __init__(self) -> None:
        raise NotImplementedError("Use the `create` class method to instantiate this agent.")

    async def _create_graph(self) -> CompiledStateGraph[Any, Any, Any]:
        if self._lifespan is not None:
            with anyio.CancelScope(), contextlib.suppress(Exception):
                await self._lifespan.shutdown()
            self._lifespan = None

        self._lifespan = Lifespan(f"Agent<white>[<c>{escape_tag(self.session_id)}</>]</>")
        await self._lifespan.startup()

        # Builtin Tools
        analyzer = analyzer_tool(self.sources, self.llm)
        df_tools = dataframe_tools(self.sources)
        sk_tools, saved_models = scikit_tools(self.sources, self.session_id)
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
            model=self.chat_model,
            tools=all_tools,
            prompt=system_prompt,
            checkpointer=InMemorySaver(),
            pre_model_hook=self.pre_model_hook,
        )
        self.agent = await anyio.to_thread.run_sync(_fn)
        self.config = ensure_config({"recursion_limit": 200, "configurable": {"thread_id": threading.get_ident()}})
        self.saved_models = saved_models
        logger.opt(colors=True).info(
            f"创建数据分析 Agent: <c>{self.session_id}</>, 使用工具数: <y>{len(builtin_tools)}</>"
            + (f", MCP 工具数: <y>{len(mcp_tools)}</>" if mcp_tools else "")
        )

        return self.agent

    @classmethod
    async def create(
        cls,
        sources_dict: SourcesDict,
        llm: LLM,
        chat_model: BaseChatModel,
        session_id: SessionID,
        *,
        pre_model_hook: Runnable | None = None,  # for rate limiting
        mcp_connections: Iterable[Connection] | None = None,
    ) -> Self:
        self = super().__new__(cls)
        self.sources = Sources(sources_dict)
        self.llm = llm
        self.chat_model = chat_model
        self.session_id = session_id
        self.pre_model_hook = pre_model_hook
        self.mcp_connections = list(mcp_connections) if mcp_connections else None

        await self._create_graph()
        return self

    @property
    def mcp_count(self) -> int:
        return len(self.mcp_connections) if self.mcp_connections else 0

    def get_messages(self) -> list[AnyMessage]:
        """获取当前 agent 的对话记录"""
        return self.agent.get_state(self.config).values["messages"]

    def has_messages(self) -> bool:
        """检查 agent 是否有对话记录"""
        return len(self.get_messages()) > 0

    async def create_title(self) -> str:
        return await _create_title_chain(self.llm, self.get_messages()).ainvoke(...)

    async def summary(self, report_template: str | None = None) -> tuple[str, list[str]]:
        input = report_template or PROMPTS.default_report_template
        return await _summary_chain(self.llm, self.get_messages()).ainvoke(input)

    def _resume_from_state(self, state: DataAnalyzerAgentState) -> None:
        """从状态恢复 agent"""
        self.agent.update_state(self.config, state.values)
        self.saved_models.clear()
        self.saved_models.update(state.models)
        self.sources.random_state = state.sources_random_state
        self.sources.reset()
        resume_tool_calls(self.sources, state.values.get("messages", []))
        logger.opt(colors=True).info(f"已恢复 agent 状态: {state.colorize()}")

    async def load_state(self, state_file: Path) -> None:
        """从指定的状态文件加载 agent 状态。"""
        path = anyio.Path(state_file)
        if not await path.exists():
            return

        try:
            state = DataAnalyzerAgentState.model_validate_json(await path.read_bytes())
        except ValueError:
            logger.warning("无法加载 agent 状态: 状态文件格式错误")
            return

        await anyio.to_thread.run_sync(self._resume_from_state, state)

    async def save_state(self, state_file: Path) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = DataAnalyzerAgentState(
            values=cast("AgentValues", self.agent.get_state(self.config).values),
            models=self.saved_models,
            sources_random_state=self.sources.random_state,
        )
        await anyio.Path(state_file).write_bytes(state.model_dump_json().encode("utf-8"))
        logger.opt(colors=True).info(f"已保存 agent 状态: {state.colorize()}")

    async def destroy(self) -> None:
        """销毁 agent，释放资源"""
        if self._lifespan is not None:
            await self._lifespan.shutdown()
        logger.opt(colors=True).info(f"已销毁数据分析 Agent: <c>{self.session_id}</>")

    async def stream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        """使用用户输入调用 agent，并以流式方式返回事件"""
        logger.opt(colors=True).info(f"<c>{self.session_id}</> | 开始处理用户输入: <y>{escape_tag(user_input)}</>")

        async for event in self.agent.astream(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config,
            stream_mode="messages",
        ):
            for evt in process_stream_event(event):
                yield evt

        logger.opt(colors=True).success(f"<c>{self.session_id}</> | 处理完成")
