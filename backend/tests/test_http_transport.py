from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest

from app.services.transport import (
    HttpTransport,
    RetryPolicy,
    TransportClosedError,
    TransportConnectionError,
    TransportHTTPError,
    TransportTimeoutError,
    parse_retry_after,
)


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


@pytest.mark.asyncio
async def test_get_returns_transport_neutral_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["action"] == "query"

        return httpx.Response(
            200,
            json={"query": {"pages": []}},
            headers={"X-Test": "yes"},
        )

    transport = HttpTransport(
        base_url="https://wiki.example.test/",
        http_transport=httpx.MockTransport(handler),
    )

    try:
        response = await transport.get(
            "api.php",
            params={"action": "query"},
        )
    finally:
        await transport.close()

    assert response.status_code == 200
    assert response.json() == {"query": {"pages": []}}
    assert response.headers["x-test"] == "yes"
    assert response.url == "https://wiki.example.test/api.php?action=query"


@pytest.mark.asyncio
async def test_retryable_get_retries_server_error() -> None:
    attempts = 0
    sleep = SleepRecorder()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts < 3:
            return httpx.Response(503, text="temporarily unavailable")

        return httpx.Response(200, json={"ok": True})

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.1,
            max_delay_seconds=1.0,
        ),
        sleep=sleep,
    )

    try:
        response = await transport.get("https://example.test/health")
    finally:
        await transport.close()

    assert response.json() == {"ok": True}
    assert attempts == 3
    assert sleep.delays == [0.1, 0.2]


@pytest.mark.asyncio
async def test_retry_after_header_is_respected() -> None:
    attempts = 0
    sleep = SleepRecorder()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(
                429,
                text="rate limited",
                headers={"Retry-After": "2"},
            )

        return httpx.Response(200, json={"ok": True})

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(
            max_attempts=2,
            base_delay_seconds=0.1,
            max_delay_seconds=5.0,
        ),
        sleep=sleep,
    )

    try:
        response = await transport.get("https://example.test/data")
    finally:
        await transport.close()

    assert response.status_code == 200
    assert attempts == 2
    assert sleep.delays == [2.0]


@pytest.mark.asyncio
async def test_post_is_not_retried_by_default() -> None:
    attempts = 0
    sleep = SleepRecorder()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, text="unavailable")

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=3),
        sleep=sleep,
    )

    try:
        with pytest.raises(TransportHTTPError) as captured:
            await transport.post(
                "https://example.test/login",
                data={"username": "bot"},
            )
    finally:
        await transport.close()

    assert attempts == 1
    assert sleep.delays == []
    assert captured.value.status_code == 503
    assert captured.value.body_preview == "unavailable"


@pytest.mark.asyncio
async def test_post_can_be_explicitly_retried() -> None:
    attempts = 0
    sleep = SleepRecorder()

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return httpx.Response(503)

        return httpx.Response(200, json={"authenticated": True})

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(
            max_attempts=2,
            base_delay_seconds=0.25,
            max_delay_seconds=1.0,
        ),
        sleep=sleep,
    )

    try:
        response = await transport.post(
            "https://example.test/login",
            retry=True,
        )
    finally:
        await transport.close()

    assert response.json() == {"authenticated": True}
    assert attempts == 2
    assert sleep.delays == [0.25]


@pytest.mark.asyncio
async def test_timeout_is_mapped_to_transport_exception() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "request timed out",
            request=request,
        )

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    try:
        with pytest.raises(TransportTimeoutError) as captured:
            await transport.get("https://example.test/slow")
    finally:
        await transport.close()

    assert captured.value.method == "GET"
    assert captured.value.url == "https://example.test/slow"


@pytest.mark.asyncio
async def test_connection_error_is_mapped_to_transport_exception() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    try:
        with pytest.raises(TransportConnectionError) as captured:
            await transport.get("https://example.test/unreachable")
    finally:
        await transport.close()

    assert captured.value.method == "GET"
    assert captured.value.url == "https://example.test/unreachable"


@pytest.mark.asyncio
async def test_context_manager_closes_transport() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    transport = HttpTransport(
        http_transport=httpx.MockTransport(handler)
    )

    async with transport:
        response = await transport.get("https://example.test/")
        assert response.status_code == 200

    assert transport.is_closed is True

    with pytest.raises(TransportClosedError):
        await transport.get("https://example.test/")


def test_parse_retry_after_supports_seconds() -> None:
    assert parse_retry_after("3.5") == 3.5
    assert parse_retry_after("-2") == 0.0
    assert parse_retry_after("invalid") is None


def test_parse_retry_after_supports_http_date() -> None:
    now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
    retry_at = datetime(2026, 7, 23, 12, 0, 5, tzinfo=UTC)

    assert parse_retry_after(
        format_datetime(retry_at, usegmt=True),
        now=now,
    ) == 5.0


def test_retry_policy_validates_configuration() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)

    with pytest.raises(ValueError):
        RetryPolicy(
            base_delay_seconds=2.0,
            max_delay_seconds=1.0,
        )
