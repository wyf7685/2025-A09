from app.const import STATE_DIR
from app.core.agent import DataAnalyzerAgent
from app.core.chain import get_chat_model, get_llm
from app.log import logger
from app.services.datasource import datasource_service
from app.utils import run_sync

type SessionID = str
type ModelID = str


class DataAnalyzerAgentService:
    def __init__(self) -> None:
        self.agents: dict[SessionID, dict[ModelID, DataAnalyzerAgent]] = {}

    @run_sync
    def create_agent(
        self,
        source_id: str,
        session_id: SessionID,
        model_id: ModelID | None = None,
    ) -> DataAnalyzerAgent:
        """创建新的数据分析 Agent"""
        llm = get_llm()
        chat_model = get_chat_model(model_id)
        data_source = datasource_service.get_source(source_id).copy()
        agent = DataAnalyzerAgent(data_source, llm, chat_model, session_id)
        agent.load_state(STATE_DIR / f"{session_id}.json")
        self.agents.setdefault(session_id, {})[model_id or "$default"] = agent
        logger.info(f"为会话 {session_id} 创建新 Agent，使用模型: {model_id}")
        return agent

    def get_agent(
        self,
        session_id: SessionID,
        model_id: ModelID | None = None,
    ) -> DataAnalyzerAgent | None:
        """获取指定会话和模型的 Agent"""
        agent = self.agents.get(session_id, {}).get(model_id or "$default")
        if agent is not None:
            agent.load_state(STATE_DIR / f"{session_id}.json")
        return agent

    async def get_or_create_agent(
        self,
        source_id: str,
        session_id: SessionID,
        model_id: ModelID | None = None,
    ) -> DataAnalyzerAgent:
        """获取或创建数据分析 Agent"""
        if agent := self.get_agent(session_id, model_id):
            return agent
        return await self.create_agent(source_id, session_id, model_id)


daa_service = DataAnalyzerAgentService()
