from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgePage, KnowledgeRevision
from app.services.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.knowledge.persistence.mappers import (
    KnowledgePersistenceMapper,
)
from app.services.knowledge.persistence.results import (
    DocumentUpsertResult,
    DocumentUpsertStatus,
)


class KnowledgeDocumentRepository:
    """Persist the knowledge document aggregate without committing transactions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        mapper: type[KnowledgePersistenceMapper] = KnowledgePersistenceMapper,
    ) -> None:
        self._session = session
        self._mapper = mapper

    async def get_by_wiki_page_id(
        self,
        wiki_page_id: int,
    ) -> KnowledgePage | None:
        normalized_page_id = self._mapper.parse_positive_integer(
            wiki_page_id,
            field_name="wiki_page_id",
        )

        statement = select(KnowledgePage).where(
            KnowledgePage.wiki_page_id == normalized_page_id
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def get_revision_by_wiki_revision_id(
        self,
        wiki_revision_id: int,
    ) -> KnowledgeRevision | None:
        normalized_revision_id = self._mapper.parse_positive_integer(
            wiki_revision_id,
            field_name="wiki_revision_id",
        )

        statement = select(KnowledgeRevision).where(
            KnowledgeRevision.wiki_revision_id == normalized_revision_id
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        document: KnowledgeDocument,
        revision: KnowledgeDocumentRevision,
    ) -> DocumentUpsertResult:
        """
        Create or update one document aggregate.

        The repository flushes generated identifiers but never commits.
        Transaction ownership remains with the calling sync engine.
        """

        self._mapper.validate_document_revision_pair(
            document,
            revision,
        )

        wiki_page_id = self._mapper.parse_positive_integer(
            document.id,
            field_name="document.id",
        )
        wiki_revision_id = self._mapper.parse_positive_integer(
            revision.id,
            field_name="revision.id",
        )

        page = await self.get_by_wiki_page_id(wiki_page_id)

        if page is None:
            page = self._mapper.document_to_page(document)
            self._session.add(page)
            await self._session.flush()

            persistence_revision, persistence_content = (
                self._mapper.revision_to_models(
                    revision,
                    page=page,
                )
            )
            self._session.add_all(
                [persistence_revision, persistence_content]
            )
            await self._session.flush()

            return DocumentUpsertResult(
                status=DocumentUpsertStatus.created,
                page=page,
                revision=persistence_revision,
            )

        metadata_changed = self._mapper.apply_document_to_page(
            document,
            page,
        )

        existing_revision = (
            await self.get_revision_by_wiki_revision_id(
                wiki_revision_id
            )
        )

        if existing_revision is not None:
            if metadata_changed:
                await self._session.flush()

                return DocumentUpsertResult(
                    status=DocumentUpsertStatus.updated,
                    page=page,
                    revision=existing_revision,
                )

            return DocumentUpsertResult(
                status=DocumentUpsertStatus.unchanged,
                page=page,
                revision=existing_revision,
            )

        persistence_revision, persistence_content = (
            self._mapper.revision_to_models(
                revision,
                page=page,
            )
        )
        self._session.add_all(
            [persistence_revision, persistence_content]
        )
        await self._session.flush()

        return DocumentUpsertResult(
            status=DocumentUpsertStatus.updated,
            page=page,
            revision=persistence_revision,
        )
