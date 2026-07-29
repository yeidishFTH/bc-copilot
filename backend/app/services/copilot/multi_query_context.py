from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol, runtime_checkable

from app.services.copilot.multi_query_retrieval import (
    MultiQueryRetrievalResult,
)
from app.services.copilot.planner import (
    RetrievalStrategy,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)
from app.services.knowledge.retrieval import (
    KnowledgeContext,
    KnowledgeContextBuilder,
)


@runtime_checkable
class MultiQuerySearchReader(Protocol):
    """Multi-query search required by the context service."""

    async def search(
        self,
        query: str,
        *,
        limit: int = 30,
        per_query_limit: int = 20,
        max_queries: int = 5,
        namespace_ids: Sequence[int] | None = None,
    ) -> MultiQueryRetrievalResult:
        ...


class MultiQueryKnowledgeContextService:
    """
    Build bounded RAG context from merged multi-query results.

    This service intentionally has the same build_context interface
    as KnowledgeContextService, allowing CopilotAnswerService and
    existing test doubles to remain compatible.
    """

    DEFAULT_SEARCH_LIMIT = 30
    MAX_SEARCH_LIMIT = 100
    DEFAULT_MAX_QUERIES = 5
    MAX_PER_QUERY_LIMIT = 30

    def __init__(
        self,
        retrieval: MultiQuerySearchReader,
        *,
        builder: KnowledgeContextBuilder | None = None,
    ) -> None:
        if not isinstance(
            retrieval,
            MultiQuerySearchReader,
        ):
            raise TypeError(
                "retrieval must implement "
                "MultiQuerySearchReader"
            )

        self._retrieval = retrieval
        self._builder = builder or KnowledgeContextBuilder()

    async def build_context(
        self,
        query: str,
        *,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        namespace_ids: Sequence[int] | None = None,
        max_characters: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHARACTERS
        ),
        max_chunks: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHUNKS
        ),
        max_chunks_per_page: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHUNKS_PER_PAGE
        ),
    ) -> KnowledgeContext:
        return await self.build_context_with_strategy(
            query,
            strategy=RetrievalStrategy.BALANCED,
            search_limit=search_limit,
            namespace_ids=namespace_ids,
            max_characters=max_characters,
            max_chunks=max_chunks,
            max_chunks_per_page=max_chunks_per_page,
        )

    async def build_context_with_strategy(
        self,
        query: str,
        *,
        strategy: RetrievalStrategy,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        namespace_ids: Sequence[int] | None = None,
        max_characters: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHARACTERS
        ),
        max_chunks: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHUNKS
        ),
        max_chunks_per_page: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHUNKS_PER_PAGE
        ),
    ) -> KnowledgeContext:
        if not isinstance(strategy, RetrievalStrategy):
            raise TypeError(
                "strategy must be a RetrievalStrategy"
            )

        normalized_search_limit = (
            KnowledgeContextBuilder
            ._validate_positive_integer(
                search_limit,
                field_name="search_limit",
                maximum=self.MAX_SEARCH_LIMIT,
            )
        )

        per_query_limit = min(
            normalized_search_limit,
            self.MAX_PER_QUERY_LIMIT,
        )

        retrieval_result = await self._retrieval.search(
            query,
            limit=normalized_search_limit,
            per_query_limit=per_query_limit,
            max_queries=self.DEFAULT_MAX_QUERIES,
            namespace_ids=namespace_ids,
        )

        reranked_results = self._rerank_for_strategy(
            query,
            retrieval_result.results,
            strategy=strategy,
        )

        return self._builder.build(
            query,
            reranked_results,
            max_characters=max_characters,
            max_chunks=max_chunks,
            max_chunks_per_page=max_chunks_per_page,
        )

    _TOKEN_PATTERN = re.compile(
        r"[א-תA-Za-z0-9׳']+"
    )

    @classmethod
    def _rerank_for_strategy(
        cls,
        query: str,
        results: Sequence[KnowledgeSearchResult],
        *,
        strategy: RetrievalStrategy,
    ) -> tuple[KnowledgeSearchResult, ...]:
        if strategy is RetrievalStrategy.BALANCED:
            return tuple(results)

        reranked = tuple(
            replace(
                result,
                rank=(
                    result.rank
                    + cls._strategy_bonus(
                        query,
                        result,
                        strategy=strategy,
                    )
                ),
            )
            for result in results
        )

        ordered = tuple(
            sorted(
                reranked,
                key=lambda result: (
                    -result.rank,
                    result.title.casefold(),
                    result.position,
                ),
            )
        )

        if strategy is RetrievalStrategy.MULTI_DOCUMENT:
            return cls._diversify_pages(ordered)

        return ordered

    @classmethod
    def _strategy_bonus(
        cls,
        query: str,
        result: KnowledgeSearchResult,
        *,
        strategy: RetrievalStrategy,
    ) -> float:
        document_type = (
            result.document_type
            or ""
        ).casefold()

        title = result.title.casefold()
        heading = " ".join(
            result.heading_path
        ).casefold()

        query_tokens = cls._tokens(query)
        title_tokens = cls._tokens(title)
        heading_tokens = cls._tokens(heading)

        title_overlap = cls._coverage(
            query_tokens,
            title_tokens,
        )
        heading_overlap = cls._coverage(
            query_tokens,
            heading_tokens,
        )

        if strategy is RetrievalStrategy.DETAILED_PROCEDURE:
            if (
                "נוהל" in document_type
                or title.startswith("נוהל")
            ):
                return 1.60

            if (
                "צ'קליסט" in document_type
                or "צ׳קליסט" in document_type
            ):
                return 0.45

            return 0.0

        if strategy is RetrievalStrategy.TITLE_FIRST:
            return (
                title_overlap * 3.20
                + heading_overlap * 0.40
            )

        if strategy is RetrievalStrategy.PRECISE_CITATION:
            return (
                title_overlap * 1.60
                + heading_overlap * 2.10
            )

        if strategy is RetrievalStrategy.BROAD_SUMMARY:
            bonus = title_overlap * 0.80

            if any(
                signal in document_type
                for signal in (
                    "ידע",
                    "פורטל",
                    "הדרכה",
                    "מדריך",
                )
            ):
                bonus += 1.10

            return bonus

        if strategy is RetrievalStrategy.MULTI_DOCUMENT:
            return (
                title_overlap * 0.70
                + heading_overlap * 0.30
            )

        if strategy is RetrievalStrategy.CHANGE_FOCUSED:
            bonus = 0.0
            combined = f"{title} {heading}"

            if any(
                signal in combined
                for signal in (
                    "עדכון",
                    "שינוי",
                    "גרסה",
                    "רענון",
                    "עודכן",
                )
            ):
                bonus += 2.00

            if result.version:
                bonus += 0.40

            if result.updated_on:
                bonus += 0.30

            return bonus

        if strategy is RetrievalStrategy.CHECKLIST_FIRST:
            if (
                "צ'קליסט" in document_type
                or "צ׳קליסט" in document_type
                or "צ'קליסט" in title
                or "צ׳קליסט" in title
            ):
                return 2.40

            if "נוהל" in document_type:
                return -0.35

            return 0.0

        if strategy is RetrievalStrategy.SYSTEM_FIRST:
            if any(
                signal in document_type
                for signal in (
                    "מערכת",
                    "מדריך מערכת",
                )
            ):
                return 2.10

            if any(
                signal in title
                for signal in (
                    "salesforce",
                    "מערכת",
                    "lamassu",
                )
            ):
                return 1.70

            return 0.0

        if strategy is RetrievalStrategy.OVERVIEW_FIRST:
            bonus = title_overlap * 1.20

            if any(
                signal in document_type
                for signal in (
                    "ידע",
                    "פורטל",
                    "רקע",
                )
            ):
                bonus += 1.70

            if "נוהל" in document_type:
                bonus -= 0.80

            return bonus

        return 0.0

    @classmethod
    def _diversify_pages(
        cls,
        results: Sequence[KnowledgeSearchResult],
    ) -> tuple[KnowledgeSearchResult, ...]:
        unseen_pages: list[KnowledgeSearchResult] = []
        repeated_pages: list[KnowledgeSearchResult] = []
        seen_page_ids: set[str] = set()

        for result in results:
            if result.page_id in seen_page_ids:
                repeated_pages.append(result)
                continue

            seen_page_ids.add(result.page_id)
            unseen_pages.append(result)

        return tuple(
            unseen_pages + repeated_pages
        )

    @classmethod
    def _tokens(
        cls,
        value: str,
    ) -> frozenset[str]:
        return frozenset(
            match.group(0).casefold()
            for match in cls._TOKEN_PATTERN.finditer(
                value
            )
            if len(match.group(0)) >= 2
        )

    @staticmethod
    def _coverage(
        query_tokens: frozenset[str],
        candidate_tokens: frozenset[str],
    ) -> float:
        if not query_tokens:
            return 0.0

        return (
            len(query_tokens & candidate_tokens)
            / len(query_tokens)
        )
