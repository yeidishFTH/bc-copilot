from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.services.copilot.multi_query_retrieval import (
    MultiQueryRetrievalResult,
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

        return self._builder.build(
            query,
            retrieval_result.results,
            max_characters=max_characters,
            max_chunks=max_chunks,
            max_chunks_per_page=max_chunks_per_page,
        )
