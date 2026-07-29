from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import bindparam, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeChunk,
    KnowledgePage,
    KnowledgeRevision,
)
from app.services.knowledge.embeddings import (
    EmbeddingVector,
)


@dataclass(frozen=True, slots=True)
class KnowledgeEmbeddingCandidate:
    """
    One persisted knowledge chunk awaiting an embedding.

    The candidate contains only the source data required to build the
    provider-neutral embedding input. It does not expose SQLAlchemy models
    outside the persistence layer.
    """

    chunk_id: uuid.UUID
    title: str
    heading_path: tuple[str, ...]
    content: str
    position: int


class KnowledgeEmbeddingRepository:
    """
    Read and update persisted knowledge-chunk embeddings.

    Transaction ownership remains with the caller. Methods may execute and
    flush database statements, but they never commit or roll back.
    """

    EMBEDDING_DIMENSIONS = 1536
    DEFAULT_BATCH_SIZE = 50
    MAX_BATCH_SIZE = 500

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def fetch_pending(
        self,
        *,
        limit: int = DEFAULT_BATCH_SIZE,
    ) -> tuple[KnowledgeEmbeddingCandidate, ...]:
        """
        Return a deterministic batch of active latest-revision chunks.

        Only chunks whose embedding is currently NULL are returned. Once a
        caller stores and commits their vectors, the next invocation naturally
        advances to the next pending batch without offset bookkeeping.
        """

        normalized_limit = self._normalize_limit(limit)

        statement = (
            select(
                KnowledgeChunk.id.label("chunk_id"),
                KnowledgePage.title,
                KnowledgeChunk.heading_path,
                KnowledgeChunk.content,
                KnowledgeChunk.position,
            )
            .select_from(KnowledgeChunk)
            .join(
                KnowledgeRevision,
                KnowledgeRevision.id
                == KnowledgeChunk.revision_id,
            )
            .join(
                KnowledgePage,
                KnowledgePage.id
                == KnowledgeRevision.page_id,
            )
            .where(
                KnowledgePage.is_active.is_(True),
                KnowledgePage.latest_revision_id
                == KnowledgeRevision.wiki_revision_id,
                KnowledgeChunk.embedding.is_(None),
            )
            .order_by(
                KnowledgePage.title.asc(),
                KnowledgeChunk.position.asc(),
                KnowledgeChunk.id.asc(),
            )
            .limit(normalized_limit)
        )

        result = await self._session.execute(statement)

        return tuple(
            self._row_to_candidate(row)
            for row in result.all()
        )

    async def store_embeddings(
        self,
        embeddings: Mapping[
            uuid.UUID,
            EmbeddingVector,
        ],
    ) -> int:
        """
        Persist one validated vector for every supplied chunk identifier.

        The method uses an executemany UPDATE and flushes without committing.
        The caller may therefore commit each successful batch or roll it back
        atomically when generation or persistence fails.
        """

        normalized = self._normalize_embeddings(
            embeddings
        )

        if not normalized:
            return 0

        chunk_table = KnowledgeChunk.__table__

        statement = (
            update(chunk_table)
            .where(
                chunk_table.c.id
                == bindparam("target_chunk_id")
            )
            .values(
                embedding=bindparam(
                    "embedding_values"
                )
            )
        )

        parameters = [
            {
                "target_chunk_id": chunk_id,
                "embedding_values": list(
                    vector.values
                ),
            }
            for chunk_id, vector in normalized
        ]

        await self._session.execute(
            statement,
            parameters,
        )
        await self._session.flush()

        return len(parameters)

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
                "embedding batch limit must be an integer"
            )

        if limit < 1 or limit > cls.MAX_BATCH_SIZE:
            raise ValueError(
                "embedding batch limit must be between "
                f"1 and {cls.MAX_BATCH_SIZE}"
            )

        return limit

    @classmethod
    def _normalize_embeddings(
        cls,
        embeddings: Mapping[
            uuid.UUID,
            EmbeddingVector,
        ],
    ) -> tuple[
        tuple[uuid.UUID, EmbeddingVector],
        ...,
    ]:
        if not isinstance(embeddings, Mapping):
            raise ValueError(
                "embeddings must be a mapping"
            )

        normalized: list[
            tuple[uuid.UUID, EmbeddingVector]
        ] = []

        for chunk_id, vector in embeddings.items():
            if not isinstance(chunk_id, uuid.UUID):
                raise ValueError(
                    "embedding chunk identifiers "
                    "must be UUID values"
                )

            if not isinstance(
                vector,
                EmbeddingVector,
            ):
                raise ValueError(
                    "embedding values must be "
                    "EmbeddingVector instances"
                )

            if (
                vector.dimensions
                != cls.EMBEDDING_DIMENSIONS
            ):
                raise ValueError(
                    "embedding vector must contain "
                    f"{cls.EMBEDDING_DIMENSIONS} dimensions"
                )

            normalized.append(
                (chunk_id, vector)
            )

        normalized.sort(
            key=lambda item: item[0].hex
        )

        return tuple(normalized)

    @staticmethod
    def _row_to_candidate(
        row: object,
    ) -> KnowledgeEmbeddingCandidate:
        heading_path = getattr(
            row,
            "heading_path",
            None,
        )

        return KnowledgeEmbeddingCandidate(
            chunk_id=row.chunk_id,
            title=row.title,
            heading_path=tuple(
                heading_path or ()
            ),
            content=row.content,
            position=row.position,
        )
