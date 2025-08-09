from pathlib import Path

from dotenv import load_dotenv
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

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/db.sqlite3"

    # Docker Executor
    DOCKER_RUNNER_IMAGE: str | None = None

    # LLM config
    TEST_MODEL_NAME: str
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = None
    OLLAMA_API_URL: str | None = None

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


load_dotenv()
settings = Settings()  # pyright: ignore[reportCallIssue]
