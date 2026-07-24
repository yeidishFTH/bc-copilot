from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.services.knowledge import KnowledgeDocumentRevision
from app.services.mediawiki.exceptions import MediaWikiProtocolError


class MediaWikiRevisionMapper:
    """Map MediaWiki revision objects into domain revisions."""

    @classmethod
    def revision_to_document_revision(
        cls,
        revision: Mapping[str, Any],
        *,
        document_id: str | int,
    ) -> KnowledgeDocumentRevision:
        """Convert one MediaWiki revision object into a domain model."""

        normalized_document_id = str(document_id).strip()

        if not normalized_document_id:
            raise ValueError("document_id cannot be empty")

        revision_id = cls._extract_positive_integer(
            revision,
            "revid",
            error_message=(
                "MediaWiki revision object contains an invalid revid"
            ),
        )

        timestamp = cls._extract_timestamp(revision)
        raw_content = cls._extract_raw_content(revision)
        parent_id = cls._extract_optional_parent_id(revision)
        author_name = cls._extract_optional_string(
            revision,
            "user",
            error_message=(
                "MediaWiki revision object contains an invalid user"
            ),
        )
        comment = cls._extract_optional_string(
            revision,
            "comment",
            error_message=(
                "MediaWiki revision object contains an invalid comment"
            ),
        )

        return KnowledgeDocumentRevision(
            id=str(revision_id),
            document_id=normalized_document_id,
            timestamp=timestamp,
            raw_content=raw_content,
            parent_id=parent_id,
            author_name=author_name,
            comment=comment,
        )

    @staticmethod
    def _extract_positive_integer(
        payload: Mapping[str, Any],
        key: str,
        *,
        error_message: str,
    ) -> int:
        value = payload.get(key)

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
        ):
            raise MediaWikiProtocolError(error_message)

        return value

    @staticmethod
    def _extract_timestamp(
        revision: Mapping[str, Any],
    ) -> datetime:
        value = revision.get("timestamp")

        if not isinstance(value, str) or not value:
            raise MediaWikiProtocolError(
                "MediaWiki revision object contains an invalid timestamp"
            )

        normalized_value = (
            value[:-1] + "+00:00"
            if value.endswith("Z")
            else value
        )

        try:
            timestamp = datetime.fromisoformat(normalized_value)
        except ValueError as error:
            raise MediaWikiProtocolError(
                "MediaWiki revision object contains an invalid timestamp"
            ) from error

        if timestamp.tzinfo is None:
            raise MediaWikiProtocolError(
                "MediaWiki revision timestamp must include a timezone"
            )

        return timestamp

    @staticmethod
    def _extract_raw_content(
        revision: Mapping[str, Any],
    ) -> str:
        slots = revision.get("slots")

        if not isinstance(slots, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki revision object contains invalid slots"
            )

        main_slot = slots.get("main")

        if not isinstance(main_slot, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki revision object contains no main slot"
            )

        if "contenthidden" in main_slot:
            raise MediaWikiProtocolError(
                "MediaWiki revision content is hidden"
            )

        content = main_slot.get("content")

        if not isinstance(content, str):
            raise MediaWikiProtocolError(
                "MediaWiki revision main slot contains invalid content"
            )

        return content

    @staticmethod
    def _extract_optional_parent_id(
        revision: Mapping[str, Any],
    ) -> str | None:
        parent_id = revision.get("parentid")

        if parent_id is None or parent_id == 0:
            return None

        if (
            not isinstance(parent_id, int)
            or isinstance(parent_id, bool)
            or parent_id < 1
        ):
            raise MediaWikiProtocolError(
                "MediaWiki revision object contains an invalid parentid"
            )

        return str(parent_id)

    @staticmethod
    def _extract_optional_string(
        payload: Mapping[str, Any],
        key: str,
        *,
        error_message: str,
    ) -> str | None:
        value = payload.get(key)

        if value is None:
            return None

        if not isinstance(value, str):
            raise MediaWikiProtocolError(error_message)

        return value
