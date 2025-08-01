import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable
from types import TracebackType
from typing import cast

import anyio
from anyio.abc import TaskGroup

from app.log import logger
from app.utils import is_coroutine_callable, run_sync

type SYNC_LIFESPAN_FUNC = Callable[[], object]
type ASYNC_LIFESPAN_FUNC = Callable[[], Awaitable[object]]
type LIFESPAN_FUNC = SYNC_LIFESPAN_FUNC | ASYNC_LIFESPAN_FUNC


def _ensure_async(func: LIFESPAN_FUNC) -> ASYNC_LIFESPAN_FUNC:
    return cast("ASYNC_LIFESPAN_FUNC", func) if is_coroutine_callable(func) else run_sync(func)


class Lifespan:
    def __init__(self, name: str) -> None:
        self._name = name
        self._task_group: TaskGroup | None = None

        self._startup_funcs: list[ASYNC_LIFESPAN_FUNC] = []
        self._ready_funcs: list[ASYNC_LIFESPAN_FUNC] = []
        self._shutdown_funcs: list[ASYNC_LIFESPAN_FUNC] = []

    @property
    def task_group(self) -> TaskGroup:
        if self._task_group is None:
            raise RuntimeError("Lifespan not started")
        return self._task_group

    @task_group.setter
    def task_group(self, task_group: TaskGroup) -> None:
        if self._task_group is not None:
            raise RuntimeError("Lifespan already started")
        self._task_group = task_group

    def on_startup[F: LIFESPAN_FUNC](self, func: F) -> F:
        self._startup_funcs.append(_ensure_async(func))
        return func

    def on_shutdown[F: LIFESPAN_FUNC](self, func: F) -> F:
        self._shutdown_funcs.append(_ensure_async(func))
        return func

    def on_ready[F: LIFESPAN_FUNC](self, func: F) -> F:
        self._ready_funcs.append(_ensure_async(func))
        return func

    async def _run_lifespan_func(self, funcs: Iterable[ASYNC_LIFESPAN_FUNC]) -> None:
        async with anyio.create_task_group() as tg:
            for func in funcs:
                tg.start_soon(func)

    def _log(self, msg: str, /) -> None:
        logger.opt(colors=True).debug(f"<m>{self._name}</> | {msg}")

    async def startup(self) -> None:
        # create background task group
        self._log("生命周期启动中...")
        self.task_group = anyio.create_task_group()
        await self.task_group.__aenter__()

        # run startup funcs
        if self._startup_funcs:
            self._log("执行生命周期函数: <y>startup</>")
            await self._run_lifespan_func(self._startup_funcs)

        # run ready funcs
        if self._ready_funcs:
            self._log("执行生命周期函数: <y>ready</>")
            await self._run_lifespan_func(self._ready_funcs)

        self._log("生命周期启动完成")

    async def shutdown(
        self,
        *,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        if self._shutdown_funcs:
            self._log("执行生命周期函数: <y>shutdown</>")
            await self._run_lifespan_func(reversed(self._shutdown_funcs))

        # shutdown background task group
        self._log("正在关闭任务组")
        self.task_group.cancel_scope.cancel()
        with contextlib.suppress(Exception):
            await self.task_group.__aexit__(exc_type, exc_val, exc_tb)

        self._log("生命周期关闭完成")
        self._task_group = None

    async def __aenter__(self, *_: object) -> None:
        await self.startup()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.shutdown(exc_type=exc_type, exc_val=exc_val, exc_tb=exc_tb)

    @contextlib.asynccontextmanager
    async def __call__(self, *_: object) -> AsyncGenerator[None]:
        try:
            await self.startup()
            yield
        finally:
            await self.shutdown()


# Global lifespan instance, used by FastAPI application
lifespan = Lifespan("Application")
