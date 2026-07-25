from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.db.models import SyncStatus
from app.services.sync import SyncExecutionResult
from app.cli.sync_knowledge import (
    build_parser,
    exit_code_for_result,
    require_mediawiki_credentials,
    result_payload,
    split_mediawiki_api_url,
)


def make_settings(
    *,
    username: str | None = "WikiBot",
    password: str | None = "secret",
) -> Settings:
    return Settings(
        mediawiki_bot_username=username,
        mediawiki_bot_password=(
            SecretStr(password)
            if password is not None
            else None
        ),
    )


def make_result(
    status: SyncStatus,
) -> SyncExecutionResult:
    return SyncExecutionResult(
        run_id=uuid4(),
        status=status,
        pages_seen=1,
        pages_created=1,
        pages_updated=0,
        pages_unchanged=0,
        pages_failed=0,
    )


def test_parser_accepts_limited_sync() -> None:
    arguments = build_parser().parse_args(
        [
            "--namespace-id",
            "0",
            "--limit",
            "1",
        ]
    )

    assert arguments.namespace_id == 0
    assert arguments.limit == 1


def test_credentials_are_loaded_from_settings() -> None:
    credentials = require_mediawiki_credentials(
        make_settings()
    )

    assert credentials.username == "WikiBot"
    assert credentials.password == "secret"


@pytest.mark.parametrize(
    ("username", "password", "message"),
    [
        (None, "secret", "MEDIAWIKI_BOT_USERNAME"),
        ("   ", "secret", "MEDIAWIKI_BOT_USERNAME"),
        ("WikiBot", None, "MEDIAWIKI_BOT_PASSWORD"),
        ("WikiBot", "", "MEDIAWIKI_BOT_PASSWORD"),
    ],
)
def test_missing_credentials_are_rejected(
    username: str | None,
    password: str | None,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        require_mediawiki_credentials(
            make_settings(
                username=username,
                password=password,
            )
        )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (SyncStatus.succeeded, 0),
        (SyncStatus.partial, 2),
        (SyncStatus.failed, 1),
    ],
)
def test_exit_code_matches_sync_status(
    status: SyncStatus,
    expected: int,
) -> None:
    assert exit_code_for_result(make_result(status)) == expected


def test_result_payload_is_json_ready() -> None:
    result = make_result(SyncStatus.succeeded)

    payload = result_payload(result)

    assert payload["run_id"] == str(result.run_id)
    assert payload["status"] == "succeeded"
    assert payload["pages_seen"] == 1
    assert payload["pages_created"] == 1
    assert payload["error_summary"] is None


def test_mediawiki_api_url_is_split_into_origin_and_path() -> None:
    base_url, api_path = split_mediawiki_api_url(
        "https://wiki.bitcoinchange.co.il/api.php"
    )

    assert base_url == "https://wiki.bitcoinchange.co.il"
    assert api_path == "/api.php"


@pytest.mark.parametrize(
    "api_url",
    [
        "",
        "wiki.bitcoinchange.co.il/api.php",
        "https://wiki.bitcoinchange.co.il",
        "https://wiki.bitcoinchange.co.il/",
        "https://wiki.bitcoinchange.co.il/api.php?format=json",
    ],
)
def test_invalid_mediawiki_api_urls_are_rejected(
    api_url: str,
) -> None:
    with pytest.raises(ValueError, match="MEDIAWIKI_API_URL"):
        split_mediawiki_api_url(api_url)
