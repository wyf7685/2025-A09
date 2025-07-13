from pathlib import Path

from dotenv import load_dotenv
from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/db.sqlite3"

    # LLM config
    TEST_MODEL_NAME: str
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str | None = None
    OLLAMA_API_URL: str | None = None

    # Dremio REST API config
    DREMIO_BASE_URL: HttpUrl
    DREMIO_USERNAME: str
    DREMIO_PASSWORD: SecretStr
    DREMIO_EXTERNAL_DIR: Path
    DREMIO_EXTERNAL_NAME: str


load_dotenv()
settings = Settings()  # pyright: ignore[reportCallIssue]
