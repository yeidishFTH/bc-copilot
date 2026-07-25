from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.services.knowledge.models import KnowledgeSearchResult


@dataclass(frozen=True, slots=True)
class KnowledgeContextSource:
    """One selected source included in an LLM-ready context."""

    index: int
    page_id: str
    revision_id: str
    chunk_id: str
    title: str
    heading_path: tuple[str, ...]
    canonical_url: str
    content: str
    rank: float


@dataclass(frozen=True, slots=True)
class KnowledgeContext:
    """Retrieval context prepared for a future RAG model."""

    query: str
    text: str
    sources: tuple[KnowledgeContextSource, ...]
    character_count: int
    estimated_tokens: int
    truncated: bool


@runtime_checkable
class KnowledgeRetriever(Protocol):
    """Retrieval operations required by KnowledgeContextService."""

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        ...


class KnowledgeContextBuilder:
    """
    Convert ranked search results into a bounded, source-aware context.

    Selection rules:
    - preserve retrieval ranking order;
    - remove duplicate chunks and duplicate content;
    - limit chunks from the same page;
    - enforce a hard character budget;
    - expose every selected source separately for citations.
    """

    DEFAULT_MAX_CHARACTERS = 12_000
    DEFAULT_MAX_CHUNKS = 8
    DEFAULT_MAX_CHUNKS_PER_PAGE = 3
    MIN_MAX_CHARACTERS = 500
    MAX_MAX_CHARACTERS = 100_000
    MAX_CHUNKS = 50

    def build(
        self,
        query: str,
        results: Sequence[KnowledgeSearchResult],
        *,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
        max_chunks: int = DEFAULT_MAX_CHUNKS,
        max_chunks_per_page: int = DEFAULT_MAX_CHUNKS_PER_PAGE,
    ) -> KnowledgeContext:
        normalized_query = self._normalize_query(query)
        normalized_max_characters = self._validate_max_characters(
            max_characters
        )
        normalized_max_chunks = self._validate_positive_integer(
            max_chunks,
            field_name="max_chunks",
            maximum=self.MAX_CHUNKS,
        )
        normalized_per_page = self._validate_positive_integer(
            max_chunks_per_page,
            field_name="max_chunks_per_page",
            maximum=self.MAX_CHUNKS,
        )

        selected: list[KnowledgeContextSource] = []
        rendered_blocks: list[str] = []
        seen_chunk_ids: set[str] = set()
        seen_content: set[tuple[str, tuple[str, ...], str]] = set()
        page_counts: Counter[str] = Counter()
        truncated = False

        for result in results:
            fingerprint = (
                result.page_id,
                result.heading_path,
                self._normalize_content(result.content),
            )

            if result.chunk_id in seen_chunk_ids:
                continue

            if fingerprint in seen_content:
                continue

            if page_counts[result.page_id] >= normalized_per_page:
                truncated = True
                continue

            if len(selected) >= normalized_max_chunks:
                truncated = True
                break

            source_index = len(selected) + 1
            full_source = self._to_source(
                result,
                index=source_index,
            )
            full_block = self._render_source(full_source)
            separator = "\n\n" if rendered_blocks else ""
            projected_length = (
                sum(len(block) for block in rendered_blocks)
                + (2 * max(len(rendered_blocks) - 1, 0))
                + len(separator)
                + len(full_block)
            )

            if projected_length <= normalized_max_characters:
                selected.append(full_source)
                rendered_blocks.append(full_block)
                seen_chunk_ids.add(result.chunk_id)
                seen_content.add(fingerprint)
                page_counts[result.page_id] += 1
                continue

            truncated = True

            if rendered_blocks:
                break

            shortened_source = self._truncate_first_source(
                full_source,
                max_characters=normalized_max_characters,
            )

            if shortened_source is not None:
                selected.append(shortened_source)
                rendered_blocks.append(
                    self._render_source(shortened_source)
                )
                seen_chunk_ids.add(result.chunk_id)
                seen_content.add(fingerprint)
                page_counts[result.page_id] += 1

            break

        context_text = "\n\n".join(rendered_blocks)
        character_count = len(context_text)

        return KnowledgeContext(
            query=normalized_query,
            text=context_text,
            sources=tuple(selected),
            character_count=character_count,
            estimated_tokens=math.ceil(character_count / 4),
            truncated=truncated,
        )

    @staticmethod
    def _to_source(
        result: KnowledgeSearchResult,
        *,
        index: int,
    ) -> KnowledgeContextSource:
        return KnowledgeContextSource(
            index=index,
            page_id=result.page_id,
            revision_id=result.revision_id,
            chunk_id=result.chunk_id,
            title=result.title,
            heading_path=result.heading_path,
            canonical_url=result.canonical_url,
            content=result.content.strip(),
            rank=result.rank,
        )

    @classmethod
    def _render_source(
        cls,
        source: KnowledgeContextSource,
    ) -> str:
        heading = (
            " > ".join(source.heading_path)
            if source.heading_path
            else "פתיח העמוד"
        )

        return "\n".join(
            (
                f"[SOURCE {source.index}]",
                f"כותרת: {source.title}",
                f"סעיף: {heading}",
                f"קישור: {source.canonical_url}",
                f"דירוג: {source.rank:.6f}",
                "תוכן:",
                source.content,
            )
        )

    @classmethod
    def _truncate_first_source(
        cls,
        source: KnowledgeContextSource,
        *,
        max_characters: int,
    ) -> KnowledgeContextSource | None:
        empty_source = KnowledgeContextSource(
            index=source.index,
            page_id=source.page_id,
            revision_id=source.revision_id,
            chunk_id=source.chunk_id,
            title=source.title,
            heading_path=source.heading_path,
            canonical_url=source.canonical_url,
            content="",
            rank=source.rank,
        )
        empty_block = cls._render_source(empty_source)
        available_content = max_characters - len(empty_block)

        if available_content < 2:
            return None

        shortened_content = source.content[: available_content - 1].rstrip()

        return KnowledgeContextSource(
            index=source.index,
            page_id=source.page_id,
            revision_id=source.revision_id,
            chunk_id=source.chunk_id,
            title=source.title,
            heading_path=source.heading_path,
            canonical_url=source.canonical_url,
            content=f"{shortened_content}…",
            rank=source.rank,
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        normalized = " ".join(query.split())

        if not normalized:
            raise ValueError("query cannot be empty")

        return normalized

    @staticmethod
    def _normalize_content(content: str) -> str:
        return " ".join(content.split()).casefold()

    @classmethod
    def _validate_max_characters(
        cls,
        value: int,
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("max_characters must be an integer")

        if (
            value < cls.MIN_MAX_CHARACTERS
            or value > cls.MAX_MAX_CHARACTERS
        ):
            raise ValueError(
                "max_characters must be between "
                f"{cls.MIN_MAX_CHARACTERS} and "
                f"{cls.MAX_MAX_CHARACTERS}"
            )

        return value

    @staticmethod
    def _validate_positive_integer(
        value: int,
        *,
        field_name: str,
        maximum: int,
    ) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer")

        if value < 1 or value > maximum:
            raise ValueError(
                f"{field_name} must be between 1 and {maximum}"
            )

        return value


class KnowledgeContextService:
    """Retrieve candidates and prepare bounded context for future RAG use."""

    DEFAULT_SEARCH_LIMIT = 30
    MAX_SEARCH_LIMIT = 100

    def __init__(
        self,
        retrieval: KnowledgeRetriever,
        *,
        builder: KnowledgeContextBuilder | None = None,
    ) -> None:
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
        max_chunks: int = KnowledgeContextBuilder.DEFAULT_MAX_CHUNKS,
        max_chunks_per_page: int = (
            KnowledgeContextBuilder.DEFAULT_MAX_CHUNKS_PER_PAGE
        ),
    ) -> KnowledgeContext:
        normalized_search_limit = (
            KnowledgeContextBuilder._validate_positive_integer(
                search_limit,
                field_name="search_limit",
                maximum=self.MAX_SEARCH_LIMIT,
            )
        )

        results = await self._retrieval.search(
            query,
            limit=normalized_search_limit,
            namespace_ids=namespace_ids,
        )

        return self._builder.build(
            query,
            results,
            max_characters=max_characters,
            max_chunks=max_chunks,
            max_chunks_per_page=max_chunks_per_page,
        )
