from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeChunk,
    KnowledgePage,
    KnowledgeRevision,
)
from app.services.knowledge.models import KnowledgeSearchResult


class KnowledgeSearchRepository:
    """Retrieve ranked knowledge chunks using PostgreSQL full-text search."""

    DEFAULT_LIMIT = 10
    MAX_LIMIT = 100

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_chunks(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
    ) -> list[KnowledgeSearchResult]:
        normalized_query = self._normalize_query(query)
        normalized_limit = self._normalize_limit(limit)
        normalized_namespaces = self._normalize_namespace_ids(
            namespace_ids
        )

        search_query = func.plainto_tsquery(
            "simple",
            normalized_query,
        )
        rank = func.ts_rank_cd(
            KnowledgeChunk.search_vector,
            search_query,
        ).label("rank")

        statement = (
            select(
                KnowledgePage.id.label("page_id"),
                KnowledgeRevision.id.label("revision_id"),
                KnowledgeChunk.id.label("chunk_id"),
                KnowledgePage.wiki_page_id,
                KnowledgeRevision.wiki_revision_id,
                KnowledgePage.title,
                KnowledgePage.canonical_url,
                KnowledgePage.namespace_id,
                KnowledgeChunk.position,
                KnowledgeChunk.heading_path,
                KnowledgeChunk.content,
                KnowledgeChunk.token_count,
                rank,
            )
            .select_from(KnowledgeChunk)
            .join(
                KnowledgeRevision,
                KnowledgeRevision.id == KnowledgeChunk.revision_id,
            )
            .join(
                KnowledgePage,
                KnowledgePage.id == KnowledgeRevision.page_id,
            )
            .where(
                KnowledgePage.is_active.is_(True),
                KnowledgePage.latest_revision_id
                == KnowledgeRevision.wiki_revision_id,
                KnowledgeChunk.search_vector.is_not(None),
                KnowledgeChunk.search_vector.op("@@")(search_query),
            )
            .order_by(
                desc(rank),
                KnowledgePage.title.asc(),
                KnowledgeChunk.position.asc(),
            )
            .limit(normalized_limit)
        )

        if normalized_namespaces is not None:
            statement = statement.where(
                KnowledgePage.namespace_id.in_(
                    normalized_namespaces
                )
            )

        result = await self._session.execute(statement)

        return [
            self._row_to_result(row)
            for row in result.all()
        ]

    @classmethod
    def build_search_statement(
        cls,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
    ) -> Select:
        """
        Build the SQL statement without executing it.

        This is useful for inspection and focused unit testing.
        """

        normalized_query = cls._normalize_query(query)
        normalized_limit = cls._normalize_limit(limit)
        normalized_namespaces = cls._normalize_namespace_ids(
            namespace_ids
        )

        search_query = func.plainto_tsquery(
            "simple",
            normalized_query,
        )
        rank = func.ts_rank_cd(
            KnowledgeChunk.search_vector,
            search_query,
        ).label("rank")

        statement = (
            select(
                KnowledgePage.id.label("page_id"),
                KnowledgeRevision.id.label("revision_id"),
                KnowledgeChunk.id.label("chunk_id"),
                KnowledgePage.wiki_page_id,
                KnowledgeRevision.wiki_revision_id,
                KnowledgePage.title,
                KnowledgePage.canonical_url,
                KnowledgePage.namespace_id,
                KnowledgeChunk.position,
                KnowledgeChunk.heading_path,
                KnowledgeChunk.content,
                KnowledgeChunk.token_count,
                rank,
            )
            .select_from(KnowledgeChunk)
            .join(
                KnowledgeRevision,
                KnowledgeRevision.id == KnowledgeChunk.revision_id,
            )
            .join(
                KnowledgePage,
                KnowledgePage.id == KnowledgeRevision.page_id,
            )
            .where(
                KnowledgePage.is_active.is_(True),
                KnowledgePage.latest_revision_id
                == KnowledgeRevision.wiki_revision_id,
                KnowledgeChunk.search_vector.is_not(None),
                KnowledgeChunk.search_vector.op("@@")(search_query),
            )
            .order_by(
                desc(rank),
                KnowledgePage.title.asc(),
                KnowledgeChunk.position.asc(),
            )
            .limit(normalized_limit)
        )

        if normalized_namespaces is not None:
            statement = statement.where(
                KnowledgePage.namespace_id.in_(
                    normalized_namespaces
                )
            )

        return statement

    @staticmethod
    def _row_to_result(row: object) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            page_id=str(row.page_id),
            revision_id=str(row.revision_id),
            chunk_id=str(row.chunk_id),
            wiki_page_id=row.wiki_page_id,
            wiki_revision_id=row.wiki_revision_id,
            title=row.title,
            canonical_url=row.canonical_url,
            namespace_id=row.namespace_id,
            position=row.position,
            heading_path=tuple(row.heading_path),
            content=row.content,
            token_count=row.token_count,
            rank=float(row.rank),
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        normalized = " ".join(query.split())

        if not normalized:
            raise ValueError("query cannot be empty")

        return normalized

    @classmethod
    def _normalize_limit(cls, limit: int) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")

        if limit < 1 or limit > cls.MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {cls.MAX_LIMIT}"
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
                    "namespace_ids must contain non-negative integers"
                )

            if namespace_id not in normalized:
                normalized.append(namespace_id)

        if not normalized:
            raise ValueError("namespace_ids cannot be empty")

        return tuple(normalized)
