from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.services.knowledge.models import KnowledgeSearchResult
from app.services.knowledge.persistence.repositories.search import (
    KnowledgeSearchRepository,
)


pytestmark = pytest.mark.asyncio


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self.rows = rows or []
        self.executed: list[Any] = []

    async def execute(self, statement: Any) -> FakeResult:
        self.executed.append(statement)
        return FakeResult(self.rows)


def make_row() -> SimpleNamespace:
    return SimpleNamespace(
        page_id=uuid4(),
        revision_id=uuid4(),
        chunk_id=uuid4(),
        wiki_page_id=101,
        wiki_revision_id=202,
        title="נוהל פתיחת סניף",
        canonical_url="https://wiki.example.test/opening",
        namespace_id=0,
        position=2,
        heading_path=["פתיחת סניף", "ספירת מזומן"],
        content="יש לבצע ספירת מזומן בתחילת המשמרת.",
        token_count=7,
        rank=0.875,
    )


async def test_search_chunks_returns_domain_results() -> None:
    row = make_row()
    session = FakeSession([row])
    repository = KnowledgeSearchRepository(
        session  # type: ignore[arg-type]
    )

    results = await repository.search_chunks(
        "  ספירת   מזומן  ",
        limit=5,
    )

    assert len(session.executed) == 1
    assert len(results) == 1

    result = results[0]

    assert isinstance(result, KnowledgeSearchResult)
    assert result.page_id == str(row.page_id)
    assert result.revision_id == str(row.revision_id)
    assert result.chunk_id == str(row.chunk_id)
    assert result.wiki_page_id == 101
    assert result.wiki_revision_id == 202
    assert result.title == "נוהל פתיחת סניף"
    assert result.heading_path == (
        "פתיחת סניף",
        "ספירת מזומן",
    )
    assert result.content == (
        "יש לבצע ספירת מזומן בתחילת המשמרת."
    )
    assert result.rank == pytest.approx(0.875)


async def test_search_chunks_returns_empty_list() -> None:
    session = FakeSession()
    repository = KnowledgeSearchRepository(
        session  # type: ignore[arg-type]
    )

    results = await repository.search_chunks("ציות")

    assert results == []
    assert len(session.executed) == 1


async def test_search_statement_uses_postgresql_full_text_search() -> None:
    statement = KnowledgeSearchRepository.build_search_statement(
        "ספירת מזומן",
        limit=8,
        namespace_ids=(0, 4, 0),
    )

    compiled_statement = statement.compile(
        dialect=postgresql.dialect(),
    )
    compiled_sql = str(compiled_statement)
    compiled_parameters = compiled_statement.params

    assert "plainto_tsquery" in compiled_sql
    assert "knowledge_chunks.search_vector @@" in compiled_sql
    assert "ts_rank_cd" in compiled_sql
    assert "knowledge_pages.is_active IS true" in compiled_sql
    assert (
        "knowledge_pages.latest_revision_id = "
        "knowledge_revisions.wiki_revision_id"
    ) in compiled_sql
    assert "knowledge_pages.namespace_id IN" in compiled_sql
    assert "LIMIT" in compiled_sql

    parameter_values = list(compiled_parameters.values())

    assert "simple" in parameter_values
    assert "ספירת מזומן" in parameter_values
    assert 8 in parameter_values
    assert [0, 4] in parameter_values


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
async def test_search_chunks_rejects_empty_query(
    query: str,
) -> None:
    session = FakeSession()
    repository = KnowledgeSearchRepository(
        session  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="query cannot be empty"):
        await repository.search_chunks(query)

    assert session.executed == []


async def test_search_chunks_rejects_non_string_query() -> None:
    session = FakeSession()
    repository = KnowledgeSearchRepository(
        session  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="query must be a string"):
        await repository.search_chunks(123)  # type: ignore[arg-type]

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
async def test_search_chunks_rejects_invalid_limit(
    limit: Any,
) -> None:
    session = FakeSession()
    repository = KnowledgeSearchRepository(
        session  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="limit"):
        await repository.search_chunks(
            "נוהל",
            limit=limit,
        )

    assert session.executed == []


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
async def test_search_chunks_rejects_invalid_namespaces(
    namespace_ids: Any,
) -> None:
    session = FakeSession()
    repository = KnowledgeSearchRepository(
        session  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="namespace_ids"):
        await repository.search_chunks(
            "נוהל",
            namespace_ids=namespace_ids,
        )

    assert session.executed == []
