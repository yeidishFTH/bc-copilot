from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from app.services.openai import (
    OpenAIClientBase,
    OpenAIConfigurationError,
    OpenAIResponseError,
)


class FakeOpenAIClient(OpenAIClientBase):
    async def post(
        self,
        body: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self._post_json(
            "/v1/test",
            body=body,
            timeout_message="test timed out",
            connection_message="test unavailable",
        )


@pytest.mark.asyncio
async def test_post_json_sends_authenticated_request() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/test"
        assert request.headers["Authorization"] == (
            "Bearer test-key"
        )
        assert request.headers["Content-Type"] == (
            "application/json"
        )
        assert json.loads(request.content) == {
            "value": 42
        }

        return httpx.Response(
            200,
            json={"ok": True},
        )

    client = FakeOpenAIClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    result = await client.post({"value": 42})

    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_post_json_preserves_openai_error_detail() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "Rate limit reached",
                }
            },
        )

    client = FakeOpenAIClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="HTTP 429: Rate limit reached",
    ):
        await client.post({"value": 1})


@pytest.mark.asyncio
async def test_post_json_rejects_invalid_json() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
        )

    client = FakeOpenAIClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="invalid JSON",
    ):
        await client.post({"value": 1})


@pytest.mark.asyncio
async def test_post_json_rejects_non_object_response() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=[1, 2, 3],
        )

    client = FakeOpenAIClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="non-object response",
    ):
        await client.post({"value": 1})


@pytest.mark.asyncio
async def test_post_json_normalizes_timeout() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "timeout",
            request=request,
        )

    client = FakeOpenAIClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="test timed out",
    ):
        await client.post({"value": 1})


@pytest.mark.asyncio
async def test_post_json_normalizes_connection_error() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "offline",
            request=request,
        )

    client = FakeOpenAIClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="test unavailable",
    ):
        await client.post({"value": 1})


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"api_key": ""}, "API key"),
        ({"api_key": "   "}, "API key"),
        (
            {
                "api_key": "test",
                "timeout_seconds": 0,
            },
            "timeout",
        ),
        (
            {
                "api_key": "test",
                "timeout_seconds": True,
            },
            "timeout",
        ),
        (
            {
                "api_key": "test",
                "base_url": "api.openai.com",
            },
            "absolute HTTP URL",
        ),
    ],
)
def test_client_rejects_invalid_configuration(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(
        OpenAIConfigurationError,
        match=message,
    ):
        FakeOpenAIClient(**kwargs)
