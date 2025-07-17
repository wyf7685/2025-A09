from app.schemas.session import SessionID


class AppError(Exception):
    pass


class ServiceError(AppError):
    service_name: str = "UNSET"


class DAAServiceError(ServiceError):
    service_name: str = "Data Analyzer Agent Service"


class AgentNotFound(DAAServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"Agent not found for session {session_id}")


class AgentInUse(DAAServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"Agent for session {session_id} is currently in use")
