from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
import pytest

from app.services.mediawiki import (
    MediaWikiAPI,
    MediaWikiAPIError,
    MediaWikiProtocolError,
)
from app.services.transport import HttpTransport, RetryPolicy

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def build_api(
    handler: Handler,
    *,
    max_continuation_requests: int = 10_000,
) -> tuple[MediaWikiAPI, HttpTransport]:
    transport = HttpTransport(
        base_url="https://wiki.example.test/api.php",
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    api = MediaWikiAPI(
        transport=transport,
        max_continuation_requests=max_continuation_requests,
    )

    return api, transport


@pytest.mark.asyncio
async def test_query_adds_required_action_api_parameters() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.params["action"] == "query"
        assert request.url.params["format"] == "json"
        assert request.url.params["formatversion"] == "2"
        assert request.url.params["list"] == "allpages"
        assert request.url.params["apnamespace"] == "0"

        return httpx.Response(
            200,
            json={
                "batchcomplete": True,
                "query": {
                    "allpages": [],
                },
            },
        )

    api, transport = build_api(handler)

    try:
        payload = await api.query(
            {
                "list": "allpages",
                "apnamespace": 0,
            }
        )
    finally:
        await transport.close()

    assert payload["query"]["allpages"] == []


@pytest.mark.asyncio
async def test_query_rejects_reserved_parameters() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Transport should not be called")

    api, transport = build_api(handler)

    try:
        with pytest.raises(ValueError) as captured:
            await api.query(
                {
                    "action": "edit",
                    "list": "allpages",
                }
            )
    finally:
        await transport.close()

    assert "reserved fields" in str(captured.value)
    assert "action" in str(captured.value)


@pytest.mark.asyncio
async def test_query_preserves_mediawiki_api_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "badvalue",
                    "info": "Unrecognized value for parameter.",
                }
            },
        )

    api, transport = build_api(handler)

    try:
        with pytest.raises(MediaWikiAPIError) as captured:
            await api.query({"list": "allpages"})
    finally:
        await transport.close()

    assert captured.value.code == "badvalue"
    assert "Unrecognized value" in captured.value.message


@pytest.mark.asyncio
async def test_query_rejects_invalid_json() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html>Not JSON</html>",
        )

    api, transport = build_api(handler)

    try:
        with pytest.raises(MediaWikiProtocolError) as captured:
            await api.query({"list": "allpages"})
    finally:
        await transport.close()

    assert "invalid JSON" in str(captured.value)


@pytest.mark.asyncio
async def test_query_rejects_non_object_json() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=["invalid", "payload"],
        )

    api, transport = build_api(handler)

    try:
        with pytest.raises(MediaWikiProtocolError) as captured:
            await api.query({"list": "allpages"})
    finally:
        await transport.close()

    assert "non-object JSON" in str(captured.value)


@pytest.mark.asyncio
async def test_iter_query_follows_mediawiki_continuation() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        if len(requests) == 1:
            assert "apcontinue" not in request.url.params

            return httpx.Response(
                200,
                json={
                    "continue": {
                        "apcontinue": "Second_Page",
                        "continue": "-||",
                    },
                    "query": {
                        "allpages": [
                            {
                                "pageid": 1,
                                "ns": 0,
                                "title": "First Page",
                            }
                        ]
                    },
                },
            )

        assert request.url.params["apcontinue"] == "Second_Page"
        assert request.url.params["continue"] == "-||"

        return httpx.Response(
            200,
            json={
                "batchcomplete": True,
                "query": {
                    "allpages": [
                        {
                            "pageid": 2,
                            "ns": 0,
                            "title": "Second Page",
                        }
                    ]
                },
            },
        )

    api, transport = build_api(handler)

    try:
        payloads = [
            payload
            async for payload in api.iter_query(
                {
                    "list": "allpages",
                    "apnamespace": 0,
                }
            )
        ]
    finally:
        await transport.close()

    assert len(payloads) == 2
    assert (
        payloads[0]["query"]["allpages"][0]["title"]
        == "First Page"
    )
    assert (
        payloads[1]["query"]["allpages"][0]["title"]
        == "Second Page"
    )
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_iter_query_rejects_invalid_continuation_shape() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "continue": "invalid",
                "query": {
                    "allpages": [],
                },
            },
        )

    api, transport = build_api(handler)

    try:
        with pytest.raises(MediaWikiProtocolError) as captured:
            async for _ in api.iter_query({"list": "allpages"}):
                pass
    finally:
        await transport.close()

    assert "continuation value must be an object" in str(
        captured.value
    )


@pytest.mark.asyncio
async def test_iter_query_enforces_request_limit() -> None:
    request_count = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            200,
            json={
                "continue": {
                    "apcontinue": f"Page_{request_count}",
                    "continue": "-||",
                },
                "query": {
                    "allpages": [],
                },
            },
        )

    api, transport = build_api(
        handler,
        max_continuation_requests=2,
    )

    try:
        with pytest.raises(MediaWikiProtocolError) as captured:
            async for _ in api.iter_query({"list": "allpages"}):
                pass
    finally:
        await transport.close()

    assert request_count == 2
    assert "exceeded the configured request limit" in str(
        captured.value
    )


def test_api_rejects_invalid_continuation_limit() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = HttpTransport(
        base_url="https://wiki.example.test/api.php",
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(ValueError):
        MediaWikiAPI(
            transport=transport,
            max_continuation_requests=0,
        )
