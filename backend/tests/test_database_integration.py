import pytest
from sqlalchemy import text

from app.db.session import AsyncSessionFactory


pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_database_connection() -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


async def test_initial_migration_tables_exist() -> None:
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    )

    async with AsyncSessionFactory() as session:
        result = await session.execute(query)

    tables = {row[0] for row in result.fetchall()}
    expected = {
        "alembic_version",
        "knowledge_pages",
        "knowledge_revisions",
        "knowledge_content",
        "knowledge_chunks",
        "knowledge_categories",
        "knowledge_page_categories",
        "knowledge_links",
        "sync_runs",
        "sync_page_events",
    }

    assert expected.issubset(tables)
