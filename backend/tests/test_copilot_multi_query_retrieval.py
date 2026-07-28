from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pytest

from app.services.copilot.multi_query_retrieval import (
    MultiQueryRetrievalService,
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
    document_type: str | None = None,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        page_id=f"page-{title}",
        revision_id=f"revision-{title}",
        chunk_id=chunk_id,
        wiki_page_id=101,
        wiki_revision_id=202,
        title=title,
        canonical_url=(
            f"https://wiki.example.test/{chunk_id}"
        ),
        namespace_id=0,
        position=position,
        heading_path=("שלבי ביצוע",),
        content=f"תוכן עבור {title}",
        token_count=10,
        rank=rank,
        status=(
            "מאושר"
            if document_type is not None
            else None
        ),
        document_type=document_type,
        portal=(
            "נציגים"
            if document_type is not None
            else None
        ),
        category=None,
        audience=(),
        owner=None,
        responsible_department=None,
        updated_on=(
            date(2026, 7, 27)
            if document_type is not None
            else None
        ),
        version=None,
    )


class FakeRetrieval:
    def __init__(
        self,
        results_by_query: dict[
            str,
            tuple[KnowledgeSearchResult, ...],
        ],
    ) -> None:
        self.results_by_query = results_by_query
        self.calls: list[dict[str, object]] = []

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
                "namespace_ids": (
                    tuple(namespace_ids)
                    if namespace_ids is not None
                    else None
                ),
            }
        )

        return self.results_by_query.get(query, ())[
            :limit
        ]


@pytest.mark.asyncio
async def test_executes_original_and_rewritten_queries() -> None:
    retrieval = FakeRetrieval({})
    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "איך מוחקים לקוח?",
        max_queries=4,
    )

    assert result.executed_queries == (
        "איך מוחקים לקוח?",
        "מחיקת כרטיס לקוח",
        "נוהל מחיקת כרטיס לקוח",
        "מחיקת חשבון לקוח",
    )

    assert [
        call["query"]
        for call in retrieval.calls
    ] == list(result.executed_queries)


