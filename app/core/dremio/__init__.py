from .abstract import AbstractDremioClient as AbstractDremioClient

_client: AbstractDremioClient | None = None


def get_dremio_client() -> AbstractDremioClient:
    from app.log import logger

    global _client

    if _client is None:
        try:
            from .flight import DremioFlightClient

            _client = DremioFlightClient()

        except Exception:
            logger.warning("使用Flight客户端连接Dremio失败，尝试使用REST客户端")
            from .rest import DremioRestClient

            _client = DremioRestClient()

    return _client


__all__ = ["AbstractDremioClient", "get_dremio_client"]
