import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOST: str = "0.0.0.0"  # noqa: S104
    PORT: int = 8081

    # JWT 配置
    JWT_SECRET_KEY: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # 管理员账号
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: SecretStr

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/db.sqlite3"

    # Docker Executor
    DOCKER_RUNNER_IMAGE: str | None = None
    EXECUTOR_DATA_DIR: Path | None = None

    # Dremio REST API config
    DREMIO_BASE_URL: str = "http://localhost"
    DREMIO_REST_PORT: int = 9047
    DREMIO_FLIGHT_PORT: int = 32010
    DREMIO_USERNAME: str
    DREMIO_PASSWORD: SecretStr
    DREMIO_EXTERNAL_DIR: Path
    DREMIO_EXTERNAL_NAME: str

    @property
    def DREMIO_REST_URL(self) -> URL:  # noqa: N802
        return URL(self.DREMIO_BASE_URL).with_port(self.DREMIO_REST_PORT)

    # FastAPI CORS
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:5173",  # Vue 开发服务器默认端口
        "http://localhost:8081",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: SecretStr | None = None


if os.getenv("APP_SKIP_DOTENV", "false").lower() != "true" and Path(".env").exists():
    from dotenv import load_dotenv

    load_dotenv(".env")

settings = Settings()  # pyright: ignore[reportCallIssue]

__all__ = ["settings"]
