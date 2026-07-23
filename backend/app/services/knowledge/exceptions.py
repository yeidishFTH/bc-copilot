from __future__ import annotations


class KnowledgeSourceError(Exception):
    """Base exception for all knowledge-source failures."""


class KnowledgeConnectionError(KnowledgeSourceError):
    """Raised when a connection to the knowledge source cannot be established."""


class KnowledgeAuthenticationError(KnowledgeSourceError):
    """Raised when the knowledge source rejects authentication."""


class KnowledgeNotFoundError(KnowledgeSourceError):
    """Raised when a requested page or revision does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class KnowledgeRateLimitError(KnowledgeSourceError):
    """Raised when the knowledge source rate-limits a request."""

    def __init__(
        self,
        message: str = "Knowledge source rate limit exceeded",
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)
