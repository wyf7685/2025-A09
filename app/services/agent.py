import contextlib
from collections.abc import AsyncGenerator

from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain import get_chat_model, get_llm
from app.log import logger
from app.schemas.session import Session
from app.services.datasource import datasource_service
from app.utils import run_sync

type SessionID = str
type ModelID = str


class DAAServiceError(Exception):
    pass


class AgentNotFound(DAAServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"Agent not found for session {session_id}")


class AgentInUse(DAAServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"Agent for session {session_id} is currently in use")


class DataAnalyzerAgentService:
    def __init__(self) -> None:
        self.agents: dict[SessionID, tuple[ModelID | None, DataAnalyzerAgent]] = {}
        self.in_use: dict[SessionID, bool] = {}

    @run_sync
    def create_agent(
        self,
        session: Session,
        model_id: ModelID | None = None,
    ) -> DataAnalyzerAgent:
        """创建新的数据分析 Agent"""
        state_file = STATE_DIR / f"{session.id}.json"
        if agent := self.get_agent(session, None):
            agent.save_state(state_file)

        llm = get_llm()
        chat_model = get_chat_model(model_id)
        sources = {source_id: datasource_service.get_source(source_id).copy() for source_id in session.dataset_ids}
        agent = DataAnalyzerAgent(sources, llm, chat_model, session.id)
        agent.load_state(state_file)
        self.agents[session.id] = model_id, agent
        logger.info(f"为会话 {session.id} 创建新 Agent，使用模型: {model_id}")
        return agent

    def get_agent(
        self,
        session: Session,
        model_id: ModelID | None = None,
    ) -> DataAnalyzerAgent | None:
        """获取指定会话和模型的 Agent"""
        previous, agent = self.agents.get(session.id, (None, None))
        if model_id is not None and previous != model_id:
            return None
        return agent

    def aquire(self, session_id: SessionID) -> bool:
        """尝试获取会话的 Agent"""
        if self.in_use.get(session_id, False):
            return False
        self.in_use[session_id] = True
        return True

    def release(self, session_id: SessionID) -> None:
        """释放会话的 Agent"""
        if session_id in self.in_use:
            del self.in_use[session_id]
            logger.info(f"释放会话 {session_id} 的 Agent")
        else:
            logger.warning(f"尝试释放未被占用的会话 {session_id} 的 Agent")

    @contextlib.asynccontextmanager
    async def use_agent(
        self,
        session: Session,
        model_id: ModelID | None = None,
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
