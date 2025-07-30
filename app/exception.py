from fastapi import status

from app.schemas.session import SessionID


class AppError(Exception):
    pass


class ServiceError(AppError):
    service_name: str = "UNSET"


class DAAServiceError(ServiceError):
    service_name: str = "Data Analyzer Agent Service"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR


class AgentNotFound(DAAServiceError):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"未找到会话 {session_id} 的 agent")


class AgentInUse(DAAServiceError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"会话 {session_id} 的 agent 正在使用中")


class AgentCancelled(DAAServiceError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"会话 {session_id} 的 agent 操作已被取消")


class SessionServiceError(ServiceError):
    service_name: str = "Session Service"


class SessionNotFound(SessionServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"未找到会话 {session_id}")


class SessionLoadFailed(SessionServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"加载会话 {session_id} 失败")


class SessionDeleteFailed(SessionServiceError):
    def __init__(self, session_id: SessionID) -> None:
        super().__init__(f"删除会话 {session_id} 失败")


class DataSourceServiceError(ServiceError):
    service_name: str = "Data Source Service"


class DataSourceNotFound(DataSourceServiceError):
    def __init__(self, source_id: str) -> None:
        super().__init__(f"未找到数据源 {source_id}")


class DataSourceLoadFailed(DataSourceServiceError):
    def __init__(self, source_id: str) -> None:
        super().__init__(f"加载数据源 {source_id} 失败")
