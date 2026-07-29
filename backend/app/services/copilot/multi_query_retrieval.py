from __future__ import annotations

import re

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
    query_match_bonus: float
    semantic_mode_bonus: float
    intent_title_bonus: float


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

    EXACT_TITLE_MATCH_BONUS = 3.00
    INTENT_TITLE_MATCH_BONUS = 6.00
    TITLE_PHRASE_MATCH_BONUS = 2.20
    HIGH_TITLE_COVERAGE_BONUS = 1.50
    MEDIUM_TITLE_COVERAGE_BONUS = 0.80
    HEADING_PHRASE_MATCH_BONUS = 0.70
    CONTENT_PHRASE_MATCH_BONUS = 0.35

    APPROVED_STATUS_BONUS = 0.35
    PROCEDURE_DOCUMENT_BONUS = 0.75
    TRAINING_DOCUMENT_BONUS = 0.25
    SYSTEM_GUIDE_DOCUMENT_BONUS = 0.15

    OVERVIEW_EXACT_TITLE_BONUS = 4.00
    OVERVIEW_HIGH_TITLE_COVERAGE_BONUS = 2.20
    OVERVIEW_KNOWLEDGE_DOCUMENT_BONUS = 1.20
    OVERVIEW_PROCEDURE_PENALTY = 1.50

    PROCEDURE_QUERY_PROCEDURE_BONUS = 0.90
    SYSTEM_QUERY_SYSTEM_GUIDE_BONUS = 0.90
    CHECKLIST_QUERY_CHECKLIST_BONUS = 1.50
    CHECKLIST_QUERY_PROCEDURE_PENALTY = 0.40

    _OVERVIEW_SIGNALS = (
        "מה המשמעות של",
        "מה המשמעות",
        "מה זה",
        "מהי",
        "מהו",
        "הסבר",
        "תסביר",
        "סקירה",
        "רקע על",
        "מידע על",
    )

    _PROCEDURE_SIGNALS = (
        "איך",
        "מה עושים",
        "מה צריך לעשות",
        "מה התהליך",
        "שלבים",
        "נוהל",
        "לבצע",
        "מבצעים",
        "לטפל",
        "מטפלים",
    )

    _SYSTEM_SIGNALS = (
        "במערכת",
        "מערכת",
        "salesforce",
        "סיילספורס",
        "crm",
        "accounts",
        "account",
    )

    _CHECKLIST_SIGNALS = (
        "צ'קליסט",
        "צ׳קליסט",
        "משימות",
        "פתיחת משמרת",
        "תחילת משמרת",
        "משמרת בוקר",
    )

    _TOKEN_PATTERN = re.compile(
        r"[א-תA-Za-z0-9׳']+"
    )

    _QUERY_STOP_WORDS = frozenset(
        {
            "איך",
            "מה",
            "מהו",
            "מהי",
            "מהם",
            "מהן",
            "עושים",
            "עושה",
            "צריך",
            "צריכים",
            "אפשר",
            "יש",
            "של",
            "את",
            "עם",
            "על",
            "לפי",
            "מתי",
            "איפה",
            "כתוב",
            "לי",
            "בבקשה",
        }
    )

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
                            query_match_bonus=(
                                self._query_match_bonus(
                                    result,
                                    search_query,
                                )
                            ),
                            semantic_mode_bonus=(
                                self._semantic_mode_bonus(
                                    result,
                                    query,
                                )
                            ),
                            intent_title_bonus=(
                                self._intent_title_bonus(
                                    result,
                                    rewrite,
                                )
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
                candidate.query_match_bonus = max(
                    candidate.query_match_bonus,
                    self._query_match_bonus(
                        result,
                        search_query,
                    ),
                )

                if result.rank > candidate.result.rank:
                    candidate.result = result
                    candidate.semantic_mode_bonus = (
                        self._semantic_mode_bonus(
                            result,
                            query,
                        )
                    )

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

        authority_bonus = (
            cls._document_authority_bonus(
                candidate.result
            )
        )

        return round(
            candidate.best_rank
            + repeated_bonus
            + original_bonus
            + metadata_bonus
            + early_query_bonus
            + candidate.query_match_bonus
            + candidate.semantic_mode_bonus
            + candidate.intent_title_bonus
            + authority_bonus,
            6,
        )

    @classmethod
    def _intent_title_bonus(
        cls,
        result: KnowledgeSearchResult,
        rewrite: QueryRewrite,
    ) -> float:
        """
        Reward exact agreement between detected query intent and title.

        Query rewriting has already resolved domain phrases into
        canonical aliases and explicit document names. This bonus uses
        that existing information without adding entity-specific
        ranking rules.
        """

        normalized_title = cls._normalize_match_text(
            result.title
        )

        intended_titles = {
            cls._normalize_match_text(value)
            for value in (
                *rewrite.matched_document_names,
                *rewrite.matched_aliases,
            )
            if value.strip()
        }

        if (
            normalized_title
            and normalized_title in intended_titles
        ):
            return cls.INTENT_TITLE_MATCH_BONUS

        return 0.0

    @classmethod
    def _semantic_mode_bonus(
        cls,
        result: KnowledgeSearchResult,
        original_query: str,
    ) -> float:
        normalized_query = cls._normalize_match_text(
            original_query
        )
        normalized_title = cls._normalize_match_text(
            result.title
        )
        normalized_type = cls._normalize_match_text(
            result.document_type or ""
        )

        if cls._contains_signal(
            normalized_query,
            cls._OVERVIEW_SIGNALS,
        ):
            return cls._overview_mode_bonus(
                result=result,
                normalized_query=normalized_query,
                normalized_title=normalized_title,
                normalized_type=normalized_type,
            )

        if cls._contains_signal(
            normalized_query,
            cls._CHECKLIST_SIGNALS,
        ):
            if (
                "צ'קליסט" in normalized_title
                or "צ׳קליסט" in normalized_title
                or normalized_type == "צ'קליסט"
                or normalized_type == "צ׳קליסט"
            ):
                return (
                    cls.CHECKLIST_QUERY_CHECKLIST_BONUS
                )

            if normalized_type.startswith("נוהל"):
                return -(
                    cls.CHECKLIST_QUERY_PROCEDURE_PENALTY
                )

        if cls._contains_signal(
            normalized_query,
            cls._SYSTEM_SIGNALS,
        ):
            if (
                normalized_type == "מדריך מערכת"
                or normalized_type == "מערכת"
                or normalized_title.startswith("מערכת ")
            ):
                return (
                    cls.SYSTEM_QUERY_SYSTEM_GUIDE_BONUS
                )

        if cls._contains_signal(
            normalized_query,
            cls._PROCEDURE_SIGNALS,
        ):
            if normalized_type.startswith("נוהל"):
                return (
                    cls.PROCEDURE_QUERY_PROCEDURE_BONUS
                )

        return 0.0

    @classmethod
    def _overview_mode_bonus(
        cls,
        *,
        result: KnowledgeSearchResult,
        normalized_query: str,
        normalized_title: str,
        normalized_type: str,
    ) -> float:
        bonus = 0.0

        query_terms = cls._meaningful_terms(
            normalized_query
        )
        title_terms = cls._meaningful_terms(
            normalized_title
        )

        if normalized_title == normalized_query:
            bonus += cls.OVERVIEW_EXACT_TITLE_BONUS
        elif normalized_title in normalized_query:
            bonus += cls.OVERVIEW_EXACT_TITLE_BONUS
        elif query_terms:
            coverage = (
                len(query_terms.intersection(title_terms))
                / len(query_terms)
            )

            if coverage >= 0.65:
                bonus += (
                    cls.OVERVIEW_HIGH_TITLE_COVERAGE_BONUS
                )

        if (
            normalized_type in {
                "ידע ארגוני",
                "פורטל",
                "אחר",
            }
            or normalized_title in {
                "ציות ורגולציה",
            }
        ):
            bonus += (
                cls.OVERVIEW_KNOWLEDGE_DOCUMENT_BONUS
            )

        if normalized_type.startswith("נוהל"):
            bonus -= cls.OVERVIEW_PROCEDURE_PENALTY

        return bonus

    @staticmethod
    def _contains_signal(
        value: str,
        signals: tuple[str, ...],
    ) -> bool:
        return any(
            signal in value
            for signal in signals
        )

    @classmethod
    def _query_match_bonus(
        cls,
        result: KnowledgeSearchResult,
        query: str,
    ) -> float:
        normalized_query = cls._normalize_match_text(
            query
        )
        normalized_title = cls._normalize_match_text(
            result.title
        )

        if not normalized_query:
            return 0.0

        title_bonus = 0.0

        if normalized_title == normalized_query:
            title_bonus = cls.EXACT_TITLE_MATCH_BONUS
        elif (
            len(normalized_query) >= 4
            and normalized_query in normalized_title
        ):
            title_bonus = cls.TITLE_PHRASE_MATCH_BONUS
        else:
            query_terms = cls._meaningful_terms(
                normalized_query
            )
            title_terms = cls._meaningful_terms(
                normalized_title
            )

            if query_terms:
                coverage = (
                    len(query_terms.intersection(title_terms))
                    / len(query_terms)
                )

                if coverage >= 0.8:
                    title_bonus = (
                        cls.HIGH_TITLE_COVERAGE_BONUS
                    )
                elif coverage >= 0.5:
                    title_bonus = (
                        cls.MEDIUM_TITLE_COVERAGE_BONUS
                    )

        heading_text = cls._normalize_match_text(
            " ".join(result.heading_path)
        )
        content_text = cls._normalize_match_text(
            result.content
        )

        phrase_bonus = 0.0

        if (
            len(normalized_query) >= 3
            and normalized_query in heading_text
        ):
            phrase_bonus = max(
                phrase_bonus,
                cls.HEADING_PHRASE_MATCH_BONUS,
            )

        if (
            3 <= len(normalized_query) <= 100
            and normalized_query in content_text
        ):
            phrase_bonus = max(
                phrase_bonus,
                cls.CONTENT_PHRASE_MATCH_BONUS,
            )

        return title_bonus + phrase_bonus

    @classmethod
    def _document_authority_bonus(
        cls,
        result: KnowledgeSearchResult,
    ) -> float:
        bonus = 0.0

        normalized_status = cls._normalize_match_text(
            result.status or ""
        )
        normalized_type = cls._normalize_match_text(
            result.document_type or ""
        )

        if normalized_status in {
            "מאושר",
            "מאושר לפרסום",
            "פעיל",
        }:
            bonus += cls.APPROVED_STATUS_BONUS

        if normalized_type.startswith("נוהל"):
            bonus += cls.PROCEDURE_DOCUMENT_BONUS
        elif normalized_type in {
            "הדרכה",
            "מדריך",
        }:
            bonus += cls.TRAINING_DOCUMENT_BONUS
        elif normalized_type == "מדריך מערכת":
            bonus += cls.SYSTEM_GUIDE_DOCUMENT_BONUS

        return bonus

    @classmethod
    def _meaningful_terms(
        cls,
        value: str,
    ) -> frozenset[str]:
        return frozenset(
            token
            for token in cls._TOKEN_PATTERN.findall(
                value
            )
            if (
                len(token) >= 2
                and token not in cls._QUERY_STOP_WORDS
            )
        )

    @staticmethod
    def _normalize_match_text(
        value: str,
    ) -> str:
        return " ".join(
            value.casefold().split()
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
