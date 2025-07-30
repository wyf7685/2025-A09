from app.schemas.dremio import DremioContainer, DremioSource


class _Cache[T]:
    def __init__(self) -> None:
        self._value: T | None = None

    def get(self) -> T | None:
        return self._value

    def set(self, value: T) -> None:
        self._value = value

    def expire(self) -> None:
        self._value = None


source_cache = _Cache[list[DremioSource]]()
container_cache = _Cache[list[DremioContainer]]()
