from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from app.services.knowledge.models import KnowledgeSearchResult
from app.services.knowledge.retrieval import (
    KnowledgeRetrievalService,
)


pytestmark = pytest.mark.asyncio


def make_result(
    *,
    chunk_id: str,
    rank: float = 0.9,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        page_id="page-1",
        revision_id="revision-1",
        chunk_id=chunk_id,
        wiki_page_id=101,
        wiki_revision_id=202,
        title="נוהל פתיחת סניף",
        canonical_url="https://wiki.example.test/opening",
        namespace_id=0,
        position=0,
        heading_path=("פתיחת סניף", "ספירת מזומן"),
        content="יש לבצע ספירת מזומן בתחילת המשמרת.",
        token_count=7,
        rank=rank,
    )


class FakeSearchReader:
    def __init__(
        self,
        results: Sequence[KnowledgeSearchResult] = (),
    ) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def search_chunks(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> list[KnowledgeSearchResult]:
        self.calls.append(
            {
                "query": query,
                "limit": limit,
                "namespace_ids": namespace_ids,
            }
        )
        return list(self.results)


async def test_search_normalizes_and_forwards_request() -> None:
    reader = FakeSearchReader([make_result(chunk_id="chunk-1")])
    service = KnowledgeRetrievalService(reader)

    results = await service.search(
        "  ספירת   מזומן  ",
        limit=5,
        namespace_ids=[0, 4, 0],
    )

    assert len(results) == 1
    assert reader.calls == [
        {
            "query": "ספירת מזומן",
            "limit": 5,
            "namespace_ids": (0, 4),
        }
    ]


async def test_search_removes_duplicate_chunks() -> None:
    duplicate = make_result(chunk_id="chunk-1")

    reader = FakeSearchReader(
        [
            duplicate,
            duplicate,
            make_result(chunk_id="chunk-2", rank=0.8),
        ]
    )
    service = KnowledgeRetrievalService(reader)

    results = await service.search("פתיחת סניף")

    assert [result.chunk_id for result in results] == [
        "chunk-1",
        "chunk-2",
    ]


async def test_search_returns_empty_tuple() -> None:
    reader = FakeSearchReader()
    service = KnowledgeRetrievalService(reader)

    results = await service.search("ציות")

    assert results == ()


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
async def test_search_rejects_empty_query(query: str) -> None:
    reader = FakeSearchReader()
    service = KnowledgeRetrievalService(reader)

    with pytest.raises(ValueError, match="query cannot be empty"):
        await service.search(query)

    assert reader.calls == []


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
async def test_search_rejects_invalid_limit(limit: Any) -> None:
    reader = FakeSearchReader()
    service = KnowledgeRetrievalService(reader)

    with pytest.raises(ValueError, match="limit"):
        await service.search(
            "נוהל",
            limit=limit,
        )

    assert reader.calls == []


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
async def test_search_rejects_invalid_namespaces(
    namespace_ids: Any,
) -> None:
    reader = FakeSearchReader()
    service = KnowledgeRetrievalService(reader)

    with pytest.raises(ValueError, match="namespace_ids"):
        await service.search(
            "נוהל",
            namespace_ids=namespace_ids,
        )

    assert reader.calls == []
