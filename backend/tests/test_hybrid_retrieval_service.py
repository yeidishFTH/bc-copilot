from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest

from app.services.knowledge.models import (
    KnowledgeSearchResult,
)
from app.services.knowledge.retrieval.hybrid import (
    HybridRetrievalService,
)


def make_result(
    *,
    chunk_id: str,
    title: str | None = None,
    position: int = 0,
    rank: float = 1.0,
    document_type: str | None = None,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        page_id=f"page-{chunk_id}",
        revision_id=f"revision-{chunk_id}",
        chunk_id=chunk_id,
        wiki_page_id=101,
        wiki_revision_id=202,
        title=title or f"Document {chunk_id}",
        canonical_url=(
            f"https://wiki.example.test/{chunk_id}"
        ),
        namespace_id=0,
        position=position,
        heading_path=("סעיף",),
        content=f"תוכן {chunk_id}",
        token_count=3,
        rank=rank,
        document_type=document_type,
    )


class RecordingRetriever:
    def __init__(
        self,
        results: Sequence[
            KnowledgeSearchResult
        ] = (),
        *,
        delay: float = 0.0,
    ) -> None:
        self.results = tuple(results)
        self.delay = delay
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

        if self.delay:
            await asyncio.sleep(self.delay)

        return self.results[:limit]


@pytest.mark.asyncio
async def test_search_runs_and_fuses_retrievers() -> None:
    lexical = RecordingRetriever(
        (
            make_result(chunk_id="shared"),
            make_result(chunk_id="lexical"),
        )
    )
    semantic = RecordingRetriever(
        (
            make_result(chunk_id="semantic"),
            make_result(chunk_id="shared"),
        )
    )

    service = HybridRetrievalService(
        lexical=lexical,
        semantic=semantic,
    )

    results = await service.search(
        "  מחיקת   לקוח  ",
        limit=3,
        namespace_ids=[0, 4, 0],
    )

    assert lexical.calls == [
        {
            "query": "מחיקת לקוח",
            "limit": 9,
            "namespace_ids": (0, 4),
        }
    ]
    assert semantic.calls == lexical.calls

    assert [
        result.chunk_id
        for result in results
    ] == [
        "shared",
        "semantic",
        "lexical",
    ]

    assert results[0].rank > results[1].rank
    assert results[0].rank > results[2].rank


def test_fusion_rewards_overlap() -> None:
    shared = make_result(chunk_id="shared")
    lexical_only = make_result(
        chunk_id="lexical"
    )
    semantic_only = make_result(
        chunk_id="semantic"
    )

    results = HybridRetrievalService._fuse(
        (
            lexical_only,
            shared,
        ),
        (
            semantic_only,
            shared,
        ),
        limit=3,
        rrf_constant=60,
    )

    assert results[0].chunk_id == "shared"
    assert results[0].rank == pytest.approx(
        (1 / 62) + (1 / 62)
    )


def test_fusion_ignores_duplicate_list_entries() -> None:
    duplicate = make_result(
        chunk_id="duplicate"
    )

    results = HybridRetrievalService._fuse(
        (
            duplicate,
            duplicate,
        ),
        (),
        limit=5,
        rrf_constant=60,
    )

    assert len(results) == 1
    assert results[0].rank == pytest.approx(
        1 / 61
    )


def test_fusion_prefers_richer_metadata() -> None:
    lexical = make_result(
        chunk_id="shared",
        document_type=None,
    )
    semantic = make_result(
        chunk_id="shared",
        document_type="נוהל",
    )

    results = HybridRetrievalService._fuse(
        (lexical,),
        (semantic,),
        limit=1,
        rrf_constant=60,
    )

    assert results[0].document_type == "נוהל"


@pytest.mark.asyncio
async def test_search_returns_empty_tuple() -> None:
    service = HybridRetrievalService(
        lexical=RecordingRetriever(),
        semantic=RecordingRetriever(),
    )

    results = await service.search(
        "ציות"
    )

    assert results == ()


@pytest.mark.asyncio
async def test_search_executes_retrievers_concurrently() -> None:
    lexical = RecordingRetriever(
        delay=0.05
    )
    semantic = RecordingRetriever(
        delay=0.05
    )

    service = HybridRetrievalService(
        lexical=lexical,
        semantic=semantic,
    )

    loop = asyncio.get_running_loop()
    started = loop.time()

    await service.search("בדיקה")

    elapsed = loop.time() - started

    assert elapsed < 0.09


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\n\t",
    ],
)
@pytest.mark.asyncio
async def test_rejects_empty_query(
    query: str,
) -> None:
    lexical = RecordingRetriever()
    semantic = RecordingRetriever()

    service = HybridRetrievalService(
        lexical=lexical,
        semantic=semantic,
    )

    with pytest.raises(
        ValueError,
        match="query cannot be empty",
    ):
        await service.search(query)

    assert lexical.calls == []
    assert semantic.calls == []


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
    service = HybridRetrievalService(
        lexical=RecordingRetriever(),
        semantic=RecordingRetriever(),
    )

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        await service.search(
            "נוהל",
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
    service = HybridRetrievalService(
        lexical=RecordingRetriever(),
        semantic=RecordingRetriever(),
    )

    with pytest.raises(
        ValueError,
        match="namespace_ids",
    ):
        await service.search(
            "נוהל",
            namespace_ids=namespace_ids,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("rrf_constant", 0),
        ("rrf_constant", True),
        ("candidate_multiplier", 0),
        ("candidate_multiplier", 11),
    ],
)
def test_rejects_invalid_configuration(
    field_name: str,
    value: Any,
) -> None:
    arguments = {
        "lexical": RecordingRetriever(),
        "semantic": RecordingRetriever(),
        field_name: value,
    }

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        HybridRetrievalService(**arguments)


def test_requires_lexical_protocol() -> None:
    with pytest.raises(
        TypeError,
        match="lexical",
    ):
        HybridRetrievalService(
            lexical=object(),  # type: ignore[arg-type]
            semantic=RecordingRetriever(),
        )


def test_requires_semantic_protocol() -> None:
    with pytest.raises(
        TypeError,
        match="semantic",
    ):
        HybridRetrievalService(
            lexical=RecordingRetriever(),
            semantic=object(),  # type: ignore[arg-type]
        )
