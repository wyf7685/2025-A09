import contextlib
from collections.abc import AsyncGenerator
from typing import NamedTuple

import anyio
from anyio.lowlevel import checkpoint

from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain import get_chat_model_async, get_llm_async
from app.core.lifespan import lifespan
from app.exception import AgentCancelled, AgentInUse, AgentNotFound
from app.log import logger
from app.schemas.custom_model import LLModelID
from app.schemas.session import Session, SessionID
from app.services.datasource import datasource_service
from app.services.mcp import mcp_service
from app.utils import escape_tag


class AgentTuple(NamedTuple):
    agent: DataAnalyzerAgent
    model_id: LLModelID | None


class DataAnalyzerAgentService:
    def __init__(self) -> None:
        self.agents: dict[SessionID, AgentTuple] = {}
        self._in_use: dict[SessionID, anyio.Lock] = {}
        self._scope: dict[SessionID, anyio.CancelScope] = {}

        lifespan.on_shutdown(self._destroy_all)

    async def _create(
        self,
        session: Session,
        model_id: LLModelID | None = None,
    ) -> DataAnalyzerAgent:
        """创建新的数据分析 Agent"""
        state_file = STATE_DIR / f"{session.id}.json"
        if existing := self._get(session, None):
            try:
                self.cancel(session.id)
                await existing.save_state(state_file)
                await existing.destroy()
            except Exception:
                logger.opt(colors=True).exception(f"销毁会话 <c>{escape_tag(session.id)}</> 的 Agent 失败")
            finally:
                self.agents.pop(session.id, None)
                del existing

        mcps = mcp_service.gets(*(session.mcp_ids or []))
        sources = {id: (await datasource_service.get_source(id)).copy() for id in session.dataset_ids}
        llm = await get_llm_async(model_id)
        chat_model = await get_chat_model_async(model_id)
        agent = await DataAnalyzerAgent.create(
            sources_dict=sources,
            llm=llm,
            chat_model=chat_model,
            session_id=session.id,
            mcp_connections=(mcp.connection for mcp in mcps),
        )
        await agent.load_state(state_file)

        self.agents[session.id] = AgentTuple(agent, model_id)
        logger.opt(colors=True).info(
            f"为会话 <c>{escape_tag(session.id)}</> 创建新 Agent，使用模型: <y>{escape_tag(model_id)}</>"
        )
        return agent

    def _get(
        self,
        session: Session,
        model_id: LLModelID | None = None,
    ) -> DataAnalyzerAgent | None:
        """获取指定会话和模型的 Agent"""
        t = self.agents.get(session.id)
        if t is None or (model_id is not None and t.model_id != model_id):
            return None
        return t.agent

    async def destroy(self, session_id: SessionID) -> None:
        """销毁会话的 Agent"""
        if session_id not in self.agents:
            raise AgentNotFound(session_id)

        self.cancel(session_id)
        await checkpoint()

        agent, *_ = self.agents.pop(session_id)
        self._scope.pop(session_id, None)
        self._in_use.pop(session_id, None)

        try:
            await agent.destroy()
            logger.opt(colors=True).info(f"已销毁会话 <c>{escape_tag(session_id)}</> 的 Agent")
        except Exception:
            logger.opt(colors=True).exception(f"销毁会话 <c>{escape_tag(session_id)}</> 的 Agent 失败")

    def cancel(self, session_id: SessionID) -> None:
        """取消会话的 Agent 操作"""
        if scope := self._scope.get(session_id):
            scope.cancel()
            logger.opt(colors=True).info(f"取消会话 <c>{escape_tag(session_id)}</> 的 Agent 操作")

    @contextlib.asynccontextmanager
    async def use_agent(
        self,
        session: Session,
        model_id: LLModelID | None = None,
        *,
        create_if_non_exist: bool,
    ) -> AsyncGenerator[DataAnalyzerAgent]:
        if session.id not in self._in_use:
            self._in_use[session.id] = anyio.Lock()

        if self._in_use[session.id].locked():
            raise AgentInUse(session.id)

        async with self._in_use[session.id]:
            agent = self._get(session, model_id)
            if agent is None:
                if not create_if_non_exist:
                    raise AgentNotFound(session.id)
                agent = await self._create(session, model_id)

            with anyio.CancelScope() as scope:
                self._scope[session.id] = scope
                try:
                    yield agent
                finally:
                    with anyio.CancelScope(shield=True):
                        self._scope.pop(session.id, None)

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
        # mcps = mcp_service.gets(*(session.mcp_ids or []))

        ### v1
        # async with self.use_agent(session, create_if_non_exist=True) as agent:
        #     await agent.bind_mcp(mcp.connection for mcp in mcps)
        # logger.opt(colors=True).info(f"刷新会话 <c>{escape_tag(session.id)}</> 的 MCP 连接")

        ### v2
        # try:
        #     async with self.use_agent(session, create_if_non_exist=False) as agent:
        #         await agent.bind_mcp(mcp.connection for mcp in mcps)
        # except AgentNotFound:
        #     return
        # else:
        #     logger.opt(colors=True).info(f"刷新会话 <c>{escape_tag(session.id)}</> 的 MCP 连接")

        ### v3
        # 直接删掉，下次用到就会创建带有新 MCP 的 Agent
        with contextlib.suppress(AgentNotFound):
            await self.destroy(session.id)

    async def _destroy_all(self) -> None:
        async def destroy(session_id: SessionID) -> None:
            try:
                await self.destroy(session_id)
            except AgentNotFound:
                pass
            except Exception:
                logger.opt(colors=True).exception(f"销毁会话 <c>{escape_tag(session_id)}</> 的 Agent 失败")

        async with anyio.create_task_group() as tg:
            for session_id in self.agents:
                tg.start_soon(destroy, session_id)


daa_service = DataAnalyzerAgentService()
