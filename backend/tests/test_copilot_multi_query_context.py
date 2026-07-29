from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.services.copilot.multi_query_context import (
    MultiQueryKnowledgeContextService,
)
from app.services.copilot.multi_query_retrieval import (
    MultiQueryRetrievalResult,
)
from app.services.copilot.query_rewriter import (
    QueryRewrite,
)
from app.services.copilot.planner import (
    RetrievalStrategy,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)


def make_result(
    *,
    chunk_id: str,
    title: str,
    rank: float,
    position: int = 0,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        page_id=f"page-{chunk_id}",
        revision_id=f"revision-{chunk_id}",
        chunk_id=chunk_id,
        wiki_page_id=101,
        wiki_revision_id=202,
        title=title,
        canonical_url=(
            f"https://wiki.example.test/{chunk_id}"
        ),
        namespace_id=0,
        position=position,
        heading_path=(
            title,
            "שלבי ביצוע",
        ),
        content=(
            f"תוכן מפורט עבור {title}. "
            "זהו קטע ידע שנועד לבדיקת בניית ההקשר."
        ),
        token_count=14,
        rank=rank,
    )


class FakeMultiQueryRetrieval:
    def __init__(
        self,
        results: tuple[KnowledgeSearchResult, ...],
    ) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        query: str,
        *,
        limit: int = 30,
        per_query_limit: int = 20,
        max_queries: int = 5,
        namespace_ids: Sequence[int] | None = None,
    ) -> MultiQueryRetrievalResult:
        self.calls.append(
            {
                "query": query,
                "limit": limit,
                "per_query_limit": per_query_limit,
                "max_queries": max_queries,
                "namespace_ids": (
                    tuple(namespace_ids)
                    if namespace_ids is not None
                    else None
                ),
            }
        )

        rewrite = QueryRewrite(
            original_query=query,
            normalized_query=query,
            search_queries=(query,),
            matched_aliases=(),
            matched_document_names=(),
        )

        limited_results = self.results[:limit]

        return MultiQueryRetrievalResult(
            rewrite=rewrite,
            results=limited_results,
            executed_queries=(query,),
            raw_result_count=len(limited_results),
            unique_result_count=len(limited_results),
        )


@pytest.mark.asyncio
async def test_builds_context_from_multi_query_results() -> None:
    retrieval = FakeMultiQueryRetrieval(
        (
            make_result(
                chunk_id="one",
                title="נוהל מחיקת כרטיס לקוח",
                rank=8.5,
            ),
            make_result(
                chunk_id="two",
                title="נוהל זיהוי ואימות לקוח",
                rank=5.0,
            ),
        )
    )

    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context(
        "איך מוחקים לקוח?",
        search_limit=14,
        namespace_ids=(0,),
        max_characters=5_000,
        max_chunks=4,
        max_chunks_per_page=2,
    )

    assert len(context.sources) == 2
    assert context.sources[0].chunk_id == "one"
    assert "נוהל מחיקת כרטיס לקוח" in context.text

    call = retrieval.calls[-1]

    assert call["query"] == "איך מוחקים לקוח?"
    assert call["limit"] == 14
    assert call["per_query_limit"] == 14
    assert call["max_queries"] == 5
    assert call["namespace_ids"] == (0,)


@pytest.mark.asyncio
async def test_caps_per_query_limit() -> None:
    retrieval = FakeMultiQueryRetrieval(())
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    await service.build_context(
        "סכם לי את הנוהל",
        search_limit=45,
    )

    call = retrieval.calls[-1]

    assert call["limit"] == 45
    assert call["per_query_limit"] == 30


@pytest.mark.asyncio
async def test_preserves_context_limits() -> None:
    retrieval = FakeMultiQueryRetrieval(
        tuple(
            make_result(
                chunk_id=f"chunk-{index}",
                title=f"מסמך {index}",
                rank=10.0 - index,
                position=index,
            )
            for index in range(8)
        )
    )

    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context(
        "שאלה",
        max_chunks=3,
        max_chunks_per_page=2,
    )

    assert len(context.sources) == 3


@pytest.mark.asyncio
async def test_rejects_invalid_search_limit() -> None:
    retrieval = FakeMultiQueryRetrieval(())
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    with pytest.raises(
        ValueError,
        match="search_limit",
    ):
        await service.build_context(
            "שאלה",
            search_limit=0,
        )


