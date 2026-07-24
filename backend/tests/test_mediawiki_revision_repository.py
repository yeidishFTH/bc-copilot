from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import httpx
import pytest

from app.services.knowledge import KnowledgeNotFoundError
from app.services.mediawiki import (
    MediaWikiAPI,
    MediaWikiProtocolError,
    MediaWikiRevisionRepository,
)
from app.services.transport import HttpTransport, RetryPolicy

Handler = Callable[[httpx.Request], Awaitable[httpx.Response]]


def build_repository(
    handler: Handler,
) -> tuple[MediaWikiRevisionRepository, HttpTransport]:
    transport = HttpTransport(
        base_url="https://wiki.example.test/api.php",
        http_transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=1),
    )

    repository = MediaWikiRevisionRepository(
        api=MediaWikiAPI(transport=transport),
    )

    return repository, transport


def revision_payload() -> dict[str, object]:
    return {
        "query": {
            "pages": [
                {
                    "pageid": 42,
                    "ns": 0,
                    "title": "Test Page",
                    "revisions": [
                        {
                            "revid": 900,
                            "parentid": 899,
                            "timestamp": (
                                "2026-07-24T08:30:45Z"
                            ),
                            "user": "Wiki Editor",
                            "comment": "Updated procedure",
                            "slots": {
                                "main": {
                                    "contentmodel": "wikitext",
                                    "contentformat": (
                                        "text/x-wiki"
                                    ),
                                    "content": (
                                        "== Procedure ==\n"
                                        "Revision content"
                                    ),
                                }
                            },
                        }
                    ],
                }
            ]
        }
    }


@pytest.mark.asyncio
async def test_get_revision_requests_and_maps_content() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.params["revids"] == "900"
        assert request.url.params["prop"] == "revisions"
        assert request.url.params["rvslots"] == "main"
        assert request.url.params["rvprop"] == (
            "ids|timestamp|user|comment|content"
        )

        return httpx.Response(
            200,
            json=revision_payload(),
        )

    repository, transport = build_repository(handler)

    try:
        revision = await repository.get_revision("900")
    finally:
        await transport.close()

    assert revision.id == "900"
    assert revision.document_id == "42"
    assert revision.parent_id == "899"
    assert revision.author_name == "Wiki Editor"
    assert revision.comment == "Updated procedure"
    assert revision.raw_content == (
        "== Procedure ==\nRevision content"
    )
    assert revision.timestamp == datetime(
        2026,
        7,
        24,
        8,
        30,
        45,
        tzinfo=timezone.utc,
    )


@pytest.mark.asyncio
async def test_missing_revision_raises_not_found() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "badrevids": {
                        "900": {
                            "revid": 900,
                            "missing": True,
                        }
                    },
                    "pages": [],
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(
            KnowledgeNotFoundError
        ) as captured:
            await repository.get_revision("900")
    finally:
        await transport.close()

    assert captured.value.resource == "revision"
    assert captured.value.identifier == "900"


@pytest.mark.asyncio
async def test_page_without_revisions_raises_not_found() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 42,
                            "title": "Test Page",
                        }
                    ]
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(KnowledgeNotFoundError):
            await repository.get_revision("900")
    finally:
        await transport.close()


@pytest.mark.parametrize(
    "revision_id",
    [
        "",
        "   ",
        "abc",
        "0",
        "-1",
        "9.5",
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_revision_id(
    revision_id: str,
) -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        raise AssertionError(
            "Transport should not be called"
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(ValueError) as captured:
            await repository.get_revision(revision_id)
    finally:
        await transport.close()

    assert "positive integer" in str(captured.value)


@pytest.mark.asyncio
async def test_rejects_missing_query_object() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"batchcomplete": True},
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(
            MediaWikiProtocolError
        ) as captured:
            await repository.get_revision("900")
    finally:
        await transport.close()

    assert "no query object" in str(captured.value)


@pytest.mark.asyncio
async def test_rejects_invalid_pages_value() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": {
                        "42": {
                            "pageid": 42,
                        }
                    }
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(
            MediaWikiProtocolError
        ) as captured:
            await repository.get_revision("900")
    finally:
        await transport.close()

    assert "invalid pages value" in str(captured.value)


@pytest.mark.asyncio
async def test_rejects_invalid_page_id() -> None:
    payload = revision_payload()
    query = payload["query"]
    assert isinstance(query, dict)
    pages = query["pages"]
    assert isinstance(pages, list)
    page = pages[0]
    assert isinstance(page, dict)
    page["pageid"] = "42"

    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(200, json=payload)

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(
            MediaWikiProtocolError
        ) as captured:
            await repository.get_revision("900")
    finally:
        await transport.close()

    assert "invalid pageid" in str(captured.value)


@pytest.mark.asyncio
async def test_rejects_invalid_revisions_value() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 42,
                            "revisions": {},
                        }
                    ]
                }
            },
        )

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(
            MediaWikiProtocolError
        ) as captured:
            await repository.get_revision("900")
    finally:
        await transport.close()

    assert "invalid revisions value" in str(captured.value)


@pytest.mark.asyncio
async def test_ignores_unrequested_revision() -> None:
    payload = revision_payload()
    query = payload["query"]
    assert isinstance(query, dict)
    pages = query["pages"]
    assert isinstance(pages, list)
    page = pages[0]
    assert isinstance(page, dict)
    revisions = page["revisions"]
    assert isinstance(revisions, list)
    revision = revisions[0]
    assert isinstance(revision, dict)
    revision["revid"] = 901

    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(200, json=payload)

    repository, transport = build_repository(handler)

    try:
        with pytest.raises(KnowledgeNotFoundError):
            await repository.get_revision("900")
    finally:
        await transport.close()


def test_repository_is_exported_from_mediawiki_package() -> None:
    from app.services.mediawiki.repositories.revisions import (
        MediaWikiRevisionRepository as DirectRepository,
    )

    assert MediaWikiRevisionRepository is DirectRepository
