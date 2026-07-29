from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from pgvector.sqlalchemy import Vector

from app.db.models import KnowledgeChunk


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260729_0004_chunk_embeddings.py"
)


def load_migration() -> Any:
    specification = (
        importlib.util.spec_from_file_location(
            "chunk_embedding_migration",
            MIGRATION_PATH,
        )
    )

    if (
        specification is None
        or specification.loader is None
    ):
        raise RuntimeError(
            "could not load embedding migration"
        )

    module = importlib.util.module_from_spec(
        specification
    )
    specification.loader.exec_module(module)

    return module


def test_chunk_model_has_nullable_vector_column() -> None:
    column = KnowledgeChunk.__table__.c.embedding

    assert isinstance(column.type, Vector)
    assert column.type.dim == 1536
    assert column.nullable is True


def test_migration_metadata_is_linear() -> None:
    migration = load_migration()

    assert migration.revision == "20260729_0004"
    assert migration.down_revision == "20260726_0003"
    assert migration.EMBEDDING_DIMENSIONS == 1536


def test_migration_enables_vector_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration()
    executed: list[str] = []
    columns: list[tuple[str, Any]] = []

    monkeypatch.setattr(
        migration.op,
        "execute",
        executed.append,
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: columns.append(
            (table, column)
        ),
    )

    migration.upgrade()

    assert executed == [
        "CREATE EXTENSION IF NOT EXISTS vector"
    ]
    assert len(columns) == 1

    table_name, column = columns[0]

    assert table_name == "knowledge_chunks"
    assert column.name == "embedding"
    assert isinstance(column.type, Vector)
    assert column.type.dim == 1536
    assert column.nullable is True


def test_migration_downgrade_drops_embedding_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration()
    dropped: list[tuple[str, str]] = []

    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped.append(
            (table, column)
        ),
    )

    migration.downgrade()

    assert dropped == [
        ("knowledge_chunks", "embedding")
    ]
