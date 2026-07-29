from __future__ import annotations

import pytest

from app.services.copilot.intent import (
    CopilotIntent,
    IntentClassification,
)
from app.services.copilot.planner import (
    CopilotPlanner,
    RetrievalStrategy,
)


def classification(
    intent: CopilotIntent,
) -> IntentClassification:
    return IntentClassification(
        intent=intent,
        confidence=0.9,
        matched_signals=("test",),
    )


@pytest.mark.parametrize(
    (
        "intent",
        "strategy",
        "search_limit",
        "max_chunks",
    ),
    [
        (
            CopilotIntent.PROCEDURE,
            RetrievalStrategy.DETAILED_PROCEDURE,
            35,
            10,
        ),
        (
            CopilotIntent.DOCUMENT_LOOKUP,
            RetrievalStrategy.TITLE_FIRST,
            18,
            5,
        ),
        (
            CopilotIntent.CITATION,
            RetrievalStrategy.PRECISE_CITATION,
            14,
            4,
        ),
        (
            CopilotIntent.SUMMARY,
            RetrievalStrategy.BROAD_SUMMARY,
            45,
            15,
        ),
        (
            CopilotIntent.COMPARISON,
            RetrievalStrategy.MULTI_DOCUMENT,
            55,
            18,
        ),
        (
            CopilotIntent.CHANGE_LOG,
            RetrievalStrategy.CHANGE_FOCUSED,
            30,
            10,
        ),
        (
            CopilotIntent.GENERAL_QUESTION,
            RetrievalStrategy.BALANCED,
            30,
            8,
        ),
    ],
)
def test_returns_plan_for_each_intent(
    intent: CopilotIntent,
    strategy: RetrievalStrategy,
    search_limit: int,
    max_chunks: int,
) -> None:
    planner = CopilotPlanner()

    plan = planner.plan(classification(intent))

    assert plan.intent is intent
    assert plan.strategy is strategy
    assert plan.search_limit == search_limit
    assert plan.max_chunks == max_chunks
    assert plan.max_characters >= 500
    assert plan.max_chunks_per_page >= 1
    assert plan.require_citations is True


def test_comparison_plan_is_broader_than_citation() -> None:
    planner = CopilotPlanner()

    comparison = planner.plan(
        classification(CopilotIntent.COMPARISON)
    )
    citation = planner.plan(
        classification(CopilotIntent.CITATION)
    )

    assert (
        comparison.search_limit
        > citation.search_limit
    )
    assert (
        comparison.max_characters
        > citation.max_characters
    )
    assert (
        comparison.max_chunks
        > citation.max_chunks
    )


def test_summary_allows_more_chunks_per_page() -> None:
    planner = CopilotPlanner()

    summary = planner.plan(
        classification(CopilotIntent.SUMMARY)
    )
    lookup = planner.plan(
        classification(
            CopilotIntent.DOCUMENT_LOOKUP
        )
    )

    assert (
        summary.max_chunks_per_page
        > lookup.max_chunks_per_page
    )


def test_rejects_invalid_classification() -> None:
    planner = CopilotPlanner()

    with pytest.raises(
        TypeError,
        match=(
            "classification must be "
            "an IntentClassification"
        ),
    ):
        planner.plan("procedure")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("question", "expected_strategy"),
    [
        (
            "מהן המשימות בתחילת משמרת בוקר?",
            RetrievalStrategy.CHECKLIST_FIRST,
        ),
        (
            "איך עובדים עם Accounts בסיילספורס?",
            RetrievalStrategy.SYSTEM_FIRST,
        ),
        (
            "מה המשמעות של ציות ורגולציה?",
            RetrievalStrategy.OVERVIEW_FIRST,
        ),
        (
            "איך מטפלים בלקוח?",
            RetrievalStrategy.DETAILED_PROCEDURE,
        ),
    ],
)
def test_general_question_uses_query_aware_strategy(
    question: str,
    expected_strategy: RetrievalStrategy,
) -> None:
    planner = CopilotPlanner()

    plan = planner.plan(
        classification(
            CopilotIntent.GENERAL_QUESTION
        ),
        question,
    )

    assert plan.strategy is expected_strategy


def test_explicit_intent_overrides_general_query_signals() -> None:
    planner = CopilotPlanner()

    plan = planner.plan(
        classification(
            CopilotIntent.CITATION
        ),
        "איפה כתוב בצ'קליסט?",
    )

    assert (
        plan.strategy
        is RetrievalStrategy.PRECISE_CITATION
    )


def test_planner_remains_backward_compatible_without_question() -> None:
    planner = CopilotPlanner()

    plan = planner.plan(
        classification(
            CopilotIntent.GENERAL_QUESTION
        )
    )

    assert plan.strategy is RetrievalStrategy.BALANCED
