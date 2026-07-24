from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.knowledge import (
    KnowledgeDocument,
    KnowledgeNotFoundError,
)
from app.services.mediawiki.api import MediaWikiAPI
from app.services.mediawiki.exceptions import MediaWikiProtocolError
from app.services.mediawiki.mappers import MediaWikiPageMapper


class MediaWikiPageRepository:
    """Read MediaWiki page metadata as source-neutral domain models."""

    def __init__(
        self,
        *,
        api: MediaWikiAPI,
        mapper: MediaWikiPageMapper | None = None,
    ) -> None:
        self._api = api
        self._mapper = mapper or MediaWikiPageMapper()

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> Sequence[KnowledgeDocument]:
        """List pages from one namespace.

        MediaWiki continuation is handled by MediaWikiAPI.iter_query().
        """

        if namespace_id < 0:
            raise ValueError("namespace_id cannot be negative")

        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")

        documents: list[KnowledgeDocument] = []

        async for payload in self._api.iter_query(
            {
                "generator": "allpages",
                "gapnamespace": namespace_id,
                "gaplimit": "max",
                "prop": "info",
                "inprop": "url",
            }
        ):
            pages = self._extract_pages(payload)

            for page in pages:
                if self._is_missing_page(page):
                    continue

                documents.append(
                    self._mapper.page_to_document(page)
                )

                if limit is not None and len(documents) >= limit:
                    return tuple(documents)

        return tuple(documents)

    async def get_page(
        self,
        identifier: str,
    ) -> KnowledgeDocument:
        """Get one page by numeric page ID or canonical title."""

        normalized_identifier = identifier.strip()

        if not normalized_identifier:
            raise ValueError("identifier cannot be empty")

        identifier_params = self._identifier_params(
            normalized_identifier
        )

        payload = await self._api.query(
            {
                **identifier_params,
                "prop": "info",
                "inprop": "url",
                "redirects": 1,
            }
        )

        pages = self._extract_pages(payload)

        if not pages:
            raise KnowledgeNotFoundError(
                "document",
                normalized_identifier,
            )

        page = pages[0]

        if self._is_missing_page(page):
            raise KnowledgeNotFoundError(
                "document",
                normalized_identifier,
            )

        return self._mapper.page_to_document(page)

    async def get_page_by_id(
        self,
        page_id: str | int,
    ) -> KnowledgeDocument:
        normalized_page_id = str(page_id).strip()

        if not normalized_page_id.isdigit():
            raise ValueError("page_id must be a positive integer")

        if int(normalized_page_id) < 1:
            raise ValueError("page_id must be a positive integer")

        return await self.get_page(normalized_page_id)

    async def get_page_by_title(
        self,
        title: str,
    ) -> KnowledgeDocument:
        normalized_title = title.strip()

        if not normalized_title:
            raise ValueError("title cannot be empty")

        payload = await self._api.query(
            {
                "titles": normalized_title,
                "prop": "info",
                "inprop": "url",
                "redirects": 1,
            }
        )

        pages = self._extract_pages(payload)

        if not pages or self._is_missing_page(pages[0]):
            raise KnowledgeNotFoundError(
                "document",
                normalized_title,
            )

        return self._mapper.page_to_document(pages[0])

    @staticmethod
    def _identifier_params(
        identifier: str,
    ) -> dict[str, str]:
        if identifier.isdigit() and int(identifier) > 0:
            return {"pageids": identifier}

        return {"titles": identifier}

    @staticmethod
    def _extract_pages(
        payload: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        query = payload.get("query")

        if not isinstance(query, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki page response contains no query object"
            )

        pages = query.get("pages")

        if pages is None:
            return []

        if not isinstance(pages, list):
            raise MediaWikiProtocolError(
                "MediaWiki page response contains an invalid pages value"
            )

        validated_pages: list[Mapping[str, Any]] = []

        for page in pages:
            if not isinstance(page, Mapping):
                raise MediaWikiProtocolError(
                    "MediaWiki pages list contains a non-object value"
                )

            validated_pages.append(page)

        return validated_pages

    @staticmethod
    def _is_missing_page(
        page: Mapping[str, Any],
    ) -> bool:
        if "missing" not in page:
            return False

        missing = page["missing"]

        return missing is True or missing == "" or missing == 1