@pytest.mark.asyncio
async def test_merges_duplicate_chunks() -> None:
    shared = make_result(
        chunk_id="shared",
        title="נוהל מחיקת כרטיס לקוח",
        rank=4.0,
    )

    retrieval = FakeRetrieval(
        {
            "איך מוחקים לקוח?": (
                shared,
                make_result(
                    chunk_id="original-only",
                    title="מידע כללי",
                    rank=3.8,
                ),
            ),
            "מחיקת כרטיס לקוח": (
                replace_rank(shared, 5.2),
            ),
            "נוהל מחיקת כרטיס לקוח": (
                replace_rank(shared, 5.0),
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "איך מוחקים לקוח?",
        max_queries=3,
    )

    assert result.raw_result_count == 4
    assert result.unique_result_count == 2
    assert len(result.results) == 2
    assert result.results[0].chunk_id == "shared"
    assert result.results[0].rank > 5.2


@pytest.mark.asyncio
async def test_repeated_result_beats_single_result() -> None:
    repeated = make_result(
        chunk_id="repeated",
        title="נוהל זיהוי ואימות לקוח",
        rank=3.0,
    )
    single = make_result(
        chunk_id="single",
        title="מסמך אחר",
        rank=3.4,
    )

    retrieval = FakeRetrieval(
        {
            "איך מזהים לקוח?": (
                repeated,
                single,
            ),
            "זיהוי ואימות לקוח": (
                repeated,
            ),
            "נוהל זיהוי ואימות לקוח": (
                repeated,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "איך מזהים לקוח?",
        max_queries=3,
    )

    assert result.results[0].chunk_id == "repeated"


@pytest.mark.asyncio
async def test_metadata_adds_small_quality_bonus() -> None:
    without_metadata = make_result(
        chunk_id="without",
        title="מסמך ללא מטא דאטה",
        rank=2.0,
    )
    with_metadata = make_result(
        chunk_id="with",
        title="נוהל רשמי",
        rank=2.0,
        document_type="נוהל",
    )

    retrieval = FakeRetrieval(
        {
            "שאלה כללית": (
                without_metadata,
                with_metadata,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "שאלה כללית",
        max_queries=1,
    )

    assert result.results[0].chunk_id == "with"
    assert (
        result.results[0].rank
        > result.results[1].rank
    )


@pytest.mark.asyncio
async def test_respects_limits_and_namespaces() -> None:
    retrieval = FakeRetrieval({})
    service = MultiQueryRetrievalService(retrieval)

    await service.search(
        "מה עושים בכספומט?",
        limit=7,
        per_query_limit=4,
        max_queries=2,
        namespace_ids=(0, 2),
    )

    assert len(retrieval.calls) == 2
    assert all(
        call["limit"] == 4
        for call in retrieval.calls
    )
    assert all(
        call["namespace_ids"] == (0, 2)
        for call in retrieval.calls
    )


@pytest.mark.asyncio
async def test_unknown_query_runs_once() -> None:
    retrieval = FakeRetrieval({})
    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "מי אחראי על ההדרכה?"
    )

    assert result.executed_queries == (
        "מי אחראי על ההדרכה?",
    )
    assert len(retrieval.calls) == 1


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("limit", {"limit": 0}),
        (
            "per_query_limit",
            {"per_query_limit": 0},
        ),
        ("max_queries", {"max_queries": 0}),
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_limits(
    field_name: str,
    kwargs: dict[str, int],
) -> None:
    retrieval = FakeRetrieval({})
    service = MultiQueryRetrievalService(retrieval)

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        await service.search(
            "שאלה",
            **kwargs,
        )


def replace_rank(
    result: KnowledgeSearchResult,
    rank: float,
) -> KnowledgeSearchResult:
    from dataclasses import replace

    return replace(
        result,
        rank=rank,
    )


@pytest.mark.asyncio
async def test_exact_title_match_can_outrank_higher_raw_rank() -> None:
    title_match = make_result(
        chunk_id="title-match",
        title="דגשים בעת רישום לקוחות זרים",
        rank=2.0,
    )
    generic = make_result(
        chunk_id="generic",
        title="נוהל בקרה וביקורת",
        rank=3.2,
    )

    retrieval = FakeRetrieval(
        {
            "איך מטפלים בלקוח זר?": (
                generic,
            ),
            "לקוחות זרים": (
                generic,
            ),
            "דגשים בעת רישום לקוחות זרים": (
                title_match,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "איך מטפלים בלקוח זר?",
        max_queries=3,
    )

    assert result.results[0].chunk_id == "title-match"


@pytest.mark.asyncio
async def test_procedure_document_receives_authority_bonus() -> None:
    guide = make_result(
        chunk_id="guide",
        title="מערכת Salesforce",
        rank=3.0,
        document_type="מדריך מערכת",
    )
    procedure = make_result(
        chunk_id="procedure",
        title="נוהל מכירת USDT ERC-20 וטיפול בתקלות",
        rank=3.0,
        document_type="נוהל",
    )

    retrieval = FakeRetrieval(
        {
            "Lamassu": (
                guide,
                procedure,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "Lamassu",
        max_queries=1,
    )

    assert result.results[0].chunk_id == "procedure"
    assert (
        result.results[0].rank
        > result.results[1].rank
    )


@pytest.mark.asyncio
async def test_title_phrase_match_adds_ranking_bonus() -> None:
    matching = make_result(
        chunk_id="matching",
        title="נוהל מחיקת כרטיס לקוח",
        rank=2.0,
    )
    unrelated = make_result(
        chunk_id="unrelated",
        title="מסמך כללי",
        rank=2.5,
    )

    retrieval = FakeRetrieval(
        {
            "מחיקת כרטיס לקוח": (
                unrelated,
                matching,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "מחיקת כרטיס לקוח",
        max_queries=1,
    )

    assert result.results[0].chunk_id == "matching"


@pytest.mark.asyncio
async def test_overview_query_prefers_knowledge_page_over_procedure() -> None:
    overview = make_result(
        chunk_id="overview",
        title="ציות ורגולציה",
        rank=2.2,
        document_type="פורטל",
    )
    procedure = make_result(
        chunk_id="procedure",
        title="נוהל התקשרות עם מחלקת ציות",
        rank=4.3,
        document_type="נוהל",
    )

    retrieval = FakeRetrieval(
        {
            "מה המשמעות של ציות ורגולציה?": (
                procedure,
                overview,
            ),
            "ציות ורגולציה": (
                procedure,
                overview,
            ),
            "מחלקת ציות": (
                procedure,
            ),
            "AML": (
                procedure,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "מה המשמעות של ציות ורגולציה?",
        max_queries=4,
    )

    assert result.results[0].chunk_id == "overview"


@pytest.mark.asyncio
async def test_procedure_query_still_prefers_procedure() -> None:
    overview = make_result(
        chunk_id="overview",
        title="ציות ורגולציה",
        rank=3.0,
        document_type="פורטל",
    )
    procedure = make_result(
        chunk_id="procedure",
        title="נוהל התקשרות עם מחלקת ציות",
        rank=3.0,
        document_type="נוהל",
    )

    retrieval = FakeRetrieval(
        {
            "איך פונים למחלקת ציות?": (
                overview,
                procedure,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "איך פונים למחלקת ציות?",
        max_queries=1,
    )

    assert result.results[0].chunk_id == "procedure"


@pytest.mark.asyncio
async def test_system_query_prefers_system_document() -> None:
    system_document = make_result(
        chunk_id="system",
        title="מערכת Salesforce",
        rank=2.5,
        document_type="מדריך מערכת",
    )
    generic_document = make_result(
        chunk_id="generic",
        title="נוהל הקמת סניף",
        rank=2.8,
        document_type="נוהל",
    )

    retrieval = FakeRetrieval(
        {
            "איפה רואים לקוח במערכת Salesforce?": (
                generic_document,
                system_document,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "איפה רואים לקוח במערכת Salesforce?",
        max_queries=1,
    )

    assert result.results[0].chunk_id == "system"


@pytest.mark.asyncio
async def test_checklist_query_prefers_checklist_document() -> None:
    checklist = make_result(
        chunk_id="checklist",
        title="צ'קליסט פתיחת ותחזוקת סניף",
        rank=2.5,
        document_type="צ'קליסט",
    )
    procedure = make_result(
        chunk_id="procedure",
        title="נוהל בקרה וביקורת",
        rank=2.8,
        document_type="נוהל",
    )

    retrieval = FakeRetrieval(
        {
            "מהן המשימות בתחילת משמרת בוקר?": (
                procedure,
                checklist,
            ),
        }
    )

    service = MultiQueryRetrievalService(retrieval)

    result = await service.search(
        "מהן המשימות בתחילת משמרת בוקר?",
        max_queries=1,
    )

    assert result.results[0].chunk_id == "checklist"
