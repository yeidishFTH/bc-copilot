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
    Convert an intent classification into a retrieval plan.

    The planner is deterministic and does not call an external model.
    It only decides how broad or precise retrieval should be.
    """

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
    ) -> RetrievalPlan:
        if not isinstance(
            classification,
            IntentClassification,
        ):
            raise TypeError(
                "classification must be "
                "an IntentClassification"
            )

        return self._PLANS[classification.intent]
