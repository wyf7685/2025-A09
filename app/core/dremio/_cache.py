from aiocache import BaseCache, RedisCache, SimpleMemoryCache

from app.core.config import settings
from app.core.lifespan import lifespan
from app.log import logger
from app.schemas.dremio import DremioContainer, DremioSource
from app.utils import with_semaphore

__cache: BaseCache | None = None


async def _init_cache() -> BaseCache:
    try:
        cache = RedisCache(
            endpoint=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
        )
        await cache.client.connection_pool.get_connection()
        logger.opt(colors=True).info("使用 <g>RedisCache</> 作为缓存")
    except Exception:
        logger.opt(colors=True).warning("<g>RedisCache</> 连接失败，使用 <g>SimpleMemoryCache</>")
        cache = SimpleMemoryCache()

    return cache


@with_semaphore(1)
async def _get_cache() -> BaseCache:
    global __cache
    if __cache is None:
        __cache = await _init_cache()
    return __cache


class _Cache[T]:
    def __init__(self, type_: type[T]) -> None:
        self._type = type_
        self._key = f"dremio_cache:{self._type.__name__}"

    async def aget(self) -> list[T] | None:
        cache = await _get_cache()
        value = await cache.get(self._key)
        if value is None:
            return None
        return [self._type(**item) for item in value]

    async def aset(self, value: list[T], ttl: int | None) -> None:
        cache = await _get_cache()
        await cache.set(
            self._key,
            [item.__dict__ for item in value],
            **({"ttl": ttl} if ttl is not None else {}),
        )

    async def aexpire(self) -> None:
        cache = await _get_cache()
        await cache.delete(self._key)

    def get(self) -> list[T] | None:
        return lifespan.from_thread(self.aget)

    def set(self, value: list[T], ttl: int | None) -> None:
        return lifespan.from_thread(self.aset, value, ttl)

    def expire(self) -> None:
        return lifespan.from_thread(self.aexpire)


lifespan.on_startup(_get_cache)
source_cache = _Cache(DremioSource)
container_cache = _Cache(DremioContainer)
