from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


DEFAULT_RETRYABLE_METHODS = frozenset(
    {
        "DELETE",
        "GET",
        "HEAD",
        "OPTIONS",
        "PUT",
        "TRACE",
    }
)

DEFAULT_RETRYABLE_STATUS_CODES = frozenset(
    {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy for safe and explicitly retryable HTTP requests."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    retryable_methods: frozenset[str] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_METHODS
    )
    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: DEFAULT_RETRYABLE_STATUS_CODES
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds cannot be negative")

        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds cannot be negative")

        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError(
                "max_delay_seconds cannot be lower than base_delay_seconds"
            )

    def supports_method(self, method: str) -> bool:
        return method.upper() in self.retryable_methods

    def supports_status(self, status_code: int) -> bool:
        return status_code in self.retryable_status_codes

    def delay_seconds(
        self,
        *,
        failed_attempt: int,
        retry_after_seconds: float | None = None,
    ) -> float:
        if retry_after_seconds is not None:
            return min(max(retry_after_seconds, 0.0), self.max_delay_seconds)

        exponential_delay = self.base_delay_seconds * (
            2 ** max(failed_attempt - 1, 0)
        )
        return min(exponential_delay, self.max_delay_seconds)


def parse_retry_after(
    value: str | None,
    *,
    now: datetime | None = None,
) -> float | None:
    """Parse Retry-After as seconds or an HTTP date."""

    if value is None:
        return None

    stripped_value = value.strip()
    if not stripped_value:
        return None

    try:
        return max(float(stripped_value), 0.0)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(stripped_value)
    except (TypeError, ValueError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)

    current_time = now or datetime.now(UTC)
    return max((retry_at - current_time).total_seconds(), 0.0)
