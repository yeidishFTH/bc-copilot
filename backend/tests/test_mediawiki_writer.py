from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
import pytest

from app.services.mediawiki import (
    MediaWikiAuthenticator,
    MediaWikiCredentials,
)
from app.services.mediawiki.writer import (
    MediaWikiWriter,
)
from app.services.transport import (
    HttpTransport,
    RetryPolicy,
)

Handler = Callable[
    [httpx.Request],
    Awaitable[httpx.Response],
]


def build_writer(
    handler: Handler,
):
    transport = HttpTransport(
        base_url="https://wiki.example.test/api.php",
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(
            max_attempts=1
        ),
    )

    authenticator = MediaWikiAuthenticator(
        transport=transport,
        credentials=MediaWikiCredentials(
            username="CopilotBot@sync",
            password="secret",
        ),
    )

    writer = MediaWikiWriter(
        transport=transport,
        authenticator=authenticator,
    )

    return writer, authenticator, transport


@pytest.mark.asyncio
async def test_edit_page_success() -> None:
    requests: list[httpx.Request] = []

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        requests.append(request)

        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "query": {
                        "tokens": {
                            "logintoken": "LOGIN_TOKEN",
                        }
                    }
                },
            )

        if len(requests) == 2:
            return httpx.Response(
                200,
                json={
                    "login": {
                        "result": "Success",
                    }
                },
            )

        if len(requests) == 3:
            return httpx.Response(
                200,
                json={
                    "query": {
                        "userinfo": {
                            "id": 42,
                            "name": "CopilotBot",
                            "groups": [
                                "bot"
                            ],
                            "rights": [
                                "edit"
                            ],
                        }
                    }
                },
            )

        if len(requests) == 4:
            assert request.url.params["type"] == "csrf"

            return httpx.Response(
                200,
                json={
                    "query": {
                        "tokens": {
                            "csrftoken": "CSRF_TOKEN",
                        }
                    }
                },
            )

        assert request.method == "POST"

        body = request.content.decode()

        assert "action=edit" in body
        assert "title=Test+Page" in body
        assert "text=Hello" in body
        assert "token=CSRF_TOKEN" in body

        return httpx.Response(
            200,
            json={
                "edit": {
                    "result": "Success",
                    "title": "Test Page",
                    "newrevid": 123,
                }
            },
        )

    writer, authenticator, transport = build_writer(
        handler
    )

    try:
        await authenticator.login()

        result = await writer.edit_page(
            title="Test Page",
            content="Hello",
            summary="Update",
        )

    finally:
        await transport.close()

    assert result["result"] == "Success"
    assert result["newrevid"] == 123
    assert len(requests) == 5


@pytest.mark.asyncio
async def test_edit_page_preserves_api_error() -> None:

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "permissiondenied",
                    "info": "Not allowed",
                }
            },
        )

    writer, authenticator, transport = build_writer(
        handler
    )

    try:
        authenticator._session = object()

        with pytest.raises(Exception):
            await writer.edit_page(
                title="Test",
                content="Body",
                summary="Summary",
            )

    finally:
        await transport.close()
