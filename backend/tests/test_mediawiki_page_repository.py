from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
import pytest

from app.services.knowledge import KnowledgeNotFoundError
from app.services.mediawiki import (
    MediaWikiAPI,
    MediaWikiPageRepository,
    MediaWikiProtocolError,
)
from app.services.transport import HttpTransport, RetryPolicy

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def build_repository(
    handler: Handler,
) -> tuple[MediaWikiPageRepository, HttpTransport]:
    transport = HttpTransport(
        base_url="https://wiki.example.test/api.php",
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    repository = MediaWikiPageRepository(
        api=MediaWikiAPI(transport=transport),
    )

    return repository, transport


@pytest.mark.asyncio
async def test_list_pages_maps_all_pages_across_continuation() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        assert request.url.params["generator"] == "allpages"
        assert request.url.params["gapnamespace"] == "0"
        assert request.url.params["gaplimit"] == "max"
        assert request.url.params["prop"] == "info"
        assert request.url.params["inprop"] == "url"

        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "continue": {
                        "gapcontinue": "Second Page",
                        "continue": "gapcontinue||",
                    },
                    "query": {
                        "pages": [
                            {
                                "pageid": 1,
                                "ns": 0,
                                "title": "First Page",
                                "lastrevid": 101,
                                "canonicalurl": (
                                    "https://wiki.example.test/"
                                    "wiki/First_Page"
                                ),
                            }
                        ]
                    },
                },
            )

        assert (
            request.url.params["gapcontinue"]
            == "Second Page"
        )

        return httpx.Response(
            200,
            json={
                "batchcomplete": True,
                "query": {
                    "pages": [
                        {
                            "pageid": 2,
                            "ns": 0,
                            "title": "Second Page",
                            "lastrevid": 102,
                            "canonicalurl": (
                                "https://wiki.example.test/"
                                "wiki/Second_Page"
                            ),
                        }
                    ]
                },
            },
        )

    repository, transport = build_repository(handler)

    try:
        documents = await repository.list_pages()
    finally:
        await transport.close()

    assert len(documents) == 2
    assert documents[0].id == "1"
    assert documents[0].latest_revision_id == "101"
    assert documents[1].title == "Second Page"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_list_pages_honors_limit_without_extra_request() -> None:
    request_count = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            200,
            json={
                "continue": {
                    "gapcontinue": "Third Page",
                    "continue": "gapcontinue||",
                },
                "query": {
                    "pages": [
                        {
                            "pageid": 1,
                            "ns": 0,
                            "title": "First Page",
                            "canonicalurl": (
                                "https://wiki.example.test/"
                                "wiki/First_Page"
                            ),
                        },
                        {
                            "pageid": 2,
                            "ns": 0,
                            "title": "Second Page",
                            "canonicalurl": (
                                "https://wiki.example.test/"
                                "wiki/Second_Page"
                            ),
                        },
                    ]
                },
            },
        )

    repository, transport = build_repository(handler)

    try:
        documents = await repository.list_pages(limit=1)
    finally:
        await transport.close()

    assert len(documents) == 1
    assert documents[0].title == "First Page"
    assert request_count == 1


@pytest.mark.asyncio
async def test_get_page_by_numeric_identifier_uses_pageids() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["pageids"] == "42"
        assert "titles" not in request.url.params
        assert request.url.params["redirects"] == "1"

        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 42,
                            "ns": 0,
                            "title": "Test Page",
                            "lastrevid": 900,
                            "canonicalurl": (
                                "https://wiki.example.test/"
                                "wiki/Test_Page"
                            ),
                        }
                    ]
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        document = await repository.get_page("42")
    finally:
        await transport.close()

    assert document.id == "42"
    assert document.latest_revision_id == "900"


@pytest.mark.asyncio
async def test_get_page_by_title_uses_titles() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["titles"] == "Main Page"
        assert "pageids" not in request.url.params

        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 1,
                            "ns": 0,
                            "title": "Main Page",
                            "canonicalurl": (
                                "https://wiki.example.test/"
                                "wiki/Main_Page"
                            ),
                        }
                    ]
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        document = await repository.get_page_by_title(
            "Main Page"
        )
    finally:
        await transport.close()

    assert document.title == "Main Page"


@pytest.mark.asyncio
async def test_missing_page_raises_domain_not_found_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "ns": 0,
                            "title": "Missing Page",
                            "missing": True,
                        }
                    ]
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(KnowledgeNotFoundError) as captured:
            await repository.get_page_by_title(
                "Missing Page"
            )
    finally:
        await transport.close()

    assert captured.value.resource == "document"
    assert captured.value.identifier == "Missing Page"


@pytest.mark.asyncio
async def test_repository_rejects_invalid_pages_shape() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "1": {
                            "pageid": 1,
                        }
                    }
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(MediaWikiProtocolError) as captured:
            await repository.list_pages()
    finally:
        await transport.close()

    assert "invalid pages value" in str(captured.value)


@pytest.mark.asyncio
async def test_repository_rejects_empty_identifier() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Transport should not be called")

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(ValueError):
            await repository.get_page("   ")
    finally:
        await transport.close()


@pytest.mark.parametrize(
    ("namespace_id", "limit"),
    [
        (-1, None),
        (0, 0),
        (0, -1),
    ],
)
@pytest.mark.asyncio
async def test_list_pages_rejects_invalid_arguments(
    namespace_id: int,
    limit: int | None,
) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("Transport should not be called")

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(ValueError):
            await repository.list_pages(
                namespace_id=namespace_id,
                limit=limit,
            )
    finally:
        await transport.close()
