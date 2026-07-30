from datetime import UTC, datetime, timedelta

import pytest

from app.services.auth import SessionTokenService


def test_session_token_is_random_and_hashable() -> None:
    service = SessionTokenService(
        session_hours=12
    )

    first = service.issue()
    second = service.issue()

    assert first.raw_token != second.raw_token
    assert first.token_hash != second.token_hash

    assert len(first.token_hash) == 64
    assert (
        SessionTokenService.hash_token(
            first.raw_token
        )
        == first.token_hash
    )


def test_session_expiration_uses_configured_hours() -> None:
    now = datetime(
        2026,
        7,
        30,
        12,
        0,
        tzinfo=UTC,
    )

    token = SessionTokenService(
        session_hours=12
    ).issue(now=now)

    assert token.expires_at == (
        now + timedelta(hours=12)
    )


def test_session_token_hash_never_contains_raw_token() -> None:
    token = SessionTokenService().issue()

    assert token.raw_token not in token.token_hash


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
    ],
)
def test_empty_session_token_is_rejected(
    value: str,
) -> None:
    with pytest.raises(ValueError):
        SessionTokenService.hash_token(value)


def test_short_token_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        SessionTokenService(token_bytes=16)


def test_non_positive_duration_is_rejected() -> None:
    with pytest.raises(ValueError):
        SessionTokenService(session_hours=0)
