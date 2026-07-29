from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bitcoin Change Copilot API"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:3000"

    database_url: str = (
        "postgresql+asyncpg://bc_copilot:bc_copilot_dev_password"
        "@localhost:5432/bc_copilot"
    )
    database_echo: bool = False

    mediawiki_api_url: str = "https://wiki.bitcoinchange.co.il/api.php"
    mediawiki_bot_username: str | None = None
    mediawiki_bot_password: SecretStr | None = None

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6"
    openai_timeout_seconds: float = 60.0

    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    openai_embedding_batch_size: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
