from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.services.knowledge import (
    KnowledgeAuthenticationError,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.mediawiki.auth import MediaWikiAuthenticator
from app.services.transport import HttpTransport


@runtime_checkable
class MediaWikiPageReader(Protocol):
    """Page operations required by MediaWikiKnowledgeSource."""

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> Sequence[KnowledgeDocument]:
        ...

    async def get_page(
        self,
        identifier: str,
    ) -> KnowledgeDocument:
        ...


@runtime_checkable
class MediaWikiRevisionReader(Protocol):
    """Revision operations required by MediaWikiKnowledgeSource."""

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        ...


@runtime_checkable
class MediaWikiCategoryReader(Protocol):
    """Category operations required by MediaWikiKnowledgeSource."""

    async def get_categories(
        self,
        page_identifier: str,
    ) -> Sequence[KnowledgeCategory]:
        ...


class MediaWikiKnowledgeSource:
    """Source-neutral facade over the MediaWiki adapter.

    Higher-level services, including the future Sync Engine, should depend on
    the KnowledgeSource protocol and use this class instead of coordinating
    MediaWiki repositories directly.
    """

    def __init__(
        self,
        *,
        authenticator: MediaWikiAuthenticator,
        transport: HttpTransport,
        pages: MediaWikiPageReader,
        revisions: MediaWikiRevisionReader,
        categories: MediaWikiCategoryReader,
        source_name: str = "mediawiki",
    ) -> None:
        normalized_source_name = source_name.strip()

        if not normalized_source_name:
            raise ValueError("source_name cannot be empty")

        self._authenticator = authenticator
        self._transport = transport
        self._pages = pages
        self._revisions = revisions
        self._categories = categories
        self._source_name = normalized_source_name
        self._closed = False

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def is_connected(self) -> bool:
        return (
            not self._closed
            and self._authenticator.is_authenticated
        )

    async def connect(self) -> None:
        """Authenticate the MediaWiki session.

        Repeated calls are safe while the source remains connected.
        """

        if self._closed:
            raise RuntimeError(
                "MediaWiki knowledge source has already been closed"
            )

        if self._authenticator.is_authenticated:
            return

        await self._authenticator.login()

    async def close(self) -> None:
        """Log out and release the owned HTTP transport.

        The method is idempotent. The transport is closed even when logout
        fails, while the original logout exception is preserved.
        """

        if self._closed:
            return

        try:
            if self._authenticator.is_authenticated:
                await self._authenticator.logout()
        finally:
            await self._transport.close()
            self._closed = True

    async def health(self) -> bool:
        """Return whether the authenticated MediaWiki session is usable."""

        if not self.is_connected:
            return False

        try:
            await self._authenticator.validate_session()
        except KnowledgeAuthenticationError:
            return False

        return True

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> Sequence[KnowledgeDocument]:
        self._ensure_connected()

        return await self._pages.list_pages(
            namespace_id=namespace_id,
            limit=limit,
        )

    async def get_page(
        self,
        identifier: str,
    ) -> KnowledgeDocument:
        self._ensure_connected()

        return await self._pages.get_page(identifier)

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        self._ensure_connected()

        return await self._revisions.get_revision(revision_id)

    async def get_categories(
        self,
        page_identifier: str,
    ) -> Sequence[KnowledgeCategory]:
        self._ensure_connected()

        return await self._categories.get_categories(
            page_identifier
        )

    def _ensure_connected(self) -> None:
        if self._closed:
            raise RuntimeError(
                "MediaWiki knowledge source has already been closed"
            )

        if not self._authenticator.is_authenticated:
            raise KnowledgeAuthenticationError(
                "MediaWiki knowledge source is not connected"
            )
