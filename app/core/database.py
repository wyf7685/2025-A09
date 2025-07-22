import asyncio
from collections.abc import AsyncGenerator
from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, declarative_base

from app.core.config import settings

_engine = create_async_engine(
    settings.DATABASE_URL,
    **(
        {"connect_args": {"check_same_thread": False}}
        if settings.DATABASE_URL.startswith("sqlite")
        else {"pool_size": 25, "max_overflow": 75}
    ),
)
_session_maker = async_sessionmaker(autocommit=False, autoflush=False, bind=_engine)
_current_session = ContextVar[AsyncSession]("current_session")

Base: type[DeclarativeBase] = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession]:
    session = _session_maker()
    s_t = _current_session.set(session)

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        _current_session.reset(s_t)
        await session.close()


def get_current_session() -> AsyncSession:
    """
    获取当前的数据库会话

    Returns:
        AsyncSession: 当前的数据库会话

    Raises:
        LookupError: 如果没有当前会话
    """
    return _current_session.get()


def create_all() -> None:
    """创建所有数据库表"""

    async def create_all_tables() -> None:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        loop.create_task(create_all_tables()).add_done_callback(lambda _: None)
        return

    asyncio.run(create_all_tables())


DBSession = Annotated[AsyncSession, Depends(get_db)]
