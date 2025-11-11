from app.log import logger
from app.utils import with_semaphore

from .abstract import AbstractAsyncDremioClient as AbstractAsyncDremioClient
from .abstract import AbstractDremioClient as AbstractDremioClient

_sync_client: AbstractDremioClient | None = None
_async_client: AbstractAsyncDremioClient | None = None


@with_semaphore(1)
def get_dremio_client() -> AbstractDremioClient:
    global _sync_client

    if _sync_client is None:
        try:
            from .flight import DremioFlightClient

            _sync_client = DremioFlightClient()

        except Exception as e:
            logger.warning(f"使用 Flight 客户端连接 Dremio 失败，尝试使用 REST 客户端 - {e!r}")
            from .rest import DremioRestClient

            _sync_client = DremioRestClient()

        logger.opt(colors=True).success(f"初始化 Sync Dremio: <g>{_sync_client.__class__.__name__}</>")

    return _sync_client


@with_semaphore(1)
def get_async_dremio_client() -> AbstractAsyncDremioClient:
    global _async_client

    if _async_client is None:
        try:
            from .aflight import AsyncDremioFlightClient

            _async_client = AsyncDremioFlightClient()

        except Exception as e:
            logger.warning(f"使用 Flight 客户端连接 Dremio 失败，尝试使用 REST 客户端 - {e!r}")
            from .arest import AsyncDremioRestClient

            _async_client = AsyncDremioRestClient()

        logger.opt(colors=True).success(f"初始化 Async Dremio: <g>{_async_client.__class__.__name__}</>")

    return _async_client


async def expire_dremio_cache() -> None:
    from ._cache import container_cache, source_cache

    await container_cache.aexpire()
    await source_cache.aexpire()


__all__ = [
    "AbstractAsyncDremioClient",
    "AbstractDremioClient",
    "expire_dremio_cache",
    "get_async_dremio_client",
    "get_dremio_client",
]
