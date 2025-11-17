from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Self, cast

import anyio
import anyio.lowlevel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage
from langchain_core.runnables import Runnable

from app.core.agent.events import StreamEvent, ToolCallEvent, build_tool_call_event, process_stream_event
from app.core.agent.prompts.data_analyzer import PROMPTS
from app.core.agent.schemas import AgentRuntimeContext, SourcesDict
from app.core.agent.sources import Sources
from app.core.chain.llm import get_llm_async
from app.log import logger
from app.schemas.mcp import Connection
from app.schemas.session import SessionID
from app.utils import escape_tag, run_sync

from .context import AgentContext
from .schemas import AgentValues, DataAnalyzerAgentState, WorkflowData
from .utils import create_title_chain, resume_tool_calls, summary_chain

logger = logger.opt(colors=True)


class DataAnalyzerAgent:
    ctx: AgentContext
    _wf_data: WorkflowData

    def __init__(self) -> None:
        raise NotImplementedError("Use the `create` class method to instantiate this agent.")

    @classmethod
    async def create(
        cls,
        session_id: SessionID,
        sources_dict: SourcesDict,
        mcp_connections: list[tuple[str, Connection]] | None = None,
        pre_model_hook: Runnable | None = None,
    ) -> Self:
        self = super().__new__(cls)
        self.ctx = AgentContext(
            session_id=session_id,
            sources=Sources(sources_dict),
            mcp_connections=mcp_connections,
            pre_model_hook=pre_model_hook,
        )
        self._wf_data = WorkflowData()
        await self.ctx.build_graph()
        return self

    def get_messages(self) -> list[AnyMessage]:
        """获取当前 agent 的对话记录"""
        return self.ctx.graph.get_state(self.ctx.runnable_config).values["messages"]

    def has_messages(self) -> bool:
        """检查 agent 是否有对话记录"""
        return len(self.get_messages()) > 0

    async def create_title(self) -> str:
        cfg = await self.ctx.get_model_config()
        llm = await get_llm_async(cfg.create_title)
        return await create_title_chain(llm, self.get_messages()).ainvoke(...)

    async def summary(self, report_template: str | None = None) -> tuple[str, list[str]]:
        cfg = await self.ctx.get_model_config()
        llm = await get_llm_async(cfg.summary)
        input = report_template or PROMPTS.default_report_template
        return await summary_chain(llm, self.get_messages()).ainvoke(input)

    async def get_state(self) -> DataAnalyzerAgentState:
        """获取当前 agent 状态"""
        return DataAnalyzerAgentState(
            values=cast("AgentValues", self.ctx.graph.get_state(self.ctx.runnable_config).values),
            models=self.ctx.saved_models,
            sources_random_state=self.ctx.sources.random_state,
            workflow_data=self._wf_data,
        )

    @run_sync
    def set_state(self, state: DataAnalyzerAgentState, context: AgentRuntimeContext) -> None:
        """设置当前 agent 状态"""
        self.ctx.graph.update_state(self.ctx.runnable_config, state.values)
        self.ctx.saved_models.clear()
        self.ctx.saved_models.update(state.models)
        self.ctx.sources.random_state = state.sources_random_state
        self.ctx.sources.reset()
        self._wf_data = state.workflow_data
        resume_tool_calls(context, state.workflow_data, state.values.get("messages", []))
        logger.info(f"已恢复 agent 状态: {state.colorize()}")

    async def load_state(self, state_file: Path | None = None) -> None:
        """从指定的状态文件加载 agent 状态。"""
        path = anyio.Path(state_file or self.ctx.state_file)
        if not await path.exists():
            return

        try:
            data = await path.read_bytes()
        except Exception as e:
            logger.warning(f"无法加载 agent 状态: 读取状态文件时出错: {escape_tag(repr(e))}")
            return

        try:
            state = DataAnalyzerAgentState.model_validate_json(data)
        except ValueError:
            logger.warning("无法加载 agent 状态: 状态文件格式错误")
            return

        await self.set_state(state, await self.ctx.create_runtime_context())

    async def save_state(self, state_file: Path | None = None) -> None:
        """将当前 agent 状态保存到指定的状态文件。"""
        state = await self.get_state()
        data = state.model_dump_json().encode("utf-8")
        await anyio.Path(state_file or self.ctx.state_file).write_bytes(data)
        logger.info(f"已保存 agent 状态: {state.colorize()}")

    async def destroy(self) -> None:
        """销毁 agent，释放资源"""
        if self.ctx.lifespan is not None:
            await self.ctx.lifespan.shutdown()
            self.ctx.lifespan = None
        logger.info(f"已销毁数据分析 Agent: <c>{self.ctx.session_id}</>")

    async def stream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        """使用用户输入调用 agent，并以流式方式返回事件"""
        prefix = f"<c>{self.ctx.session_id}</> |"
        logger.info(f"{prefix} 开始处理用户输入: <y>{escape_tag(user_input)}</>")

        event_send, event_recv = anyio.create_memory_object_stream[StreamEvent](0)

        async def stream_graph() -> None:
            async for event in self.ctx.graph.astream(
                {"messages": [{"role": "user", "content": user_input}]},
                self.ctx.runnable_config,
                context=await self.ctx.create_runtime_context(),
                stream_mode="messages",
            ):
                if not isinstance(event, tuple) or len(event) != 2:
                    continue
                message, metadata = cast("tuple[BaseMessage, dict[str, Any]]", event)
                if isinstance(message, AIMessage) and metadata.get("langgraph_node") != "agent":
                    continue
                for evt in process_stream_event(message, lookup_tool_source=self.ctx.lookup_tool_source):
                    if not isinstance(evt, ToolCallEvent):  # see read_tool_calls()
                        await event_send.send(evt)

            tg.cancel_scope.cancel()

        async def read_tool_calls() -> None:
            while True:
                for tc in self.ctx.flush_buffered_tool_calls():
                    if evt := build_tool_call_event(tc, self.ctx.lookup_tool_source):
                        logger.info(
                            f"{prefix} 开始工具调用: <y>{escape_tag(evt.id)}</> - <g>{escape_tag(evt.name)}</>\n"
                            f"{escape_tag(str(evt.args))}"
                        )
                        await event_send.send(evt)
                await anyio.lowlevel.checkpoint()

        async with anyio.create_task_group() as tg:
            tg.start_soon(stream_graph)
            tg.start_soon(read_tool_calls)

            async for event in event_recv:
                yield event

        logger.success(f"{prefix} 处理完成")
