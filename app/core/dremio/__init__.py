from .rest import DremioClient as DremioClient
from .rest import DremioSource as DremioSource

_client: DremioClient | None = None


def get_dremio_client() -> DremioClient:
    global _client
    if _client is None:
        _client = DremioClient()
    return _client
