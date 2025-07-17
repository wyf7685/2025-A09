import contextlib
import uuid
from pathlib import Path

from app.const import SESSION_DIR
from app.core.lifespan import lifespan
from app.log import logger
from app.schemas.session import Session, SessionID, SessionListItem


class SessionService:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    def session_exists(self, session_id: SessionID) -> bool:
        if session_id in self.sessions:
            return True
        try:
            self.load_session(session_id)
            return True
        except Exception:
            return False

    def create_session(self, dataset_id: str, name: str | None = None) -> Session:
        session_id = str(uuid.uuid4())
        session = Session(id=session_id, dataset_ids=[dataset_id], name=name)
        self.save_session(session)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: SessionID) -> Session | None:
        if session_id in self.sessions:
            return self.sessions[session_id]
        with contextlib.suppress(Exception):
            return self.load_session(session_id)
        return None

    def load_sessions(self) -> None:
        for fp in SESSION_DIR.iterdir():
            if not (fp.is_file() and fp.suffix == ".json"):
                continue
            try:
                self.load_session(fp)
            except Exception:
                logger.opt(exception=True).warning(f"Failed to load session from {fp}")

    def load_session(self, session_id: SessionID | Path) -> Session:
        fp = SESSION_DIR / f"{session_id}.json" if isinstance(session_id, str) else session_id
        if not fp.exists():
            raise KeyError(f"Session with id {session_id} not found")
        try:
            session = Session.model_validate_json(fp.read_bytes())
            self.sessions[session.id] = session
            return session
        except Exception as e:
            logger.opt(exception=True).warning(f"Failed to load session from {fp}")
            raise KeyError(f"Session with id {session_id} could not be loaded") from e

    def save_sessions(self) -> None:
        for session in self.sessions.values():
            self.save_session(session)

    def save_session(self, session: Session) -> None:
        self.sessions[session.id] = session
        fp = SESSION_DIR / f"{session.id}.json"
        try:
            fp.write_bytes(session.model_dump_json().encode("utf-8"))
        except Exception:
            logger.opt(exception=True).warning(f"Failed to save session {session.id} to {fp}")

    def list_sessions(self) -> list[SessionListItem]:
        return [
            SessionListItem(
                id=session.id,
                name=session.name or f"会话 {session.id[:8]}",
                created_at=session.created_at,
                chat_count=len(session.chat_history),
            )
            for session in self.sessions.values()
        ]

    def delete_session(self, session_id: SessionID) -> None:
        if session_id not in self.sessions:
            # 检查文件是否存在，如果存在则尝试加载后再删除
            fp = SESSION_DIR / f"{session_id}.json"
            if fp.exists():
                try:
                    self.load_session(session_id)
                except Exception:
                    # 如果加载失败，但文件存在，则直接删除文件
                    try:
                        fp.unlink()
                        logger.info(f"直接删除会话文件: {session_id}")
                        return
                    except Exception as e:
                        logger.exception(f"删除会话文件失败: {e}")
                        raise KeyError(f"Session with id {session_id} could not be deleted") from e
            else:
                raise KeyError(f"Session with id {session_id} not found")

        # 从内存中删除会话
        self.sessions.pop(session_id, None)

        # 删除文件
        fp = SESSION_DIR / f"{session_id}.json"
        try:
            if fp.exists():
                fp.unlink()
                logger.info(f"删除会话文件成功: {session_id}")
        except Exception as e:
            logger.exception(f"删除会话文件失败: {e}")
            # 即使文件删除失败，也不抛出异常，因为内存中的会话已经被删除
            # 这样前端仍然可以认为删除成功


session_service = SessionService()


@lifespan.on_startup
def _() -> None:
    """在应用启动时加载会话"""
    session_service.load_sessions()
