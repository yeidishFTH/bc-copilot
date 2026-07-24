from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.knowledge import (
    KnowledgeDocumentRevision,
    KnowledgeNotFoundError,
)
from app.services.mediawiki.api import MediaWikiAPI
from app.services.mediawiki.exceptions import MediaWikiProtocolError
from app.services.mediawiki.mappers import MediaWikiRevisionMapper


class MediaWikiRevisionRepository:
    """Read immutable MediaWiki revisions as domain models."""

    def __init__(
        self,
        *,
        api: MediaWikiAPI,
        mapper: MediaWikiRevisionMapper | None = None,
    ) -> None:
        self._api = api
        self._mapper = mapper or MediaWikiRevisionMapper()

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        """Get one immutable revision by its numeric revision ID."""

        normalized_revision_id = revision_id.strip()

        if (
            not normalized_revision_id.isdigit()
            or int(normalized_revision_id) < 1
        ):
            raise ValueError(
                "revision_id must be a positive integer"
            )

        payload = await self._api.query(
            {
                "revids": normalized_revision_id,
                "prop": "revisions",
                "rvprop": (
                    "ids|timestamp|user|comment|content"
                ),
                "rvslots": "main",
            }
        )

        pages = self._extract_pages(payload)

        for page in pages:
            document_id = self._extract_document_id(page)
            revisions = self._extract_revisions(page)

            for revision in revisions:
                revision_value = revision.get("revid")

                if (
                    isinstance(revision_value, int)
                    and not isinstance(revision_value, bool)
                    and str(revision_value)
                    == normalized_revision_id
                ):
                    return (
                        self._mapper
                        .revision_to_document_revision(
                            revision,
                            document_id=document_id,
                        )
                    )

        raise KnowledgeNotFoundError(
            "revision",
            normalized_revision_id,
        )

    @staticmethod
    def _extract_pages(
        payload: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        query = payload.get("query")

        if not isinstance(query, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki revision response contains no query object"
            )

        pages = query.get("pages")

        if pages is None:
            return []

        if not isinstance(pages, list):
            raise MediaWikiProtocolError(
                "MediaWiki revision response contains "
                "an invalid pages value"
            )

        validated_pages: list[Mapping[str, Any]] = []

        for page in pages:
            if not isinstance(page, Mapping):
                raise MediaWikiProtocolError(
                    "MediaWiki revision pages list contains "
                    "a non-object value"
                )

            validated_pages.append(page)

        return validated_pages

    @staticmethod
    def _extract_document_id(
        page: Mapping[str, Any],
    ) -> str:
        page_id = page.get("pageid")

        if (
            not isinstance(page_id, int)
            or isinstance(page_id, bool)
            or page_id < 1
        ):
            raise MediaWikiProtocolError(
                "MediaWiki revision page contains "
                "an invalid pageid"
            )

        return str(page_id)

    @staticmethod
    def _extract_revisions(
        page: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        revisions = page.get("revisions")

        if revisions is None:
            return []

        if not isinstance(revisions, list):
            raise MediaWikiProtocolError(
                "MediaWiki revision page contains "
                "an invalid revisions value"
            )

        validated_revisions: list[Mapping[str, Any]] = []

        for revision in revisions:
            if not isinstance(revision, Mapping):
                raise MediaWikiProtocolError(
                    "MediaWiki revisions list contains "
                    "a non-object value"
                )

            validated_revisions.append(revision)

        return validated_revisions
