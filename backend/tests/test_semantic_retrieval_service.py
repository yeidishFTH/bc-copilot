from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from app.services.knowledge.embeddings import (
    EmbeddingVector,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)
from app.services.knowledge.retrieval.semantic import (
    SemanticRetrievalService,
)


def make_vector(
    value: float = 0.01,
) -> EmbeddingVector:
    return EmbeddingVector(
        values=tuple(
            value
            for _ in range(1536)
        )
    )


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
        title="נוהל מחיקת כרטיס לקוח",
        canonical_url=(
            "https://wiki.example.test/delete-customer"
        ),
        namespace_id=0,
        position=0,
        heading_path=("שלבי ביצוע",),
        content="יש לבצע את שלבי המחיקה.",
        token_count=6,
        rank=rank,
    )


class RecordingGenerator:
    model_id = "recording"
    dimensions = 1536

    def __init__(
        self,
        vectors: tuple[EmbeddingVector, ...] | None = None,
    ) -> None:
        self.vectors = (
            (make_vector(),)
            if vectors is None
            else vectors
        )
        self.calls: list[tuple[str, ...]] = []

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        normalized = tuple(texts)
        self.calls.append(normalized)
        return self.vectors


class RecordingVectorSearch:
    def __init__(
        self,
        results: Sequence[KnowledgeSearchResult] = (),
    ) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def search_chunks(
        self,
        query_embedding: EmbeddingVector,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> list[KnowledgeSearchResult]:
        self.calls.append(
            {
                "embedding": query_embedding,
                "limit": limit,
                "namespace_ids": namespace_ids,
            }
        )
        return list(self.results)


@pytest.mark.asyncio
async def test_search_embeds_and_forwards_query() -> None:
    generator = RecordingGenerator()
    vector_search = RecordingVectorSearch(
        [
            make_result(
                chunk_id="chunk-1"
            )
        ]
    )

    service = SemanticRetrievalService(
        generator=generator,
        search=vector_search,
    )

    results = await service.search(
        "  איך   מוחקים לקוח?  ",
        limit=5,
        namespace_ids=[0, 4, 0],
    )

    assert generator.calls == [
        ("איך מוחקים לקוח?",)
    ]
    assert len(vector_search.calls) == 1

    call = vector_search.calls[0]

    assert call["embedding"] == make_vector()
    assert call["limit"] == 5
    assert call["namespace_ids"] == (0, 4)
    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"


@pytest.mark.asyncio
async def test_search_deduplicates_chunks() -> None:
    duplicate = make_result(
        chunk_id="chunk-1"
    )

    service = SemanticRetrievalService(
        generator=RecordingGenerator(),
        search=RecordingVectorSearch(
            [
                duplicate,
                duplicate,
                make_result(
                    chunk_id="chunk-2",
                    rank=0.8,
                ),
            ]
        ),
    )

    results = await service.search(
        "מחיקת לקוח"
    )

    assert [
        result.chunk_id
        for result in results
    ] == [
        "chunk-1",
        "chunk-2",
    ]


@pytest.mark.asyncio
async def test_search_returns_empty_tuple() -> None:
    service = SemanticRetrievalService(
        generator=RecordingGenerator(),
        search=RecordingVectorSearch(),
    )

    results = await service.search(
        "ציות"
    )

    assert results == ()


@pytest.mark.asyncio
async def test_generator_count_must_match_one_query() -> None:
    service = SemanticRetrievalService(
        generator=RecordingGenerator(
            vectors=(),
        ),
        search=RecordingVectorSearch(),
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected number",
    ):
        await service.search(
            "מחיקת לקוח"
        )


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
    generator = RecordingGenerator()
    vector_search = RecordingVectorSearch()

    service = SemanticRetrievalService(
        generator=generator,
        search=vector_search,
    )

    with pytest.raises(
        ValueError,
        match="query cannot be empty",
    ):
        await service.search(query)

    assert generator.calls == []
    assert vector_search.calls == []


@pytest.mark.asyncio
async def test_rejects_non_string_query() -> None:
    service = SemanticRetrievalService(
        generator=RecordingGenerator(),
        search=RecordingVectorSearch(),
    )

    with pytest.raises(
        ValueError,
        match="query must be a string",
    ):
        await service.search(
            123  # type: ignore[arg-type]
        )


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
    service = SemanticRetrievalService(
        generator=RecordingGenerator(),
        search=RecordingVectorSearch(),
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
    service = SemanticRetrievalService(
        generator=RecordingGenerator(),
        search=RecordingVectorSearch(),
    )

    with pytest.raises(
        ValueError,
        match="namespace_ids",
    ):
        await service.search(
            "נוהל",
            namespace_ids=namespace_ids,
        )


def test_requires_embedding_generator_protocol() -> None:
    with pytest.raises(
        TypeError,
        match="generator",
    ):
        SemanticRetrievalService(
            generator=object(),  # type: ignore[arg-type]
            search=RecordingVectorSearch(),
        )


def test_requires_vector_search_protocol() -> None:
    with pytest.raises(
        TypeError,
        match="search",
    ):
        SemanticRetrievalService(
            generator=RecordingGenerator(),
            search=object(),  # type: ignore[arg-type]
        )
