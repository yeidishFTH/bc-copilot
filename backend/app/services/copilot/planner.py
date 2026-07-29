from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.services.copilot.intent import (
    CopilotIntent,
    IntentClassification,
)


class RetrievalStrategy(StrEnum):
    """Retrieval strategies selected by the Copilot planner."""

    BALANCED = "balanced"
    DETAILED_PROCEDURE = "detailed_procedure"
    TITLE_FIRST = "title_first"
    PRECISE_CITATION = "precise_citation"
    BROAD_SUMMARY = "broad_summary"
    MULTI_DOCUMENT = "multi_document"
    CHANGE_FOCUSED = "change_focused"
    CHECKLIST_FIRST = "checklist_first"
    SYSTEM_FIRST = "system_first"
    OVERVIEW_FIRST = "overview_first"


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    """Parameters used to retrieve context for one Copilot request."""

    intent: CopilotIntent
    strategy: RetrievalStrategy
    search_limit: int
    max_characters: int
    max_chunks: int
    max_chunks_per_page: int
    require_citations: bool = True


class CopilotPlanner:
    """
    Convert intent and query signals into a retrieval plan.

    The planner is deterministic and does not call an external model.
    Planner v2 also selects document-oriented retrieval strategies.
    """

    _CHECKLIST_SIGNALS = (
        "צ'קליסט",
        "צ׳קליסט",
        "משימות",
        "תחילת משמרת",
        "פתיחת משמרת",
        "משמרת בוקר",
        "מה צריך לעשות בפתיחת",
    )

    _SYSTEM_SIGNALS = (
        "salesforce",
        "סיילספורס",
        "crm",
        "accounts",
        "account",
        "lamassu",
        "במערכת",
        "מסך",
        "תפריט",
    )

    _OVERVIEW_SIGNALS = (
        "מה המשמעות",
        "מה זה",
        "מהו",
        "מהי",
        "הסבר",
        "תסביר",
        "סקירה",
        "רקע",
        "מידע כללי",
    )

    _PROCEDURE_SIGNALS = (
        "איך",
        "מה עושים",
        "מה התהליך",
        "שלבים",
        "נוהל",
        "לבצע",
        "מבצעים",
        "לטפל",
    )

    _PLANS = {
        CopilotIntent.PROCEDURE: RetrievalPlan(
            intent=CopilotIntent.PROCEDURE,
            strategy=RetrievalStrategy.DETAILED_PROCEDURE,
            search_limit=35,
            max_characters=15_000,
            max_chunks=10,
            max_chunks_per_page=4,
        ),
        CopilotIntent.DOCUMENT_LOOKUP: RetrievalPlan(
            intent=CopilotIntent.DOCUMENT_LOOKUP,
            strategy=RetrievalStrategy.TITLE_FIRST,
            search_limit=18,
            max_characters=8_000,
            max_chunks=5,
            max_chunks_per_page=2,
        ),
        CopilotIntent.CITATION: RetrievalPlan(
            intent=CopilotIntent.CITATION,
            strategy=RetrievalStrategy.PRECISE_CITATION,
            search_limit=14,
            max_characters=7_000,
            max_chunks=4,
            max_chunks_per_page=2,
        ),
        CopilotIntent.SUMMARY: RetrievalPlan(
            intent=CopilotIntent.SUMMARY,
            strategy=RetrievalStrategy.BROAD_SUMMARY,
            search_limit=45,
            max_characters=22_000,
            max_chunks=15,
            max_chunks_per_page=8,
        ),
        CopilotIntent.COMPARISON: RetrievalPlan(
            intent=CopilotIntent.COMPARISON,
            strategy=RetrievalStrategy.MULTI_DOCUMENT,
            search_limit=55,
            max_characters=26_000,
            max_chunks=18,
            max_chunks_per_page=6,
        ),
        CopilotIntent.CHANGE_LOG: RetrievalPlan(
            intent=CopilotIntent.CHANGE_LOG,
            strategy=RetrievalStrategy.CHANGE_FOCUSED,
            search_limit=30,
            max_characters=14_000,
            max_chunks=10,
            max_chunks_per_page=5,
        ),
        CopilotIntent.GENERAL_QUESTION: RetrievalPlan(
            intent=CopilotIntent.GENERAL_QUESTION,
            strategy=RetrievalStrategy.BALANCED,
            search_limit=30,
            max_characters=12_000,
            max_chunks=8,
            max_chunks_per_page=3,
        ),
    }

    def plan(
        self,
        classification: IntentClassification,
        question: str | None = None,
    ) -> RetrievalPlan:
        if not isinstance(
            classification,
            IntentClassification,
        ):
            raise TypeError(
                "classification must be "
                "an IntentClassification"
            )

        base_plan = self._PLANS[classification.intent]

        if question is None:
            return base_plan

        normalized_question = self._normalize_question(
            question
        )

        if classification.intent is not CopilotIntent.GENERAL_QUESTION:
            return base_plan

        if self._contains_any(
            normalized_question,
            self._CHECKLIST_SIGNALS,
        ):
            return RetrievalPlan(
                intent=classification.intent,
                strategy=RetrievalStrategy.CHECKLIST_FIRST,
                search_limit=30,
                max_characters=13_000,
                max_chunks=9,
                max_chunks_per_page=4,
            )

        if self._contains_any(
            normalized_question,
            self._SYSTEM_SIGNALS,
        ):
            return RetrievalPlan(
                intent=classification.intent,
                strategy=RetrievalStrategy.SYSTEM_FIRST,
                search_limit=30,
                max_characters=13_000,
                max_chunks=9,
                max_chunks_per_page=4,
            )

        if self._contains_any(
            normalized_question,
            self._OVERVIEW_SIGNALS,
        ):
            return RetrievalPlan(
                intent=classification.intent,
                strategy=RetrievalStrategy.OVERVIEW_FIRST,
                search_limit=35,
                max_characters=15_000,
                max_chunks=10,
                max_chunks_per_page=5,
            )

        if self._contains_any(
            normalized_question,
            self._PROCEDURE_SIGNALS,
        ):
            return RetrievalPlan(
                intent=classification.intent,
                strategy=RetrievalStrategy.DETAILED_PROCEDURE,
                search_limit=35,
                max_characters=15_000,
                max_chunks=10,
                max_chunks_per_page=4,
            )

        return base_plan

    @staticmethod
    def _contains_any(
        question: str,
        signals: tuple[str, ...],
    ) -> bool:
        return any(
            signal in question
            for signal in signals
        )

    @staticmethod
    def _normalize_question(
        question: str,
    ) -> str:
        if not isinstance(question, str):
            raise TypeError(
                "question must be a string"
            )

        normalized = " ".join(
            question.casefold().split()
        )

        if not normalized:
            raise ValueError(
                "question cannot be empty"
            )

        return normalized
