from __future__ import annotations

from app.services.knowledge import KnowledgeSourceError


class MediaWikiError(KnowledgeSourceError):
    """Base exception for MediaWiki adapter failures."""


class MediaWikiProtocolError(MediaWikiError):
    """Raised when MediaWiki returns an invalid or unexpected response."""


class MediaWikiAPIError(MediaWikiError):
    """Raised when MediaWiki returns an Action API error."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
    ) -> None:
        self.code = code
        self.message = message
        super().__init__(f"MediaWiki API error {code}: {message}")
