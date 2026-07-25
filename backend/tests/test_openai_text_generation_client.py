from __future__ import annotations

import json

import httpx
import pytest

from app.services.copilot import (
    OpenAIConfigurationError,
    OpenAIResponseError,
    OpenAITextGenerationClient,
)


@pytest.mark.asyncio
async def test_generate_calls_responses_api() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/responses"
        assert (
            request.headers["Authorization"]
            == "Bearer test-key"
        )

        payload = json.loads(request.content)

        assert payload["model"] == "gpt-test"
        assert payload["instructions"] == (
            "System instructions"
        )
        assert payload["input"] == "User prompt"
        assert payload["reasoning"] == {
            "effort": "low"
        }

        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": (
                                    "output_text"
                                ),
                                "text": (
                                    "תשובה "
                                    "[SOURCE 1]"
                                ),
                            }
                        ],
                    }
                ]
            },
        )

    client = OpenAITextGenerationClient(
        api_key="test-key",
        model="gpt-test",
        transport=httpx.MockTransport(handler),
    )

    answer = await client.generate(
        system_prompt="System instructions",
        user_prompt="User prompt",
    )

    assert answer == "תשובה [SOURCE 1]"


@pytest.mark.asyncio
async def test_generate_combines_output_text_parts() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "חלק ראשון",
                            },
                            {
                                "type": "output_text",
                                "text": (
                                    "חלק שני "
                                    "[SOURCE 1]"
                                ),
                            },
                        ],
                    }
                ]
            },
        )

    client = OpenAITextGenerationClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    answer = await client.generate(
        system_prompt="system",
        user_prompt="user",
    )

    assert answer == (
        "חלק ראשון\nחלק שני [SOURCE 1]"
    )


@pytest.mark.asyncio
async def test_generate_preserves_api_error() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": {
                    "message": "Invalid API key",
                }
            },
        )

    client = OpenAITextGenerationClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="HTTP 401: Invalid API key",
    ):
        await client.generate(
            system_prompt="system",
            user_prompt="user",
        )


@pytest.mark.asyncio
async def test_generate_rejects_missing_text() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"output": []},
        )

    client = OpenAITextGenerationClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="no generated text",
    ):
        await client.generate(
            system_prompt="system",
            user_prompt="user",
        )


@pytest.mark.parametrize(
    "api_key",
    [
        "",
        "   ",
    ],
)
def test_client_rejects_empty_api_key(
    api_key: str,
) -> None:
    with pytest.raises(
        OpenAIConfigurationError,
        match="API key",
    ):
        OpenAITextGenerationClient(
            api_key=api_key
        )
