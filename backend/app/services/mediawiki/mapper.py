from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.knowledge import KnowledgeDocument
from app.services.mediawiki.exceptions import MediaWikiProtocolError


class MediaWikiMapper:
    """Map validated MediaWiki payload objects into domain models."""

    @staticmethod
    def page_to_document(
        page: Mapping[str, Any],
    ) -> KnowledgeDocument:
        """Convert one MediaWiki page object into a KnowledgeDocument."""

        page_id = page.get("pageid")
        namespace_id = page.get("ns")
        title = page.get("title")

        if not isinstance(page_id, int):
            raise MediaWikiProtocolError(
                "MediaWiki page object contains an invalid pageid"
            )

        if not isinstance(namespace_id, int):
            raise MediaWikiProtocolError(
                "MediaWiki page object contains an invalid namespace"
            )

        if not isinstance(title, str) or not title:
            raise MediaWikiProtocolError(
                "MediaWiki page object contains an invalid title"
            )

        canonical_url = MediaWikiMapper._extract_canonical_url(page)

        latest_revision = page.get("lastrevid")
        latest_revision_id: str | None

        if latest_revision is None:
            latest_revision_id = None
        elif isinstance(latest_revision, int):
            latest_revision_id = str(latest_revision)
        else:
            raise MediaWikiProtocolError(
                "MediaWiki page object contains an invalid lastrevid"
            )

        return KnowledgeDocument(
            id=str(page_id),
            title=title,
            canonical_url=canonical_url,
            namespace_id=namespace_id,
            latest_revision_id=latest_revision_id,
            is_redirect=MediaWikiMapper._is_truthy_flag(
                page,
                "redirect",
            ),
        )

    @staticmethod
    def _extract_canonical_url(
        page: Mapping[str, Any],
    ) -> str:
        canonical_url = page.get("canonicalurl")

        if isinstance(canonical_url, str) and canonical_url:
            return canonical_url

        full_url = page.get("fullurl")

        if isinstance(full_url, str) and full_url:
            return full_url

        raise MediaWikiProtocolError(
            "MediaWiki page object contains no canonical URL"
        )

    @staticmethod
    def _is_truthy_flag(
        payload: Mapping[str, Any],
        key: str,
    ) -> bool:
        """Interpret MediaWiki boolean-presence fields safely."""

        if key not in payload:
            return False

        value = payload[key]

        return value is True or value == "" or value == 1
