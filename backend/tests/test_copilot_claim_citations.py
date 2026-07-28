from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.copilot.claim_citations import (
    ClaimCitationMapper,
)


@dataclass(frozen=True)
class FakeSource:
    index: int
    title: str
    heading_path: tuple[str, ...]
    chunk_id: str


@pytest.fixture
def sources() -> tuple[FakeSource, ...]:
    return (
        FakeSource(
            index=1,
            title="נוהל מחיקת כרטיס לקוח",
            heading_path=(
                "נוהל מחיקת כרטיס לקוח",
                "שלבי ביצוע",
            ),
            chunk_id="chunk-1",
        ),
        FakeSource(
            index=2,
            title="נוהל מחיקת כרטיס לקוח",
            heading_path=(
                "נוהל מחיקת כרטיס לקוח",
                "דגשים",
            ),
            chunk_id="chunk-2",
        ),
        FakeSource(
            index=3,
            title="נוהל ציות",
            heading_path=(),
            chunk_id="chunk-3",
        ),
    )


def test_maps_numbered_claim_to_source(
    sources: tuple[FakeSource, ...],
) -> None:
    mapper = ClaimCitationMapper()

    mapping = mapper.map(
        "1. יש לקבל בקשה במייל. [SOURCE 1]",
        sources=sources,
    )

    assert mapping.claim_count == 1
    assert mapping.claims[0].text == (
        "יש לקבל בקשה במייל."
    )
    assert mapping.claims[0].source_indexes == (1,)
    assert mapping.claims[0].source_chunk_ids == (
        "chunk-1",
    )


def test_maps_claim_to_multiple_sources(
    sources: tuple[FakeSource, ...],
) -> None:
    mapper = ClaimCitationMapper()

    mapping = mapper.map(
        (
            "המחיקה היא לצמיתות. "
            "[SOURCE 1] [SOURCE 2]"
        ),
        sources=sources,
    )

    assert mapping.claims[0].source_indexes == (
        1,
        2,
    )
    assert mapping.claims[0].source_titles == (
        "נוהל מחיקת כרטיס לקוח",
        "נוהל מחיקת כרטיס לקוח",
    )


def test_maps_markdown_list_items_separately(
    sources: tuple[FakeSource, ...],
) -> None:
    mapper = ClaimCitationMapper()

    mapping = mapper.map(
        (
            "- יש לקבל בקשה. [SOURCE 1]\n"
            "- יש לתעד את הבקשה. [SOURCE 2]"
        ),
        sources=sources,
    )

    assert [claim.text for claim in mapping.claims] == [
        "יש לקבל בקשה.",
        "יש לתעד את הבקשה.",
    ]


def test_ignores_uncited_text(
    sources: tuple[FakeSource, ...],
) -> None:
    mapper = ClaimCitationMapper()

    mapping = mapper.map(
        (
            "כותרת ללא מקור\n\n"
            "פעולה מתועדת. [SOURCE 1]"
        ),
        sources=sources,
    )

    assert mapping.claim_count == 1
    assert mapping.claims[0].text == (
        "פעולה מתועדת."
    )


def test_reports_uncited_sources(
    sources: tuple[FakeSource, ...],
) -> None:
    mapper = ClaimCitationMapper()

    mapping = mapper.map(
        "פעולה מתועדת. [SOURCE 2]",
        sources=sources,
    )

    assert mapping.cited_source_indexes == (2,)
    assert mapping.uncited_source_indexes == (
        1,
        3,
    )


def test_ignores_unknown_source_indexes(
    sources: tuple[FakeSource, ...],
) -> None:
    mapper = ClaimCitationMapper()

    mapping = mapper.map(
        "טענה. [SOURCE 99]",
        sources=sources,
    )

    assert mapping.claims == ()


@pytest.mark.parametrize(
    "answer",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_answer(
    sources: tuple[FakeSource, ...],
    answer: str,
) -> None:
    mapper = ClaimCitationMapper()

    with pytest.raises(
        ValueError,
        match="answer cannot be empty",
    ):
        mapper.map(
            answer,
            sources=sources,
        )


def test_knowledge_context_source_keeps_old_constructor_compatible() -> None:
    from app.services.knowledge.retrieval.context import (
        KnowledgeContextSource,
    )

    source = KnowledgeContextSource(
        index=1,
        page_id="page-1",
        revision_id="revision-1",
        chunk_id="chunk-1",
        title="מסמך בדיקה",
        heading_path=("סעיף",),
        canonical_url="https://wiki.example.test/test",
        content="תוכן",
        rank=1.0,
    )

    assert source.wiki_page_id is None
    assert source.wiki_revision_id is None
