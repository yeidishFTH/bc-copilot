from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.knowledge.embeddings import (
    EmbeddingVector,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)
from app.services.knowledge.persistence.repositories.vector_search import (
    KnowledgeVectorSearchRepository,
)


class FakeResult:
    def __init__(
        self,
        rows: list[Any],
    ) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    def __init__(
        self,
        rows: list[Any] | None = None,
    ) -> None:
        self.rows = rows or []
        self.executed: list[Any] = []

    async def execute(
        self,
        statement: Any,
    ) -> FakeResult:
        self.executed.append(statement)
        return FakeResult(self.rows)


def make_embedding(
    value: float = 0.01,
) -> EmbeddingVector:
    return EmbeddingVector(
        values=tuple(
            value
            for _ in range(1536)
        )
    )


def make_row() -> SimpleNamespace:
    return SimpleNamespace(
        page_id=uuid4(),
        revision_id=uuid4(),
        chunk_id=uuid4(),
        wiki_page_id=101,
        wiki_revision_id=202,
        title="נוהל מחיקת כרטיס לקוח",
        canonical_url=(
            "https://wiki.example.test/"
            "delete-customer"
        ),
        namespace_id=0,
        position=2,
        heading_path=[
            "שלבי ביצוע",
            "מחיקה",
        ],
        content=(
            "יש לאתר את כרטיס הלקוח "
            "ולבצע את שלבי המחיקה."
        ),
        token_count=12,
        rank=0.925,
        distance=0.075,
        status="מאושר",
        document_type="נוהל",
        portal="לקוחות",
        category="לקוחות",
        audience=["נציג"],
        owner="תפעול",
        responsible_department="תפעול",
        updated_on=None,
        version="1.0",
    )


@pytest.mark.asyncio
async def test_search_chunks_returns_domain_results() -> None:
    row = make_row()
    session = FakeSession([row])

    repository = KnowledgeVectorSearchRepository(
        session  # type: ignore[arg-type]
    )

    results = await repository.search_chunks(
        make_embedding(),
        limit=5,
    )

    assert len(session.executed) == 1
    assert len(results) == 1

    result = results[0]

    assert isinstance(
        result,
        KnowledgeSearchResult,
    )
    assert result.page_id == str(row.page_id)
    assert result.revision_id == str(
        row.revision_id
    )
    assert result.chunk_id == str(row.chunk_id)
    assert result.title == (
        "נוהל מחיקת כרטיס לקוח"
    )
    assert result.heading_path == (
        "שלבי ביצוע",
        "מחיקה",
    )
    assert result.rank == pytest.approx(
        0.925
    )
    assert result.status == "מאושר"
    assert result.document_type == "נוהל"
    assert result.audience == ("נציג",)


@pytest.mark.asyncio
async def test_search_chunks_returns_empty_list() -> None:
    session = FakeSession()

    repository = KnowledgeVectorSearchRepository(
        session  # type: ignore[arg-type]
    )

    results = await repository.search_chunks(
        make_embedding()
    )

    assert results == []
    assert len(session.executed) == 1


def test_statement_uses_cosine_distance_and_similarity() -> None:
    statement = (
        KnowledgeVectorSearchRepository
        .build_search_statement(
            make_embedding(),
            limit=8,
            namespace_ids=(0, 4, 0),
        )
    )

    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )
    sql = " ".join(str(compiled).split())
    parameters = compiled.params
    parameter_values = list(
        parameters.values()
    )

    assert (
        "knowledge_chunks.embedding <=>"
        in sql
    )
    assert (
        "1.0 - "
        in sql
        or "%(param_" in sql
    )
    assert (
        "knowledge_chunks.embedding "
        "IS NOT NULL"
        in sql
    )
    assert (
        "knowledge_pages.is_active IS true"
        in sql
    )
    assert (
        "knowledge_pages.latest_revision_id = "
        "knowledge_revisions.wiki_revision_id"
        in sql
    )
    assert (
        "knowledge_pages.namespace_id IN"
        in sql
    )
    assert "Archive/" in parameter_values
    assert "Sandbox/" in parameter_values
    assert "#redirect%" in parameter_values
    assert "#הפניה%" in parameter_values
    assert [0, 4] in parameter_values
    assert 8 in parameter_values


def test_statement_orders_by_highest_similarity() -> None:
    statement = (
        KnowledgeVectorSearchRepository
        .build_search_statement(
            make_embedding(),
            limit=5,
        )
    )

    compiled = statement.compile(
        dialect=postgresql.dialect(),
    )
    sql = " ".join(str(compiled).split())

    assert "ORDER BY rank DESC" in sql
    assert (
        "knowledge_pages.title ASC"
        in sql
    )
    assert (
        "knowledge_chunks.position ASC"
        in sql
    )


@pytest.mark.parametrize(
    "embedding",
    [
        None,
        [0.1] * 1536,
        EmbeddingVector(
            values=(0.1, 0.2)
        ),
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_embedding(
    embedding: Any,
) -> None:
    session = FakeSession()

    repository = KnowledgeVectorSearchRepository(
        session  # type: ignore[arg-type]
    )

    with pytest.raises(
        ValueError,
        match="query_embedding",
    ):
        await repository.search_chunks(
            embedding
        )

    assert session.executed == []


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        101,
        True,
        1.5,
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_limit(
    limit: Any,
) -> None:
    repository = KnowledgeVectorSearchRepository(
        FakeSession()  # type: ignore[arg-type]
    )

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        await repository.search_chunks(
            make_embedding(),
            limit=limit,
        )


@pytest.mark.parametrize(
    "namespace_ids",
    [
        (),
        [],
        (-1,),
        (True,),
        ("0",),
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_namespaces(
    namespace_ids: Any,
) -> None:
    repository = KnowledgeVectorSearchRepository(
        FakeSession()  # type: ignore[arg-type]
    )

    with pytest.raises(
        ValueError,
        match="namespace_ids",
    ):
        await repository.search_chunks(
            make_embedding(),
            namespace_ids=namespace_ids,
        )
