from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
import pytest

from app.services.knowledge import KnowledgeAuthenticationError
from app.services.mediawiki import (
    MediaWikiAPIError,
    MediaWikiAuthenticator,
    MediaWikiCredentials,
    MediaWikiProtocolError,
)
from app.services.transport import HttpTransport, RetryPolicy

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def build_authenticator(
    handler: Handler,
) -> tuple[MediaWikiAuthenticator, HttpTransport]:
    transport = HttpTransport(
        base_url="https://wiki.example.test/api.php",
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    authenticator = MediaWikiAuthenticator(
        transport=transport,
        credentials=MediaWikiCredentials(
            username="CopilotBot@sync",
            password="secret-bot-password",
        ),
    )

    return authenticator, transport


@pytest.mark.asyncio
async def test_login_uses_token_and_persistent_session() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        if len(requests) == 1:
            assert request.method == "GET"
            assert request.url.params["type"] == "login"

            return httpx.Response(
                200,
                json={
                    "query": {
                        "tokens": {
                            "logintoken": "LOGIN_TOKEN",
                        }
                    }
                },
                headers={
                    "Set-Cookie": "session=test-session; Path=/",
                },
            )

        if len(requests) == 2:
            assert request.method == "POST"
            body = request.content.decode()
            assert "action=login" in body
            assert "lgname=CopilotBot%40sync" in body
            assert "lgpassword=secret-bot-password" in body
            assert "lgtoken=LOGIN_TOKEN" in body
            assert request.headers["cookie"] == "session=test-session"

            return httpx.Response(
                200,
                json={
                    "login": {
                        "result": "Success",
                        "lguserid": 42,
                        "lgusername": "CopilotBot",
                    }
                },
            )

        assert request.method == "GET"
        assert request.url.params["meta"] == "userinfo"

        return httpx.Response(
            200,
            json={
                "query": {
                    "userinfo": {
                        "id": 42,
                        "name": "CopilotBot",
                        "groups": ["bot", "user"],
                        "rights": ["read", "edit"],
                    }
                }
            },
        )

    authenticator, transport = build_authenticator(handler)

    try:
        session = await authenticator.login()
    finally:
        await transport.close()

    assert session.user_id == 42
    assert session.username == "CopilotBot"
    assert session.groups == ("bot", "user")
    assert session.rights == ("read", "edit")
    assert authenticator.is_authenticated is True
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_login_failure_is_mapped_to_authentication_error() -> None:
    request_number = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_number
        request_number += 1

        if request_number == 1:
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

        return httpx.Response(
            200,
            json={
                "login": {
                    "result": "Failed",
                    "reason": "Incorrect username or password entered.",
                }
            },
        )

    authenticator, transport = build_authenticator(handler)

    try:
        with pytest.raises(KnowledgeAuthenticationError) as captured:
            await authenticator.login()
    finally:
        await transport.close()

    assert "Incorrect username or password" in str(captured.value)
    assert authenticator.is_authenticated is False


@pytest.mark.asyncio
async def test_anonymous_userinfo_invalidates_session() -> None:
    request_number = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_number
        request_number += 1

        if request_number == 1:
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

        if request_number == 2:
            return httpx.Response(
                200,
                json={"login": {"result": "Success"}},
            )

        return httpx.Response(
            200,
            json={
                "query": {
                    "userinfo": {
                        "id": 0,
                        "name": "127.0.0.1",
                        "anon": True,
                    }
                }
            },
        )

    authenticator, transport = build_authenticator(handler)

    try:
        with pytest.raises(KnowledgeAuthenticationError):
            await authenticator.login()
    finally:
        await transport.close()

    assert authenticator.is_authenticated is False
    assert authenticator.session is None


@pytest.mark.asyncio
async def test_csrf_token_is_cached() -> None:
    request_number = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_number
        request_number += 1

        if request_number == 1:
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

        if request_number == 2:
            return httpx.Response(
                200,
                json={"login": {"result": "Success"}},
            )

        if request_number == 3:
            return httpx.Response(
                200,
                json={
                    "query": {
                        "userinfo": {
                            "id": 42,
                            "name": "CopilotBot",
                        }
                    }
                },
            )

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

    authenticator, transport = build_authenticator(handler)

    try:
        await authenticator.login()
        first_token = await authenticator.get_csrf_token()
        second_token = await authenticator.get_csrf_token()
    finally:
        await transport.close()

    assert first_token == "CSRF_TOKEN"
    assert second_token == "CSRF_TOKEN"
    assert request_number == 4


@pytest.mark.asyncio
async def test_logout_uses_csrf_token_and_clears_state() -> None:
    request_number = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_number
        request_number += 1

        if request_number == 1:
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

        if request_number == 2:
            return httpx.Response(
                200,
                json={"login": {"result": "Success"}},
            )

        if request_number == 3:
            return httpx.Response(
                200,
                json={
                    "query": {
                        "userinfo": {
                            "id": 42,
                            "name": "CopilotBot",
                        }
                    }
                },
            )

        if request_number == 4:
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
        assert "action=logout" in body
        assert "token=CSRF_TOKEN" in body

        return httpx.Response(200, json={})

    authenticator, transport = build_authenticator(handler)

    try:
        await authenticator.login()
        await authenticator.logout()
    finally:
        await transport.close()

    assert authenticator.is_authenticated is False
    assert authenticator.session is None
    assert request_number == 5


@pytest.mark.asyncio
async def test_mediawiki_api_error_is_preserved() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "error": {
                    "code": "readapidenied",
                    "info": "You need read permission to use this module.",
                }
            },
        )

    authenticator, transport = build_authenticator(handler)

    try:
        with pytest.raises(MediaWikiAPIError) as captured:
            await authenticator.login()
    finally:
        await transport.close()

    assert captured.value.code == "readapidenied"
    assert "read permission" in captured.value.message


@pytest.mark.asyncio
async def test_malformed_token_response_raises_protocol_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"query": {"tokens": {}}},
        )

    authenticator, transport = build_authenticator(handler)

    try:
        with pytest.raises(MediaWikiProtocolError):
            await authenticator.login()
    finally:
        await transport.close()


def test_credentials_do_not_expose_password_in_repr() -> None:
    credentials = MediaWikiCredentials(
        username="CopilotBot@sync",
        password="super-secret",
    )

    assert "CopilotBot@sync" in repr(credentials)
    assert "super-secret" not in repr(credentials)
