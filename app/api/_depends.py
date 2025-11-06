from typing import Annotated

from fastapi import Depends, HTTPException, Path
from pydantic import BaseModel

from app.schemas.session import Session, SessionID
from app.services.session import session_service


async def _current_session_from_path(session_id: SessionID = Path(description="会话ID")) -> Session:
    if session := await session_service.get(session_id):
        return session
    raise HTTPException(status_code=404, detail="Session not found")


CurrentSessionFromPath = Annotated[Session, Depends(_current_session_from_path)]


class _SessionIDBody(BaseModel):
    session_id: SessionID


async def _current_session_from_body(request: _SessionIDBody) -> Session:
    if session := await session_service.get(request.session_id):
        return session
    raise HTTPException(status_code=404, detail="Session not found")


CurrentSessionFromBody = Annotated[Session, Depends(_current_session_from_body)]
