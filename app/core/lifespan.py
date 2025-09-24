import contextlib
import enum
import functools
import threading
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable
from types import TracebackType
from typing import Any, cast

import anyio
from anyio.abc import TaskGroup

from app.log import logger
from app.utils import escape_tag, is_coroutine_callable, run_sync

type SyncLifespanFunc = Callable[[], object]
type AsyncLifespanFunc = Callable[[], Awaitable[object]]
type LifespanFunc = SyncLifespanFunc | AsyncLifespanFunc


def _ensure_async(func: LifespanFunc) -> AsyncLifespanFunc:
    return cast("AsyncLifespanFunc", func) if is_coroutine_callable(func) else run_sync(func)


class LifespanState(int, enum.Enum):
    INITIAL = 0  # task group not created
    STARTING = 1  # task group created, running startup functions
    STARTED = 2  # lifespan started, running ready functions
    STOPPING = 3  # running shutdown functions
    STOPPED = 4  # task group stopped


class Lifespan:
    def __init__(self, name: str) -> None:
        self._name = name
        self._state: LifespanState = LifespanState.INITIAL
        self._task_group: TaskGroup | None = None

        self._startup_funcs: list[AsyncLifespanFunc] = []
        self._ready_funcs: list[AsyncLifespanFunc] = []
        self._shutdown_funcs: list[AsyncLifespanFunc] = []

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

    def start_soon[*Ts](self, func: Callable[[*Ts], Awaitable[object]], /, *args: *Ts, name: object = None) -> None:
        @functools.wraps(func)
        async def wrapper() -> None:
            await func(*args)

        self.task_group.start_soon(self._run, wrapper, "后台任务执行失败", False, name=name)

    def from_thread[*Ts, R](self, func: Callable[[*Ts], Awaitable[R]], /, *args: *Ts) -> R:
        event = threading.Event()
        _unset = object()
        result: Any = _unset

        async def _wrapper() -> None:
            nonlocal result
            try:
                result = await func(*args)
            except Exception as e:
                result = e
            finally:
                event.set()

        self.start_soon(_wrapper)
        event.wait()

        if isinstance(result, Exception):
            raise result
        assert result is not _unset
        return result

    def on_startup[F: LifespanFunc](self, func: F) -> F:
        f = _ensure_async(func)
        self._startup_funcs.append(f)
        if self._state in (LifespanState.STARTING, LifespanState.STARTED):
            self.start_soon(f)
        return func

    def on_shutdown[F: LifespanFunc](self, func: F) -> F:
        self._shutdown_funcs.append(_ensure_async(func))
        return func

    def on_ready[F: LifespanFunc](self, func: F) -> F:
        f = _ensure_async(func)
        self._ready_funcs.append(f)
        if self._state == LifespanState.STARTED:
            self.start_soon(f)
        return func

    async def _run(self, func: AsyncLifespanFunc, err_msg: str, should_raise: bool) -> None:
        try:
            await func()
        except Exception:
            logger.opt(colors=True, exception=True).error(
                f"<m>{self._name}</> | {err_msg} - <y>{escape_tag(repr(func))}</>"
            )
            if should_raise:
                raise

    async def _run_lifespan_func(self, funcs: Iterable[AsyncLifespanFunc]) -> None:
        async with anyio.create_task_group() as tg:
            for func in funcs:
                tg.start_soon(self._run, func, "生命周期函数执行失败", True)

    def _log(self, msg: str, /) -> None:
        logger.opt(colors=True).debug(f"<m>{self._name}</> | {msg}")

    async def startup(self) -> None:
        if self._state != LifespanState.INITIAL:
            raise RuntimeError("Lifespan already started or starting")

        # create background task group
        self._log("生命周期启动中...")
        self.task_group = anyio.create_task_group()
        await self.task_group.__aenter__()
        self._state = LifespanState.STARTING

        # run startup funcs
        if self._startup_funcs:
            self._log(f"执行生命周期函数: <g>startup</> - <y>{len(self._startup_funcs)}</>")
            await self._run_lifespan_func(self._startup_funcs[:])

        self._state = LifespanState.STARTED

        # run ready funcs
        if self._ready_funcs:
            self._log(f"执行生命周期函数: <g>ready</> - <y>{len(self._ready_funcs)}</>")
            await self._run_lifespan_func(self._ready_funcs[:])

        self._log("生命周期启动完成")

    async def shutdown(
        self,
        *,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> None:
        if self._state in (LifespanState.INITIAL, LifespanState.STOPPED):
            raise RuntimeError("Lifespan not started or already stopped")

        self._log("正在关闭生命周期...")
        self._state = LifespanState.STOPPING

        if self._shutdown_funcs:
            self._log(f"执行生命周期函数: <g>shutdown</> - <y>{len(self._shutdown_funcs)}</>")
            with anyio.CancelScope(shield=True):
                await self._run_lifespan_func(reversed(self._shutdown_funcs[:]))

        # shutdown background task group
        self._log("正在关闭任务组")
        self.task_group.cancel_scope.cancel()
        with contextlib.suppress(Exception):
            await self.task_group.__aexit__(exc_type, exc_val, exc_tb)

        self._log("生命周期关闭完成")
        self._task_group = None
        self._state = LifespanState.STOPPED

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
