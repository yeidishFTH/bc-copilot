from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from app.services.copilot.query_rewriter import (
    QueryRewrite,
    QueryRewriter,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)


@runtime_checkable
class KnowledgeQueryRetriever(Protocol):
    """Retrieval operations required by multi-query search."""

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        ...


@dataclass(frozen=True, slots=True)
class MultiQueryRetrievalResult:
    """Merged and reranked results from several search queries."""

    rewrite: QueryRewrite
    results: tuple[KnowledgeSearchResult, ...]
    executed_queries: tuple[str, ...]
    raw_result_count: int
    unique_result_count: int


@dataclass(slots=True)
class _AggregatedCandidate:
    result: KnowledgeSearchResult
    best_rank: float
    hit_count: int
    first_query_index: int
    appeared_in_original_query: bool


class MultiQueryRetrievalService:
    """
    Execute several deterministic searches and merge their results.

    Ranking combines:
    - the strongest database rank;
    - repeated appearances across rewritten queries;
    - a small bonus for appearing in the original query;
    - a small metadata-quality bonus.

    The service does not call an LLM.
    """

    DEFAULT_LIMIT = 30
    DEFAULT_PER_QUERY_LIMIT = 20
    DEFAULT_MAX_QUERIES = 5

    MAX_LIMIT = 100
    MAX_PER_QUERY_LIMIT = 100
    MAX_QUERIES = 8

    REPEATED_HIT_BONUS = 0.35
    ORIGINAL_QUERY_BONUS = 0.20
    METADATA_BONUS = 0.10
    EARLY_QUERY_BONUS = 0.04

    def __init__(
        self,
        retrieval: KnowledgeQueryRetriever,
        *,
        rewriter: QueryRewriter | None = None,
    ) -> None:
        if not isinstance(
            retrieval,
            KnowledgeQueryRetriever,
        ):
            raise TypeError(
                "retrieval must implement "
                "KnowledgeQueryRetriever"
            )

        self._retrieval = retrieval
        self._rewriter = rewriter or QueryRewriter()

    async def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        per_query_limit: int = DEFAULT_PER_QUERY_LIMIT,
        max_queries: int = DEFAULT_MAX_QUERIES,
        namespace_ids: Sequence[int] | None = None,
    ) -> MultiQueryRetrievalResult:
        normalized_limit = self._validate_positive_integer(
            limit,
            field_name="limit",
            maximum=self.MAX_LIMIT,
        )
        normalized_per_query_limit = (
            self._validate_positive_integer(
                per_query_limit,
                field_name="per_query_limit",
                maximum=self.MAX_PER_QUERY_LIMIT,
            )
        )
        normalized_max_queries = (
            self._validate_positive_integer(
                max_queries,
                field_name="max_queries",
                maximum=self.MAX_QUERIES,
            )
        )

        rewrite = self._rewriter.rewrite(query)

        executed_queries = rewrite.search_queries[
            :normalized_max_queries
        ]

        candidates: dict[str, _AggregatedCandidate] = {}
        raw_result_count = 0

        for query_index, search_query in enumerate(
            executed_queries
        ):
            results = await self._retrieval.search(
                search_query,
                limit=normalized_per_query_limit,
                namespace_ids=namespace_ids,
            )

            raw_result_count += len(results)

            seen_in_current_query: set[str] = set()

            for result in results:
                if result.chunk_id in seen_in_current_query:
                    continue

                seen_in_current_query.add(result.chunk_id)

                candidate = candidates.get(result.chunk_id)

                if candidate is None:
                    candidates[result.chunk_id] = (
                        _AggregatedCandidate(
                            result=result,
                            best_rank=result.rank,
                            hit_count=1,
                            first_query_index=query_index,
                            appeared_in_original_query=(
                                query_index == 0
                            ),
                        )
                    )
                    continue

                candidate.hit_count += 1
                candidate.best_rank = max(
                    candidate.best_rank,
                    result.rank,
                )
                candidate.appeared_in_original_query = (
                    candidate.appeared_in_original_query
                    or query_index == 0
                )

                if result.rank > candidate.result.rank:
                    candidate.result = result

        ranked_results = tuple(
            replace(
                candidate.result,
                rank=self._score_candidate(candidate),
            )
            for candidate in sorted(
                candidates.values(),
                key=self._candidate_sort_key,
            )[:normalized_limit]
        )

        return MultiQueryRetrievalResult(
            rewrite=rewrite,
            results=ranked_results,
            executed_queries=tuple(executed_queries),
            raw_result_count=raw_result_count,
            unique_result_count=len(candidates),
        )

    @classmethod
    def _score_candidate(
        cls,
        candidate: _AggregatedCandidate,
    ) -> float:
        repeated_bonus = (
            max(candidate.hit_count - 1, 0)
            * cls.REPEATED_HIT_BONUS
        )

        original_bonus = (
            cls.ORIGINAL_QUERY_BONUS
            if candidate.appeared_in_original_query
            else 0.0
        )

        metadata_bonus = (
            cls.METADATA_BONUS
            if cls._has_metadata(candidate.result)
            else 0.0
        )

        early_query_bonus = max(
            cls.EARLY_QUERY_BONUS
            * (cls.MAX_QUERIES - candidate.first_query_index),
            0.0,
        )

        return round(
            candidate.best_rank
            + repeated_bonus
            + original_bonus
            + metadata_bonus
            + early_query_bonus,
            6,
        )

    @classmethod
    def _candidate_sort_key(
        cls,
        candidate: _AggregatedCandidate,
    ) -> tuple[float, int, int, str, int]:
        score = cls._score_candidate(candidate)

        return (
            -score,
            -candidate.hit_count,
            candidate.first_query_index,
            candidate.result.title.casefold(),
            candidate.result.position,
        )

    @staticmethod
    def _has_metadata(
        result: KnowledgeSearchResult,
    ) -> bool:
        return any(
            (
                result.status,
                result.document_type,
                result.portal,
                result.category,
                result.audience,
                result.owner,
                result.responsible_department,
                result.updated_on,
                result.version,
            )
        )

    @staticmethod
    def _validate_positive_integer(
        value: int,
        *,
        field_name: str,
        maximum: int,
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"{field_name} must be an integer"
            )

        if value < 1 or value > maximum:
            raise ValueError(
                f"{field_name} must be between "
                f"1 and {maximum}"
            )

        return value
