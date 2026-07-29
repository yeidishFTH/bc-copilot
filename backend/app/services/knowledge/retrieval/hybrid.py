from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol, runtime_checkable

from app.services.knowledge.models import (
    KnowledgeSearchResult,
)


@runtime_checkable
class HybridKnowledgeRetriever(Protocol):
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        ...


class HybridRetrievalService:
    """
    Merge lexical and semantic retrieval using Reciprocal Rank Fusion.

    RRF intentionally uses result positions rather than incomparable raw
    scores. Full-text scores may exceed 1.0, while semantic cosine similarity
    normally remains between -1.0 and 1.0. Rank fusion avoids arbitrary score
    normalization and rewards chunks appearing in both result sets.
    """

    DEFAULT_LIMIT = 10
    DEFAULT_CANDIDATE_MULTIPLIER = 3
    DEFAULT_RRF_CONSTANT = 60

    MAX_LIMIT = 100
    MAX_CANDIDATE_MULTIPLIER = 10

    def __init__(
        self,
        *,
        lexical: HybridKnowledgeRetriever,
        semantic: HybridKnowledgeRetriever,
        rrf_constant: int = DEFAULT_RRF_CONSTANT,
        candidate_multiplier: int = DEFAULT_CANDIDATE_MULTIPLIER,
    ) -> None:
        if not isinstance(
            lexical,
            HybridKnowledgeRetriever,
        ):
            raise TypeError(
                "lexical must implement HybridKnowledgeRetriever"
            )

        if not isinstance(
            semantic,
            HybridKnowledgeRetriever,
        ):
            raise TypeError(
                "semantic must implement HybridKnowledgeRetriever"
            )

        self._lexical = lexical
        self._semantic = semantic
        self._rrf_constant = self._validate_positive_integer(
            rrf_constant,
            field_name="rrf_constant",
            maximum=10_000,
        )
        self._candidate_multiplier = (
            self._validate_positive_integer(
                candidate_multiplier,
                field_name="candidate_multiplier",
                maximum=self.MAX_CANDIDATE_MULTIPLIER,
            )
        )

    async def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        normalized_query = self._normalize_query(query)
        normalized_limit = self._normalize_limit(limit)
        normalized_namespaces = (
            self._normalize_namespace_ids(
                namespace_ids
            )
        )

        candidate_limit = min(
            normalized_limit
            * self._candidate_multiplier,
            self.MAX_LIMIT,
        )

        lexical_results, semantic_results = (
            await asyncio.gather(
                self._lexical.search(
                    normalized_query,
                    limit=candidate_limit,
                    namespace_ids=normalized_namespaces,
                ),
                self._semantic.search(
                    normalized_query,
                    limit=candidate_limit,
                    namespace_ids=normalized_namespaces,
                ),
            )
        )

        return self._fuse(
            lexical_results,
            semantic_results,
            limit=normalized_limit,
            rrf_constant=self._rrf_constant,
        )

    @classmethod
    def _fuse(
        cls,
        lexical_results: Sequence[
            KnowledgeSearchResult
        ],
        semantic_results: Sequence[
            KnowledgeSearchResult
        ],
        *,
        limit: int,
        rrf_constant: int,
    ) -> tuple[KnowledgeSearchResult, ...]:
        representatives: dict[
            str,
            KnowledgeSearchResult,
        ] = {}
        scores: dict[str, float] = {}
        lexical_positions: dict[str, int] = {}
        semantic_positions: dict[str, int] = {}

        for position, result in enumerate(
            lexical_results,
            start=1,
        ):
            if result.chunk_id in lexical_positions:
                continue

            lexical_positions[result.chunk_id] = position
            representatives.setdefault(
                result.chunk_id,
                result,
            )
            scores[result.chunk_id] = (
                scores.get(result.chunk_id, 0.0)
                + 1.0 / (rrf_constant + position)
            )

        for position, result in enumerate(
            semantic_results,
            start=1,
        ):
            if result.chunk_id in semantic_positions:
                continue

            semantic_positions[result.chunk_id] = position

            representative = representatives.get(
                result.chunk_id
            )

            if (
                representative is None
                or cls._metadata_quality(result)
                > cls._metadata_quality(
                    representative
                )
            ):
                representatives[
                    result.chunk_id
                ] = result

            scores[result.chunk_id] = (
                scores.get(result.chunk_id, 0.0)
                + 1.0 / (rrf_constant + position)
            )

        ranked_chunk_ids = sorted(
            scores,
            key=lambda chunk_id: (
                -scores[chunk_id],
                min(
                    lexical_positions.get(
                        chunk_id,
                        10_000,
                    ),
                    semantic_positions.get(
                        chunk_id,
                        10_000,
                    ),
                ),
                representatives[
                    chunk_id
                ].title.casefold(),
                representatives[
                    chunk_id
                ].position,
                chunk_id,
            ),
        )[:limit]

        return tuple(
            replace(
                representatives[chunk_id],
                rank=round(
                    scores[chunk_id],
                    8,
                ),
            )
            for chunk_id in ranked_chunk_ids
        )

    @staticmethod
    def _metadata_quality(
        result: KnowledgeSearchResult,
    ) -> int:
        values = (
            result.status,
            result.document_type,
            result.portal,
            result.category,
            result.owner,
            result.responsible_department,
            result.updated_on,
            result.version,
        )

        return (
            sum(
                value is not None
                for value in values
            )
            + int(bool(result.audience))
        )

    @staticmethod
    def _normalize_query(
        query: str,
    ) -> str:
        if not isinstance(query, str):
            raise ValueError(
                "query must be a string"
            )

        normalized = " ".join(query.split())

        if not normalized:
            raise ValueError(
                "query cannot be empty"
            )

        return normalized

    @classmethod
    def _normalize_limit(
        cls,
        limit: int,
    ) -> int:
        return cls._validate_positive_integer(
            limit,
            field_name="limit",
            maximum=cls.MAX_LIMIT,
        )

    @staticmethod
    def _normalize_namespace_ids(
        namespace_ids: Sequence[int] | None,
    ) -> tuple[int, ...] | None:
        if namespace_ids is None:
            return None

        normalized: list[int] = []

        for namespace_id in namespace_ids:
            if (
                isinstance(namespace_id, bool)
                or not isinstance(namespace_id, int)
                or namespace_id < 0
            ):
                raise ValueError(
                    "namespace_ids must contain "
                    "non-negative integers"
                )

            if namespace_id not in normalized:
                normalized.append(namespace_id)

        if not normalized:
            raise ValueError(
                "namespace_ids cannot be empty"
            )

        return tuple(normalized)

    @staticmethod
    def _validate_positive_integer(
        value: int,
        *,
        field_name: str,
        maximum: int,
    ) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
        ):
            raise ValueError(
                f"{field_name} must be an integer"
            )

        if value < 1 or value > maximum:
            raise ValueError(
                f"{field_name} must be between "
                f"1 and {maximum}"
            )

        return value
