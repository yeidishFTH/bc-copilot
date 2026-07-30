from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class IssuedSessionToken:
    raw_token: str
    token_hash: str
    expires_at: datetime


class SessionTokenService:
    """Issue opaque session tokens and hash them for storage."""

    def __init__(
        self,
        *,
        session_hours: int = 12,
        token_bytes: int = 32,
    ) -> None:
        if session_hours <= 0:
            raise ValueError(
                "Session duration must be positive"
            )

        if token_bytes < 32:
            raise ValueError(
                "Session token must contain at least 32 bytes"
            )

        self._session_hours = session_hours
        self._token_bytes = token_bytes

    def issue(
        self,
        *,
        now: datetime | None = None,
    ) -> IssuedSessionToken:
        issued_at = self._normalize_datetime(
            now or datetime.now(UTC)
        )

        raw_token = secrets.token_urlsafe(
            self._token_bytes
        )

        return IssuedSessionToken(
            raw_token=raw_token,
            token_hash=self.hash_token(raw_token),
            expires_at=(
                issued_at
                + timedelta(
                    hours=self._session_hours
                )
            ),
        )

    @staticmethod
    def hash_token(raw_token: str) -> str:
        if not isinstance(raw_token, str):
            raise TypeError(
                "Session token must be a string"
            )

        normalized = raw_token.strip()

        if not normalized:
            raise ValueError(
                "Session token cannot be empty"
            )

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)
