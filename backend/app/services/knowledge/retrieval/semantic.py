from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.services.knowledge.embeddings import (
    EmbeddingGenerator,
    EmbeddingVector,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)


@runtime_checkable
class KnowledgeVectorSearchReader(Protocol):
    async def search_chunks(
        self,
        query_embedding: EmbeddingVector,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> list[KnowledgeSearchResult]:
        ...


class SemanticRetrievalService:
    """
    Convert a text query into one embedding and retrieve similar chunks.

    The service is intentionally isolated from full-text retrieval.
    Hybrid merging will be introduced only after semantic retrieval has
    independent tests and a verified PostgreSQL integration path.
    """

    DEFAULT_LIMIT = 10
    MAX_LIMIT = 100

    def __init__(
        self,
        *,
        generator: EmbeddingGenerator,
        search: KnowledgeVectorSearchReader,
    ) -> None:
        if not isinstance(generator, EmbeddingGenerator):
            raise TypeError(
                "generator must implement EmbeddingGenerator"
            )

        if not isinstance(
            search,
            KnowledgeVectorSearchReader,
        ):
            raise TypeError(
                "search must implement KnowledgeVectorSearchReader"
            )

        self._generator = generator
        self._search = search

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

        vectors = await self._generator.generate(
            (normalized_query,)
        )

        if len(vectors) != 1:
            raise RuntimeError(
                "embedding generator returned "
                "an unexpected number of vectors"
            )

        results = await self._search.search_chunks(
            vectors[0],
            limit=normalized_limit,
            namespace_ids=normalized_namespaces,
        )

        return self._deduplicate(results)[
            :normalized_limit
        ]

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
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
        ):
            raise ValueError(
                "limit must be an integer"
            )

        if (
            limit < 1
            or limit > cls.MAX_LIMIT
        ):
            raise ValueError(
                "limit must be between "
                f"1 and {cls.MAX_LIMIT}"
            )

        return limit

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
    def _deduplicate(
        results: Sequence[KnowledgeSearchResult],
    ) -> tuple[KnowledgeSearchResult, ...]:
        unique: list[KnowledgeSearchResult] = []
        seen: set[str] = set()

        for result in results:
            if result.chunk_id in seen:
                continue

            seen.add(result.chunk_id)
            unique.append(result)

        return tuple(unique)
