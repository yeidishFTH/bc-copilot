from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from app.services.knowledge.models import KnowledgeSearchResult
from app.services.knowledge.retrieval import (
    KnowledgeContextBuilder,
    KnowledgeContextService,
)


def make_result(
    *,
    chunk_id: str,
    page_id: str = "page-1",
    title: str = "נוהל זיהוי ואימות לקוח",
    heading_path: tuple[str, ...] = ("שלבי ביצוע",),
    content: str = "יש לזהות ולאמת את הלקוח לפני מתן השירות.",
    rank: float = 1.25,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        page_id=page_id,
        revision_id=f"revision-{page_id}",
        chunk_id=chunk_id,
        wiki_page_id=101,
        wiki_revision_id=202,
        title=title,
        canonical_url=f"https://wiki.example.test/{page_id}",
        namespace_id=0,
        position=0,
        heading_path=heading_path,
        content=content,
        token_count=None,
        rank=rank,
    )


def test_builder_creates_source_aware_context() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build(
        "  זיהוי   לקוח  ",
        [
            make_result(chunk_id="chunk-1"),
            make_result(
                chunk_id="chunk-2",
                page_id="page-2",
                title="יצירת עסקה",
                heading_path=("שלב 1",),
                content="יש לבדוק שהלקוח במצב Verified.",
                rank=1.0,
            ),
        ],
    )

    assert context.query == "זיהוי לקוח"
    assert len(context.sources) == 2
    assert context.sources[0].index == 1
    assert context.sources[1].index == 2
    assert "[SOURCE 1]" in context.text
    assert "כותרת: נוהל זיהוי ואימות לקוח" in context.text
    assert "סעיף: שלבי ביצוע" in context.text
    assert "https://wiki.example.test/page-1" in context.text
    assert context.character_count == len(context.text)
    assert context.estimated_tokens > 0
    assert context.truncated is False


def test_builder_limits_chunks_from_same_page() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build(
        "לקוח",
        [
            make_result(chunk_id="chunk-1"),
            make_result(
                chunk_id="chunk-2",
                heading_path=("אחריות",),
            ),
            make_result(
                chunk_id="chunk-3",
                heading_path=("צ׳קליסט",),
            ),
            make_result(
                chunk_id="chunk-4",
                page_id="page-2",
                title="יצירת עסקה",
            ),
        ],
        max_chunks_per_page=2,
    )

    assert [source.chunk_id for source in context.sources] == [
        "chunk-1",
        "chunk-2",
        "chunk-4",
    ]
    assert context.truncated is True


def test_builder_removes_duplicate_chunk_ids() -> None:
    builder = KnowledgeContextBuilder()
    duplicate = make_result(chunk_id="chunk-1")

    context = builder.build(
        "לקוח",
        [duplicate, duplicate],
    )

    assert len(context.sources) == 1
    assert context.truncated is False


def test_builder_removes_duplicate_content_from_same_section() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build(
        "לקוח",
        [
            make_result(chunk_id="chunk-1"),
            make_result(
                chunk_id="chunk-2",
                content=(
                    "  יש לזהות ולאמת את הלקוח "
                    "לפני מתן השירות.  "
                ),
            ),
        ],
    )

    assert len(context.sources) == 1


def test_builder_enforces_max_chunks() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build(
        "נוהל",
        [
            make_result(
                chunk_id=f"chunk-{index}",
                page_id=f"page-{index}",
            )
            for index in range(1, 6)
        ],
        max_chunks=2,
    )

    assert len(context.sources) == 2
    assert context.truncated is True


def test_builder_truncates_first_source_to_character_budget() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build(
        "נוהל",
        [
            make_result(
                chunk_id="chunk-1",
                content="א" * 2_000,
            )
        ],
        max_characters=500,
    )

    assert len(context.sources) == 1
    assert context.character_count <= 500
    assert context.sources[0].content.endswith("…")
    assert context.truncated is True


def test_builder_stops_before_exceeding_budget() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build(
        "נוהל",
        [
            make_result(
                chunk_id="chunk-1",
                page_id="page-1",
                content="א" * 250,
            ),
            make_result(
                chunk_id="chunk-2",
                page_id="page-2",
                content="ב" * 400,
            ),
        ],
        max_characters=500,
    )

    assert len(context.sources) == 1
    assert context.character_count <= 500
    assert context.truncated is True


def test_builder_returns_empty_context_for_no_results() -> None:
    builder = KnowledgeContextBuilder()

    context = builder.build("לא נמצא", [])

    assert context.text == ""
    assert context.sources == ()
    assert context.character_count == 0
    assert context.estimated_tokens == 0
    assert context.truncated is False


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("query", {"query": "   "}),
        ("max_characters", {"max_characters": 499}),
        ("max_characters", {"max_characters": True}),
        ("max_chunks", {"max_chunks": 0}),
        ("max_chunks", {"max_chunks": 51}),
        ("max_chunks_per_page", {"max_chunks_per_page": 0}),
    ],
)
def test_builder_rejects_invalid_arguments(
    field_name: str,
    kwargs: dict[str, Any],
) -> None:
    builder = KnowledgeContextBuilder()
    arguments: dict[str, Any] = {
        "query": "נוהל",
        "results": [],
    }
    arguments.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        builder.build(**arguments)


class FakeRetrieval:
    def __init__(
        self,
        results: Sequence[KnowledgeSearchResult],
    ) -> None:
        self.results = tuple(results)
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        self.calls.append(
            {
                "query": query,
                "limit": limit,
                "namespace_ids": namespace_ids,
            }
        )
        return self.results


@pytest.mark.asyncio
async def test_context_service_retrieves_candidates_and_builds_context() -> None:
    retrieval = FakeRetrieval(
        [make_result(chunk_id="chunk-1")]
    )
    service = KnowledgeContextService(retrieval)

    context = await service.build_context(
        "זיהוי לקוח",
        search_limit=20,
        namespace_ids=[0],
        max_chunks=5,
    )

    assert retrieval.calls == [
        {
            "query": "זיהוי לקוח",
            "limit": 20,
            "namespace_ids": [0],
        }
    ]
    assert len(context.sources) == 1


@pytest.mark.asyncio
async def test_context_service_rejects_invalid_search_limit() -> None:
    retrieval = FakeRetrieval([])
    service = KnowledgeContextService(retrieval)

    with pytest.raises(ValueError, match="search_limit"):
        await service.build_context(
            "נוהל",
            search_limit=101,
        )

    assert retrieval.calls == []
