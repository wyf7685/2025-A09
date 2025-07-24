import contextlib
from collections.abc import AsyncGenerator
from typing import NamedTuple

from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain import get_chat_model, get_llm
from app.exception import AgentInUse, AgentNotFound
from app.log import logger
from app.schemas.custom_model import LLModelID
from app.schemas.session import Session, SessionID
from app.services.datasource import datasource_service
from app.utils import escape_tag, run_sync


class AgentTuple(NamedTuple):
    model_id: LLModelID | None
    agent: DataAnalyzerAgent


class DataAnalyzerAgentService:
    def __init__(self) -> None:
        self.agents: dict[SessionID, AgentTuple] = {}
        self.in_use: dict[SessionID, bool] = {}

    @run_sync
    def create_agent(
        self,
        session: Session,
        model_id: LLModelID | None = None,
    ) -> DataAnalyzerAgent:
        """创建新的数据分析 Agent"""
        state_file = STATE_DIR / f"{session.id}.json"
        if agent := self.get_agent(session, None):
            agent.save_state(state_file)

        llm = get_llm(model_id)
        chat_model = get_chat_model(model_id)
        sources = {source_id: datasource_service.get_source(source_id).copy() for source_id in session.dataset_ids}
        agent = DataAnalyzerAgent(sources, llm, chat_model, session.id)
        agent.load_state(state_file)
        self.agents[session.id] = AgentTuple(model_id, agent)
        logger.opt(colors=True).info(
            f"为会话 <c>{escape_tag(session.id)}</> 创建新 Agent，使用模型: <y>{escape_tag(model_id)}</>"
        )
        return agent

    def get_agent(
        self,
        session: Session,
        model_id: LLModelID | None = None,
    ) -> DataAnalyzerAgent | None:
        """获取指定会话和模型的 Agent"""
        t = self.agents.get(session.id)
        if t is None or (model_id is not None and t.model_id != model_id):
            return None
        return t.agent

    def aquire(self, session_id: SessionID) -> bool:
        """尝试获取会话的 Agent"""
        if self.in_use.get(session_id, False):
            return False
        logger.opt(colors=True).info(f"获取会话 <c>{escape_tag(session_id)}</> 的 Agent")
        self.in_use[session_id] = True
        return True

    def release(self, session_id: SessionID) -> None:
        """释放会话的 Agent"""
        if session_id in self.in_use:
            del self.in_use[session_id]
            logger.opt(colors=True).info(f"释放会话 <c>{escape_tag(session_id)}</> 的 Agent")
        else:
            logger.opt(colors=True).warning(f"尝试释放未被占用的会话 <c>{escape_tag(session_id)}</> 的 Agent")

    @contextlib.asynccontextmanager
    async def use_agent(
        self,
        session: Session,
        model_id: LLModelID | None = None,
        *,
        create_if_non_exist: bool,
    ) -> AsyncGenerator[DataAnalyzerAgent]:
        if not self.aquire(session.id):
            raise AgentInUse(session.id)

        agent = self.get_agent(session, model_id)
        if agent is None:
            if not create_if_non_exist:
                raise AgentNotFound(session.id)
            agent = await self.create_agent(session, model_id)

        try:
            yield agent
        finally:
            agent.save_state(STATE_DIR / f"{session.id}.json")
            self.release(session.id)


daa_service = DataAnalyzerAgentService()
