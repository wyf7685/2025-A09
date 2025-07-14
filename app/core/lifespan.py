import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable
from types import TracebackType
from typing import Any, cast

import anyio
from anyio.abc import TaskGroup

from app.utils import is_coroutine_callable, run_sync

type SYNC_LIFESPAN_FUNC = Callable[[], Any]
type ASYNC_LIFESPAN_FUNC = Callable[[], Awaitable[Any]]
type LIFESPAN_FUNC = SYNC_LIFESPAN_FUNC | ASYNC_LIFESPAN_FUNC


class Lifespan:
    def __init__(self) -> None:
        self._task_group: TaskGroup | None = None

        self._startup_funcs: list[LIFESPAN_FUNC] = []
        self._ready_funcs: list[LIFESPAN_FUNC] = []
        self._shutdown_funcs: list[LIFESPAN_FUNC] = []

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

    def on_startup(self, func: LIFESPAN_FUNC) -> LIFESPAN_FUNC:
        self._startup_funcs.append(func)
        return func

    def on_shutdown(self, func: LIFESPAN_FUNC) -> LIFESPAN_FUNC:
        self._shutdown_funcs.append(func)
        return func

    def on_ready(self, func: LIFESPAN_FUNC) -> LIFESPAN_FUNC:
        self._ready_funcs.append(func)
        return func

    @staticmethod
    async def _run_lifespan_func(
        funcs: Iterable[LIFESPAN_FUNC],
    ) -> None:
        for func in funcs:
            if is_coroutine_callable(func):
                await cast("ASYNC_LIFESPAN_FUNC", func)()
            else:
                await run_sync(cast("SYNC_LIFESPAN_FUNC", func))()

    async def startup(self) -> None:
        # create background task group
        self.task_group = anyio.create_task_group()
        await self.task_group.__aenter__()

        # run startup funcs
        if self._startup_funcs:
            await self._run_lifespan_func(self._startup_funcs)

        # run ready funcs
        if self._ready_funcs:
            await self._run_lifespan_func(self._ready_funcs)

    async def shutdown(
        self,
        *,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        if self._shutdown_funcs:
            # reverse shutdown funcs to ensure stack order
            await self._run_lifespan_func(reversed(self._shutdown_funcs))

        # shutdown background task group
        self.task_group.cancel_scope.cancel()

        with contextlib.suppress(Exception):
            await self.task_group.__aexit__(exc_type, exc_val, exc_tb)

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


lifespan = Lifespan()
