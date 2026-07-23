from __future__ import annotations


class TransportError(Exception):
    """Base exception for transport-layer failures."""


class TransportClosedError(TransportError):
    """Raised when attempting to use a closed transport."""


class TransportConnectionError(TransportError):
    """Raised when a remote service cannot be reached."""

    def __init__(
        self,
        message: str,
        *,
        method: str,
        url: str,
    ) -> None:
        self.method = method
        self.url = url
        super().__init__(message)


class TransportTimeoutError(TransportError):
    """Raised when a transport request exceeds its timeout."""

    def __init__(
        self,
        message: str,
        *,
        method: str,
        url: str,
    ) -> None:
        self.method = method
        self.url = url
        super().__init__(message)


class TransportHTTPError(TransportError):
    """Raised when a remote service returns an unsuccessful HTTP status."""

    def __init__(
        self,
        *,
        status_code: int,
        method: str,
        url: str,
        body_preview: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.status_code = status_code
        self.method = method
        self.url = url
        self.body_preview = body_preview
        self.retry_after_seconds = retry_after_seconds

        super().__init__(
            f"HTTP {status_code} returned for {method.upper()} {url}"
        )
