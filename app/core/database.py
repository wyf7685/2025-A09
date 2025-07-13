import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, declarative_base

from app.core.config import settings

kwargs = (
    {"connect_args": {"check_same_thread": False}}
    if settings.DATABASE_URL.startswith("sqlite")
    else {"pool_size": 25, "max_overflow": 75}
)
engine = create_async_engine(settings.DATABASE_URL, **kwargs)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base: type[DeclarativeBase] = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession]:
    db = SessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


def create_all() -> None:
    """创建所有数据库表"""

    async def create_all_tables() -> None:
        async with engine.begin() as conn:
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
