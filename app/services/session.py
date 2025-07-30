import contextlib
import uuid

import anyio

from app.const import SESSION_DIR
from app.core.agent.tools import TOOL_NAMES
from app.core.lifespan import lifespan
from app.exception import SessionDeleteFailed, SessionLoadFailed, SessionNotFound
from app.log import logger
from app.schemas.session import Session, SessionID, SessionListItem

_SESSION_DIR = anyio.Path(SESSION_DIR)


class SessionService:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    async def session_exists(self, session_id: SessionID) -> bool:
        if session_id in self.sessions:
            return True
        try:
            await self.load_session(session_id)
            return True
        except Exception:
            return False

    async def create_session(self, dataset_ids: list[str], name: str | None = None) -> Session:
        session_id = str(uuid.uuid4())
        session = Session(id=session_id, dataset_ids=dataset_ids, name=name)
        await self.save_session(session)
        self.sessions[session_id] = session
        return session

    async def get_session(self, session_id: SessionID) -> Session | None:
        if session_id in self.sessions:
            return self.sessions[session_id]
        with contextlib.suppress(Exception):
            return await self.load_session(session_id)
        return None

    async def load_sessions(self) -> None:
        async def load(fp: anyio.Path) -> None:
            if not (await fp.is_file() and fp.suffix == ".json"):
                return

            try:
                await self.load_session(fp)
            except Exception as e:
                logger.opt(exception=True).warning(f"Failed to load session from {fp}: {e}")

        async with anyio.create_task_group() as tg:
            async for fp in _SESSION_DIR.iterdir():
                tg.start_soon(load, fp)

    async def load_session(self, session_id: SessionID | anyio.Path) -> Session:
        fp = (_SESSION_DIR / f"{session_id}.json") if isinstance(session_id, str) else session_id
        if not await fp.exists():
            raise SessionNotFound(session_id if isinstance(session_id, str) else "<Unknown>")

        try:
            session = Session.model_validate_json(await fp.read_bytes())
        except Exception as e:
            logger.opt(exception=True).warning(f"Failed to load session from {fp}")
            raise SessionLoadFailed(session_id if isinstance(session_id, str) else session_id.stem) from e
        else:
            self.sessions[session.id] = session
            return session

    async def save_sessions(self) -> None:
        async with anyio.create_task_group() as tg:
            for session in self.sessions.values():
                tg.start_soon(self.save_session, session)

    async def save_session(self, session: Session) -> None:
        self.sessions[session.id] = session
        fp = _SESSION_DIR / f"{session.id}.json"
        try:
            await fp.write_bytes(session.model_dump_json().encode("utf-8"))
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

    async def delete_session(self, session_id: SessionID) -> None:
        fp = _SESSION_DIR / f"{session_id}.json"
        if session_id not in self.sessions:
            # 检查文件是否存在，如果存在则尝试加载后再删除
            if not await fp.exists():
                raise SessionNotFound(session_id)

            try:
                await self.load_session(session_id)
            except Exception:
                # 如果加载失败，但文件存在，则直接删除文件
                try:
                    await fp.unlink()
                    logger.info(f"直接删除会话文件: {session_id}")
                    return
                except Exception as e:
                    logger.exception(f"删除会话文件失败: {e}")
                    raise SessionDeleteFailed(session_id) from e

        # 从内存中删除会话
        self.sessions.pop(session_id, None)

        # 删除文件
        try:
            if await fp.exists():
                await fp.unlink()
                logger.info(f"删除会话文件成功: {session_id}")
        except Exception as e:
            # 即使文件删除失败，也不抛出异常，因为内存中的会话已经被删除
            # 这样前端仍然可以认为删除成功
            logger.exception(f"删除会话文件失败: {e}")

    @staticmethod
    def tool_name_repr(session: Session) -> Session:
        session = session.model_copy(deep=True)
        for entry in session.chat_history:
            for tool_call in entry.assistant_response.tool_calls.values():
                tool_call.name = TOOL_NAMES.get(tool_call.name, tool_call.name)
        return session


session_service = SessionService()
lifespan.on_startup(session_service.load_sessions)
lifespan.on_shutdown(session_service.save_sessions)
