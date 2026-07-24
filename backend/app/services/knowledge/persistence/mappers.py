from __future__ import annotations

import hashlib
import unicodedata

from app.db.models import KnowledgeContent, KnowledgePage, KnowledgeRevision
from app.services.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)


class KnowledgePersistenceMapper:
    """Map source-neutral knowledge models into SQLAlchemy persistence models."""

    @classmethod
    def document_to_page(
        cls,
        document: KnowledgeDocument,
    ) -> KnowledgePage:
        wiki_page_id = cls.parse_positive_integer(
            document.id,
            field_name="document.id",
        )
        latest_revision_id = cls.require_latest_revision_id(document)

        return KnowledgePage(
            wiki_page_id=wiki_page_id,
            namespace_id=document.namespace_id,
            title=document.title,
            normalized_title=cls.normalize_title(document.title),
            canonical_url=document.canonical_url,
            latest_revision_id=latest_revision_id,
            is_redirect=document.is_redirect,
            is_active=True,
        )

    @classmethod
    def apply_document_to_page(
        cls,
        document: KnowledgeDocument,
        page: KnowledgePage,
    ) -> bool:
        """Update mutable page metadata and return whether anything changed."""

        expected_page_id = cls.parse_positive_integer(
            document.id,
            field_name="document.id",
        )

        if page.wiki_page_id != expected_page_id:
            raise ValueError(
                "document.id does not match the persisted knowledge page"
            )

        values = {
            "namespace_id": document.namespace_id,
            "title": document.title,
            "normalized_title": cls.normalize_title(document.title),
            "canonical_url": document.canonical_url,
            "latest_revision_id": cls.require_latest_revision_id(document),
            "is_redirect": document.is_redirect,
            "is_active": True,
        }

        changed = False

        for field_name, value in values.items():
            if getattr(page, field_name) != value:
                setattr(page, field_name, value)
                changed = True

        return changed

    @classmethod
    def revision_to_models(
        cls,
        revision: KnowledgeDocumentRevision,
        *,
        page: KnowledgePage,
    ) -> tuple[KnowledgeRevision, KnowledgeContent]:
        wiki_revision_id = cls.parse_positive_integer(
            revision.id,
            field_name="revision.id",
        )
        parent_revision_id = cls.parse_optional_positive_integer(
            revision.parent_id,
            field_name="revision.parent_id",
        )

        content_sha256 = cls.calculate_sha256(revision.raw_content)

        persistence_revision = KnowledgeRevision(
            page=page,
            wiki_revision_id=wiki_revision_id,
            parent_revision_id=parent_revision_id,
            revision_timestamp=revision.timestamp,
            author_name=revision.author_name,
            comment=revision.comment,
            content_sha256=content_sha256,
        )

        persistence_content = KnowledgeContent(
            revision=persistence_revision,
            raw_wikitext=revision.raw_content,
            rendered_html=revision.rendered_html or "",
            plain_text=revision.raw_content,
            language_code="he",
        )

        return persistence_revision, persistence_content

    @classmethod
    def validate_document_revision_pair(
        cls,
        document: KnowledgeDocument,
        revision: KnowledgeDocumentRevision,
    ) -> None:
        document_id = cls.parse_positive_integer(
            document.id,
            field_name="document.id",
        )
        revision_document_id = cls.parse_positive_integer(
            revision.document_id,
            field_name="revision.document_id",
        )
        revision_id = cls.parse_positive_integer(
            revision.id,
            field_name="revision.id",
        )
        latest_revision_id = cls.require_latest_revision_id(document)

        if document_id != revision_document_id:
            raise ValueError(
                "revision.document_id does not match document.id"
            )

        if latest_revision_id != revision_id:
            raise ValueError(
                "revision.id does not match document.latest_revision_id"
            )

    @staticmethod
    def normalize_title(title: str) -> str:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("document.title cannot be empty")

        normalized = unicodedata.normalize("NFKC", title)
        return " ".join(normalized.split()).casefold()

    @staticmethod
    def calculate_sha256(content: str) -> str:
        if not isinstance(content, str):
            raise ValueError("revision.raw_content must be a string")

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def require_latest_revision_id(
        cls,
        document: KnowledgeDocument,
    ) -> int:
        if document.latest_revision_id is None:
            raise ValueError(
                "document.latest_revision_id is required for persistence"
            )

        return cls.parse_positive_integer(
            document.latest_revision_id,
            field_name="document.latest_revision_id",
        )

    @staticmethod
    def parse_positive_integer(
        value: str | int,
        *,
        field_name: str,
    ) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer")

        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{field_name} must be a positive integer"
            ) from error

        if parsed < 1 or str(value).strip() != str(parsed):
            raise ValueError(f"{field_name} must be a positive integer")

        return parsed

    @classmethod
    def parse_optional_positive_integer(
        cls,
        value: str | int | None,
        *,
        field_name: str,
    ) -> int | None:
        if value is None:
            return None

        return cls.parse_positive_integer(
            value,
            field_name=field_name,
        )
