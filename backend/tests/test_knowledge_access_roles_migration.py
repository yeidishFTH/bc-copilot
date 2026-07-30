from pathlib import Path


MIGRATION_PATH = Path(
    "alembic/versions/"
    "20260730_0007_knowledge_access_roles.py"
)


def migration_text() -> str:
    return MIGRATION_PATH.read_text(
        encoding="utf-8"
    )


def test_migration_is_linear() -> None:
    text = migration_text()

    assert (
        'revision: str = "20260730_0007"'
        in text
    )
    assert (
        'down_revision: str | None = '
        '"20260730_0006"'
        in text
    )


def test_migration_adds_access_roles_array() -> None:
    text = migration_text()

    assert '"access_roles"' in text
    assert "postgresql.ARRAY(sa.Text())" in text
    assert "nullable=False" in text
    assert "ARRAY[]::text[]" in text


def test_migration_creates_gin_index() -> None:
    text = migration_text()

    assert (
        '"ix_knowledge_revision_metadata_access_roles"'
        in text
    )
    assert 'postgresql_using="gin"' in text


def test_downgrade_removes_index_and_column() -> None:
    text = migration_text()

    assert "op.drop_index(" in text
    assert "op.drop_column(" in text
