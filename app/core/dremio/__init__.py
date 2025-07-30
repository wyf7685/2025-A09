from app.utils import with_semaphore

from .abstract import AbstractAsyncDremioClient as AbstractAsyncDremioClient
from .abstract import AbstractDremioClient as AbstractDremioClient

_sync_client: AbstractDremioClient | None = None
_async_client: AbstractAsyncDremioClient | None = None


@with_semaphore(1)
def get_dremio_client() -> AbstractDremioClient:
    from app.log import logger

    global _sync_client

    if _sync_client is None:
        try:
            from .flight import DremioFlightClient

            _sync_client = DremioFlightClient()

        except Exception:
            logger.warning("使用Flight客户端连接Dremio失败，尝试使用REST客户端")
            from .rest import DremioRestClient

            _sync_client = DremioRestClient()

        logger.opt(colors=True).success(f"初始化 Sync Dremio: <g>{_sync_client.__class__.__name__}</>")

    return _sync_client


@with_semaphore(1)
def get_async_dremio_client() -> AbstractAsyncDremioClient:
    from app.log import logger

    global _async_client

    if _async_client is None:
        try:
            from .aflight import AsyncDremioFlightClient

            _async_client = AsyncDremioFlightClient()

        except Exception:
            logger.warning("使用Flight客户端连接Dremio失败，尝试使用REST客户端")
            from .arest import AsyncDremioRestClient

            _async_client = AsyncDremioRestClient()

        logger.opt(colors=True).success(f"初始化 Async Dremio: <g>{_async_client.__class__.__name__}</>")

    return _async_client


__all__ = [
    "AbstractAsyncDremioClient",
    "AbstractDremioClient",
    "get_async_dremio_client",
    "get_dremio_client",
]