def make_typed_result(
    *,
    chunk_id: str,
    title: str,
    rank: float,
    document_type: str,
    page_id: str | None = None,
) -> KnowledgeSearchResult:
    result = make_result(
        chunk_id=chunk_id,
        title=title,
        rank=rank,
    )

    from dataclasses import replace

    return replace(
        result,
        page_id=page_id or result.page_id,
        document_type=document_type,
    )


@pytest.mark.asyncio
async def test_checklist_strategy_promotes_checklist() -> None:
    procedure = make_typed_result(
        chunk_id="procedure",
        title="נוהל בקרה",
        rank=5.0,
        document_type="נוהל",
    )
    checklist = make_typed_result(
        chunk_id="checklist",
        title="צ'קליסט פתיחת ותחזוקת סניף",
        rank=4.0,
        document_type="צ'קליסט",
    )

    retrieval = FakeMultiQueryRetrieval(
        (procedure, checklist)
    )
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context_with_strategy(
        "מהן המשימות בתחילת משמרת בוקר?",
        strategy=RetrievalStrategy.CHECKLIST_FIRST,
    )

    assert context.sources[0].chunk_id == "checklist"


@pytest.mark.asyncio
async def test_system_strategy_promotes_system_guide() -> None:
    procedure = make_typed_result(
        chunk_id="procedure",
        title="נוהל כללי",
        rank=5.0,
        document_type="נוהל",
    )
    system = make_typed_result(
        chunk_id="system",
        title="מערכת Salesforce",
        rank=4.0,
        document_type="מדריך מערכת",
    )

    retrieval = FakeMultiQueryRetrieval(
        (procedure, system)
    )
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context_with_strategy(
        "איך עובדים עם Accounts בסיילספורס?",
        strategy=RetrievalStrategy.SYSTEM_FIRST,
    )

    assert context.sources[0].chunk_id == "system"


@pytest.mark.asyncio
async def test_overview_strategy_prefers_knowledge_page() -> None:
    procedure = make_typed_result(
        chunk_id="procedure",
        title="נוהל ציות",
        rank=5.0,
        document_type="נוהל",
    )
    overview = make_typed_result(
        chunk_id="overview",
        title="ציות ורגולציה",
        rank=4.0,
        document_type="פורטל",
    )

    retrieval = FakeMultiQueryRetrieval(
        (procedure, overview)
    )
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context_with_strategy(
        "מה המשמעות של ציות ורגולציה?",
        strategy=RetrievalStrategy.OVERVIEW_FIRST,
    )

    assert context.sources[0].chunk_id == "overview"


@pytest.mark.asyncio
async def test_multi_document_strategy_diversifies_pages() -> None:
    first_page_one = make_typed_result(
        chunk_id="page-one-a",
        title="מסמך ראשון",
        rank=10.0,
        document_type="נוהל",
        page_id="page-one",
    )
    second_page_one = make_typed_result(
        chunk_id="page-one-b",
        title="מסמך ראשון",
        rank=9.5,
        document_type="נוהל",
        page_id="page-one",
    )
    page_two = make_typed_result(
        chunk_id="page-two-a",
        title="מסמך שני",
        rank=9.0,
        document_type="נוהל",
        page_id="page-two",
    )

    retrieval = FakeMultiQueryRetrieval(
        (
            first_page_one,
            second_page_one,
            page_two,
        )
    )
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context_with_strategy(
        "השווה בין שני המסמכים",
        strategy=RetrievalStrategy.MULTI_DOCUMENT,
        max_chunks=3,
    )

    assert [
        source.page_id
        for source in context.sources[:2]
    ] == [
        "page-one",
        "page-two",
    ]


@pytest.mark.asyncio
async def test_regular_build_context_remains_balanced() -> None:
    first = make_typed_result(
        chunk_id="first",
        title="נוהל",
        rank=5.0,
        document_type="נוהל",
    )
    second = make_typed_result(
        chunk_id="second",
        title="צ'קליסט",
        rank=4.0,
        document_type="צ'קליסט",
    )

    retrieval = FakeMultiQueryRetrieval(
        (first, second)
    )
    service = MultiQueryKnowledgeContextService(
        retrieval
    )

    context = await service.build_context(
        "שאלה כללית",
    )

    assert context.sources[0].chunk_id == "first"
