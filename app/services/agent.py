import contextlib
import dataclasses
from collections.abc import AsyncGenerator

import anyio
import anyio.lowlevel

from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain import get_models_async
from app.core.datasource import DataSource
from app.core.lifespan import lifespan
from app.exception import AgentCancelled, AgentInUse, AgentNotFound
from app.log import logger
from app.schemas.custom_model import LLModelID
from app.schemas.session import Session, SessionID
from app.services.datasource import datasource_service
from app.services.mcp import mcp_service
from app.utils import escape_tag


@dataclasses.dataclass
class AgentState:
    agent: DataAnalyzerAgent | None = None
    model_id: LLModelID | None = None
    lock: anyio.Lock = dataclasses.field(default_factory=anyio.Lock)
    scope: anyio.CancelScope | None = None


async def dataset_id_to_sources(dataset_ids: list[str]) -> dict[str, DataSource]:
    async def fetch(id: str) -> None:
        result[id] = (await datasource_service.get_source(id)).copy()

    result: dict[str, DataSource] = {}
    async with anyio.create_task_group() as tg:
        for id in dataset_ids:
            tg.start_soon(fetch, id)
    return result


class DataAnalyzerAgentService:
    def __init__(self) -> None:
        self.agents: dict[SessionID, AgentState] = {}

        lifespan.on_shutdown(self._destroy_all)

    async def _create(
        self,
        session: Session,
        model_id: LLModelID | None = None,
    ) -> DataAnalyzerAgent:
        """创建新的数据分析 Agent"""
        if self._get(session, None):
            await self._destroy(session.id, save_state=True, pop=False)

        mcps = mcp_service.gets(*(session.mcp_ids or []))
        sources = await dataset_id_to_sources(session.dataset_ids)
        llm, chat_model = await get_models_async(model_id)
        agent = await DataAnalyzerAgent.create(
            sources_dict=sources,
            llm=llm,
            chat_model=chat_model,
            session_id=session.id,
            mcp_connections=(mcp.connection for mcp in mcps),
        )
        await agent.load_state(STATE_DIR / f"{session.id}.json")

        self.agents[session.id].agent = agent
        self.agents[session.id].model_id = model_id
        logger.opt(colors=True).info(
            f"为会话 <c>{escape_tag(session.id)}</> 创建新 Agent，使用模型: <y>{escape_tag(model_id)}</>"
        )
        return agent

    def _get(self, session: Session, model_id: LLModelID | None = None) -> DataAnalyzerAgent | None:
        """获取指定会话和模型的 Agent"""
        state = self.agents.get(session.id)
        if state is None or (model_id is not None and state.model_id != model_id):
            return None
        return state.agent

    async def _destroy(self, session_id: SessionID, *, save_state: bool = False, pop: bool = True) -> None:
        """销毁会话的 Agent"""
        if session_id not in self.agents or (state := self.agents[session_id]).agent is None:
            raise AgentNotFound(session_id)

        await self._cancel(session_id)

        agent = state.agent
        state.agent = state.model_id = None

        if save_state:
            try:
                await agent.save_state(STATE_DIR / f"{session_id}.json")
            except Exception:
                logger.opt(colors=True).exception(f"保存会话 <c>{escape_tag(session_id)}</> 的 Agent 状态失败")

        try:
            await agent.destroy()
            logger.opt(colors=True).info(f"已销毁会话 <c>{escape_tag(session_id)}</> 的 Agent")
        except Exception:
            logger.opt(colors=True).exception(f"销毁会话 <c>{escape_tag(session_id)}</> 的 Agent 失败")

        if pop:
            self.agents.pop(session_id, None)

    async def _cancel(self, session_id: SessionID) -> None:
        """取消会话的 Agent 操作"""
        if (state := self.agents.get(session_id)) and (scope := state.scope):
            scope.cancel()
            await anyio.lowlevel.cancel_shielded_checkpoint()
            logger.opt(colors=True).info(f"取消会话 <c>{escape_tag(session_id)}</> 的 Agent 操作")

    async def _destroy_all(self) -> None:
        async def destroy(session_id: SessionID) -> None:
            try:
                await self._destroy(session_id, pop=True)
            except AgentNotFound:
                pass
            except Exception:
                logger.opt(colors=True).exception(f"销毁会话 <c>{escape_tag(session_id)}</> 的 Agent 失败")

        async with anyio.create_task_group() as tg:
            for session_id in self.agents:
                tg.start_soon(destroy, session_id)

    @contextlib.asynccontextmanager
    async def use_agent(
        self,
        session: Session,
        model_id: LLModelID | None = None,
    ) -> AsyncGenerator[DataAnalyzerAgent]:
        if session.id not in self.agents:
            self.agents[session.id] = AgentState()

        state = self.agents[session.id]
        if state.lock.locked():
            raise AgentInUse(session.id)

        async with state.lock:
            agent = self._get(session, model_id)
            if agent is None:
                agent = await self._create(session, model_id)

            with anyio.CancelScope() as scope:
                state.scope = scope
                try:
                    yield agent
                finally:
                    with anyio.CancelScope(shield=True):
                        state.scope = None

                        try:
                            await agent.save_state(STATE_DIR / f"{session.id}.json")
                        except Exception:
                            logger.opt(colors=True).exception(
                                f"保存会话 <c>{escape_tag(session.id)}</> 的 Agent 状态失败"
                            )

                        if scope.cancel_called:
                            raise AgentCancelled(session.id)

    async def refresh_mcp(self, session: Session) -> None:
        """刷新会话的 MCP 连接"""
        # 直接销毁当前 Agent，下次调用会创建带有新 MCP 的 Agent
        with contextlib.suppress(AgentNotFound):
            await self._destroy(session.id, pop=False)


daa_service = DataAnalyzerAgentService()
