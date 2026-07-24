from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.knowledge import (
    KnowledgeAuthenticationError,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    KnowledgeSource,
)
from app.services.mediawiki import (
    MediaWikiCategoryReader,
    MediaWikiKnowledgeSource,
    MediaWikiPageReader,
    MediaWikiRevisionReader,
)


class FakeAuthenticator:
    def __init__(
        self,
        *,
        authenticated: bool = False,
    ) -> None:
        self.is_authenticated = authenticated
        self.login_calls = 0
        self.logout_calls = 0
        self.validate_calls = 0
        self.validation_error: Exception | None = None
        self.logout_error: Exception | None = None

    async def login(self) -> object:
        self.login_calls += 1
        self.is_authenticated = True
        return object()

    async def logout(self) -> None:
        self.logout_calls += 1

        if self.logout_error is not None:
            raise self.logout_error

        self.is_authenticated = False

    async def validate_session(self) -> object:
        self.validate_calls += 1

        if self.validation_error is not None:
            raise self.validation_error

        return object()


class FakeTransport:
    def __init__(self) -> None:
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


class FakePageRepository:
    def __init__(self) -> None:
        self.list_calls: list[tuple[int, int | None]] = []
        self.get_calls: list[str] = []

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> tuple[KnowledgeDocument, ...]:
        self.list_calls.append((namespace_id, limit))

        return (
            KnowledgeDocument(
                id="1",
                title="Main Page",
                canonical_url=(
                    "https://wiki.example.test/wiki/Main_Page"
                ),
            ),
        )

    async def get_page(
        self,
        identifier: str,
    ) -> KnowledgeDocument:
        self.get_calls.append(identifier)

        return KnowledgeDocument(
            id=identifier,
            title="Test Page",
            canonical_url=(
                "https://wiki.example.test/wiki/Test_Page"
            ),
        )


class FakeRevisionRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        self.calls.append(revision_id)

        return KnowledgeDocumentRevision(
            id=revision_id,
            document_id="1",
            timestamp=datetime(2026, 7, 24, tzinfo=UTC),
            raw_content="Test content",
        )


class FakeCategoryRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_categories(
        self,
        page_identifier: str,
    ) -> tuple[KnowledgeCategory, ...]:
        self.calls.append(page_identifier)

        return (
            KnowledgeCategory(name="Procedures"),
        )


def build_source(
    *,
    authenticated: bool = False,
) -> tuple[
    MediaWikiKnowledgeSource,
    FakeAuthenticator,
    FakeTransport,
    FakePageRepository,
    FakeRevisionRepository,
    FakeCategoryRepository,
]:
    authenticator = FakeAuthenticator(
        authenticated=authenticated
    )
    transport = FakeTransport()
    pages = FakePageRepository()
    revisions = FakeRevisionRepository()
    categories = FakeCategoryRepository()

    source = MediaWikiKnowledgeSource(
        authenticator=authenticator,  # type: ignore[arg-type]
        transport=transport,  # type: ignore[arg-type]
        pages=pages,
        revisions=revisions,
        categories=categories,
    )

    return (
        source,
        authenticator,
        transport,
        pages,
        revisions,
        categories,
    )


def test_source_satisfies_knowledge_source_protocol() -> None:
    source, *_ = build_source()

    assert isinstance(source, KnowledgeSource)
    assert source.source_name == "mediawiki"


def test_repository_fakes_satisfy_source_contracts() -> None:
    _, _, _, pages, revisions, categories = build_source()

    assert isinstance(pages, MediaWikiPageReader)
    assert isinstance(revisions, MediaWikiRevisionReader)
    assert isinstance(categories, MediaWikiCategoryReader)


@pytest.mark.asyncio
async def test_connect_authenticates_once() -> None:
    source, authenticator, *_ = build_source()

    await source.connect()
    await source.connect()

    assert authenticator.login_calls == 1
    assert source.is_connected is True


@pytest.mark.asyncio
async def test_health_validates_connected_session() -> None:
    source, authenticator, *_ = build_source(
        authenticated=True
    )

    assert await source.health() is True
    assert authenticator.validate_calls == 1


@pytest.mark.asyncio
async def test_health_returns_false_when_not_connected() -> None:
    source, authenticator, *_ = build_source()

    assert await source.health() is False
    assert authenticator.validate_calls == 0


@pytest.mark.asyncio
async def test_health_returns_false_for_expired_session() -> None:
    source, authenticator, *_ = build_source(
        authenticated=True
    )
    authenticator.validation_error = (
        KnowledgeAuthenticationError("Session expired")
    )

    assert await source.health() is False
    assert authenticator.validate_calls == 1


@pytest.mark.asyncio
async def test_source_delegates_all_knowledge_operations() -> None:
    (
        source,
        _,
        _,
        pages,
        revisions,
        categories,
    ) = build_source(authenticated=True)

    documents = await source.list_pages(
        namespace_id=4,
        limit=25,
    )
    document = await source.get_page("42")
    revision = await source.get_revision("900")
    result_categories = await source.get_categories("42")

    assert documents[0].title == "Main Page"
    assert document.id == "42"
    assert revision.id == "900"
    assert result_categories[0].name == "Procedures"

    assert pages.list_calls == [(4, 25)]
    assert pages.get_calls == ["42"]
    assert revisions.calls == ["900"]
    assert categories.calls == ["42"]


@pytest.mark.asyncio
async def test_operations_require_connection() -> None:
    source, *_ = build_source()

    with pytest.raises(KnowledgeAuthenticationError):
        await source.list_pages()

    with pytest.raises(KnowledgeAuthenticationError):
        await source.get_page("1")

    with pytest.raises(KnowledgeAuthenticationError):
        await source.get_revision("2")

    with pytest.raises(KnowledgeAuthenticationError):
        await source.get_categories("1")


@pytest.mark.asyncio
async def test_close_logs_out_and_closes_transport() -> None:
    source, authenticator, transport, *_ = build_source(
        authenticated=True
    )

    await source.close()
    await source.close()

    assert authenticator.logout_calls == 1
    assert transport.close_calls == 1
    assert source.is_connected is False


@pytest.mark.asyncio
async def test_close_releases_transport_when_logout_fails() -> None:
    source, authenticator, transport, *_ = build_source(
        authenticated=True
    )
    authenticator.logout_error = RuntimeError(
        "Logout failed"
    )

    with pytest.raises(RuntimeError, match="Logout failed"):
        await source.close()

    assert authenticator.logout_calls == 1
    assert transport.close_calls == 1
    assert source.is_connected is False


@pytest.mark.asyncio
async def test_closed_source_cannot_be_reconnected_or_used() -> None:
    source, *_ = build_source(authenticated=True)

    await source.close()

    with pytest.raises(RuntimeError, match="already been closed"):
        await source.connect()

    with pytest.raises(RuntimeError, match="already been closed"):
        await source.get_page("1")


def test_source_rejects_empty_name() -> None:
    (
        _,
        authenticator,
        transport,
        pages,
        revisions,
        categories,
    ) = build_source()

    with pytest.raises(ValueError, match="source_name"):
        MediaWikiKnowledgeSource(
            authenticator=authenticator,  # type: ignore[arg-type]
            transport=transport,  # type: ignore[arg-type]
            pages=pages,
            revisions=revisions,
            categories=categories,
            source_name="   ",
        )
