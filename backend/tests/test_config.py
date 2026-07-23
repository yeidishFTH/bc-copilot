from app.core.config import Settings


def test_default_database_url_uses_asyncpg() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+asyncpg://")
