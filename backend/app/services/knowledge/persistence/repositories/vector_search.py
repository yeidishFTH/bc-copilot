from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeChunk,
    KnowledgePage,
    KnowledgeRevision,
    KnowledgeRevisionMetadata,
)
from app.services.knowledge.embeddings import (
    EmbeddingVector,
)
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)


class KnowledgeVectorSearchRepository:
    """
    Retrieve semantically similar knowledge chunks using pgvector.

    Ranking is expressed as cosine similarity:

        similarity = 1 - cosine_distance

    Higher rank values are therefore better, matching the ordering
    convention already used throughout retrieval and context building.
    """

    EMBEDDING_DIMENSIONS = 1536
    DEFAULT_LIMIT = 10
    MAX_LIMIT = 100

    def __init__(
        self,
        session: AsyncSession,
        *,
        access_role: str | None = None,
    ) -> None:
        self._session = session
        self._access_role = self._normalize_access_role(
            access_role
        )

    async def search_chunks(
        self,
        query_embedding: EmbeddingVector,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
    ) -> list[KnowledgeSearchResult]:
        statement = self.build_search_statement(
            query_embedding,
            limit=limit,
            namespace_ids=namespace_ids,
            access_role=self._access_role,
        )

        result = await self._session.execute(
            statement
        )

        return [
            self._row_to_result(row)
            for row in result.all()
        ]

    @classmethod
    def build_search_statement(
        cls,
        query_embedding: EmbeddingVector,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
        access_role: str | None = None,
    ) -> Select:
        normalized_embedding = (
            cls._normalize_embedding(
                query_embedding
            )
        )
        normalized_limit = cls._normalize_limit(
            limit
        )
        normalized_namespaces = (
            cls._normalize_namespace_ids(
                namespace_ids
            )
        )
        normalized_access_role = (
            cls._normalize_access_role(
                access_role
            )
        )

        distance = (
            KnowledgeChunk.embedding.cosine_distance(
                list(normalized_embedding.values)
            )
        ).label("distance")

        similarity = (
            1.0 - distance
        ).label("rank")

        statement = (
            select(
                KnowledgePage.id.label("page_id"),
                KnowledgeRevision.id.label(
                    "revision_id"
                ),
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
                similarity,
                distance,
                KnowledgeRevisionMetadata.status,
                KnowledgeRevisionMetadata.document_type,
                KnowledgeRevisionMetadata.portal,
                KnowledgeRevisionMetadata.category,
                KnowledgeRevisionMetadata.audience,
                KnowledgeRevisionMetadata.access_roles,
                KnowledgeRevisionMetadata.owner,
                (
                    KnowledgeRevisionMetadata
                    .responsible_department
                ),
                KnowledgeRevisionMetadata.updated_on,
                KnowledgeRevisionMetadata.version,
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
            .outerjoin(
                KnowledgeRevisionMetadata,
                (
                    KnowledgeRevisionMetadata
                    .revision_id
                    == KnowledgeRevision.id
                ),
            )
            .where(
                KnowledgePage.is_active.is_(True),
                KnowledgePage.latest_revision_id
                == KnowledgeRevision.wiki_revision_id,
                KnowledgeChunk.embedding.is_not(None),
                ~KnowledgePage.title.startswith(
                    "Archive/"
                ),
                ~KnowledgePage.title.startswith(
                    "Sandbox/"
                ),
                ~func.lower(
                    func.ltrim(
                        KnowledgeChunk.content
                    )
                ).like("#redirect%"),
                ~func.ltrim(
                    KnowledgeChunk.content
                ).like("#הפניה%"),
            )
            .order_by(
                desc(similarity),
                KnowledgePage.title.asc(),
                KnowledgeChunk.position.asc(),
                KnowledgeChunk.id.asc(),
            )
            .limit(normalized_limit)
        )

        if normalized_namespaces is not None:
            statement = statement.where(
                KnowledgePage.namespace_id.in_(
                    normalized_namespaces
                )
            )

        statement = statement.where(
            cls._access_condition(
                normalized_access_role
            )
        )

        return statement

    @staticmethod
    def _normalize_access_role(
        access_role: str | None,
    ) -> str | None:
        if access_role is None:
            return None

        if not isinstance(access_role, str):
            raise ValueError(
                "access_role must be a string or None"
            )

        normalized = access_role.strip().casefold()

        allowed_roles = {
            "branch_user",
            "management",
            "administrator",
        }

        if normalized not in allowed_roles:
            raise ValueError(
                "access_role is not recognized"
            )

        return normalized

    @staticmethod
    def _access_condition(
        access_role: str | None,
    ):
        open_access = (
            func.coalesce(
                func.cardinality(
                    KnowledgeRevisionMetadata.access_roles
                ),
                0,
            )
            == 0
        )

        if access_role is None:
            return open_access

        return open_access | (
            KnowledgeRevisionMetadata
            .access_roles
            .any(access_role)
        )

    @classmethod
    def _normalize_embedding(
        cls,
        embedding: EmbeddingVector,
    ) -> EmbeddingVector:
        if not isinstance(
            embedding,
            EmbeddingVector,
        ):
            raise ValueError(
                "query_embedding must be an "
                "EmbeddingVector"
            )

        if (
            embedding.dimensions
            != cls.EMBEDDING_DIMENSIONS
        ):
            raise ValueError(
                "query_embedding must contain "
                f"{cls.EMBEDDING_DIMENSIONS} dimensions"
            )

        return embedding

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
    def _row_to_result(
        row: object,
    ) -> KnowledgeSearchResult:
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
            heading_path=tuple(
                row.heading_path or ()
            ),
            content=row.content,
            token_count=row.token_count,
            rank=float(row.rank),
            status=getattr(
                row,
                "status",
                None,
            ),
            document_type=getattr(
                row,
                "document_type",
                None,
            ),
            portal=getattr(
                row,
                "portal",
                None,
            ),
            category=getattr(
                row,
                "category",
                None,
            ),
            audience=tuple(
                getattr(
                    row,
                    "audience",
                    None,
                )
                or ()
            ),
            access_roles=tuple(
                getattr(
                    row,
                    "access_roles",
                    None,
                )
                or ()
            ),
            owner=getattr(
                row,
                "owner",
                None,
            ),
            responsible_department=getattr(
                row,
                "responsible_department",
                None,
            ),
            updated_on=getattr(
                row,
                "updated_on",
                None,
            ),
            version=getattr(
                row,
                "version",
                None,
            ),
        )
