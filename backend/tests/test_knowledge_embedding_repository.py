from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.services.knowledge import (
    EmbeddingVector,
)
from app.services.knowledge.persistence import (
    KnowledgeEmbeddingCandidate,
    KnowledgeEmbeddingRepository,
)


class FakeResult:
    def __init__(
        self,
        rows: list[object],
    ) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class FakeSession:
    def __init__(
        self,
        *,
        rows: list[object] | None = None,
    ) -> None:
        self.rows = rows or []
        self.executions: list[
            tuple[object, object | None]
        ] = []
        self.flushes = 0

    async def execute(
        self,
        statement: object,
        parameters: object | None = None,
    ) -> FakeResult:
        self.executions.append(
            (statement, parameters)
        )
        return FakeResult(self.rows)

    async def flush(self) -> None:
        self.flushes += 1


def make_vector(
    value: float = 0.1,
) -> EmbeddingVector:
    return EmbeddingVector(
        values=tuple(
            value
            for _ in range(
                KnowledgeEmbeddingRepository
                .EMBEDDING_DIMENSIONS
            )
        )
    )


@pytest.mark.asyncio
async def test_fetch_pending_maps_candidates() -> None:
    chunk_id = uuid.uuid4()
    session = FakeSession(
        rows=[
            SimpleNamespace(
                chunk_id=chunk_id,
                title="נוהל מחיקת כרטיס לקוח",
                heading_path=[
                    "שלבי ביצוע",
                    "מחיקה",
                ],
                content="יש לאתר את כרטיס הלקוח.",
                position=2,
            )
        ]
    )
    repository = KnowledgeEmbeddingRepository(
        session  # type: ignore[arg-type]
    )

    candidates = await repository.fetch_pending(
        limit=10
    )

    assert candidates == (
        KnowledgeEmbeddingCandidate(
            chunk_id=chunk_id,
            title="נוהל מחיקת כרטיס לקוח",
            heading_path=(
                "שלבי ביצוע",
                "מחיקה",
            ),
            content="יש לאתר את כרטיס הלקוח.",
            position=2,
        ),
    )


@pytest.mark.asyncio
async def test_fetch_pending_builds_stable_query() -> None:
    session = FakeSession()
    repository = KnowledgeEmbeddingRepository(
        session  # type: ignore[arg-type]
    )

    await repository.fetch_pending(limit=25)

    statement, parameters = session.executions[0]

    compiled = statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={
            "literal_binds": True,
        },
    )
    sql = " ".join(str(compiled).split())

    assert parameters is None
    assert "knowledge_chunks.embedding IS NULL" in sql
    assert "knowledge_pages.is_active IS true" in sql
    assert (
        "knowledge_pages.latest_revision_id = "
        "knowledge_revisions.wiki_revision_id"
    ) in sql
    assert "Archive/" in sql
    assert "Sandbox/" in sql
    assert "#redirect%" in sql
    assert "#הפניה%" in sql
    assert "ORDER BY knowledge_pages.title ASC" in sql
    assert "knowledge_chunks.position ASC" in sql
    assert "LIMIT 25" in sql


@pytest.mark.parametrize(
    "limit",
    [
        0,
        501,
        True,
        2.5,
    ],
)
@pytest.mark.asyncio
async def test_fetch_pending_rejects_invalid_limit(
    limit: Any,
) -> None:
    repository = KnowledgeEmbeddingRepository(
        FakeSession()  # type: ignore[arg-type]
    )

    with pytest.raises(
        ValueError,
        match="batch limit",
    ):
        await repository.fetch_pending(
            limit=limit,
        )


@pytest.mark.asyncio
async def test_store_embeddings_executes_bulk_update() -> None:
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    session = FakeSession()
    repository = KnowledgeEmbeddingRepository(
        session  # type: ignore[arg-type]
    )

    stored = await repository.store_embeddings(
        {
            first_id: make_vector(0.1),
            second_id: make_vector(0.2),
        }
    )

    assert stored == 2
    assert session.flushes == 1
    assert len(session.executions) == 1

    statement, parameters = session.executions[0]

    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )
    sql = " ".join(str(compiled).split())

    assert "UPDATE knowledge_chunks" in sql
    assert "embedding=%(embedding_values)s" in sql
    assert (
        "knowledge_chunks.id = "
        "%(target_chunk_id)s"
    ) in sql
    assert statement.table.name == "knowledge_chunks"
    assert statement.table is not None

    assert isinstance(parameters, list)
    assert len(parameters) == 2
    assert all(
        isinstance(
            item["target_chunk_id"],
            uuid.UUID,
        )
        for item in parameters
    )
    assert all(
        len(item["embedding_values"]) == 1536
        for item in parameters
    )


@pytest.mark.asyncio
async def test_store_embeddings_accepts_empty_mapping() -> None:
    session = FakeSession()
    repository = KnowledgeEmbeddingRepository(
        session  # type: ignore[arg-type]
    )

    stored = await repository.store_embeddings({})

    assert stored == 0
    assert session.executions == []
    assert session.flushes == 0


@pytest.mark.parametrize(
    "embeddings",
    [
        [],
        {"not-a-uuid": make_vector()},
        {uuid.uuid4(): "not-a-vector"},
        {
            uuid.uuid4(): EmbeddingVector(
                values=(0.1, 0.2)
            )
        },
    ],
)
@pytest.mark.asyncio
async def test_store_embeddings_rejects_invalid_values(
    embeddings: Any,
) -> None:
    repository = KnowledgeEmbeddingRepository(
        FakeSession()  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError):
        await repository.store_embeddings(
            embeddings
        )
