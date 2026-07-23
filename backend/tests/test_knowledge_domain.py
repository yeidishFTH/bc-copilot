from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.services.knowledge import (
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    KnowledgeLink,
    KnowledgeNotFoundError,
    KnowledgeRateLimitError,
    KnowledgeSource,
)


class FakeKnowledgeSource:
    @property
    def source_name(self) -> str:
        return "fake"

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> list[KnowledgeDocument]:
        del namespace_id, limit
        return []

    async def get_page(self, identifier: str) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=identifier,
            title="Test Page",
            canonical_url="https://example.test/wiki/Test_Page",
        )

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        return KnowledgeDocumentRevision(
            id=revision_id,
            document_id="1",
            timestamp=datetime(2026, 7, 23, tzinfo=UTC),
            raw_content="Test content",
        )

    async def get_categories(
        self,
        page_identifier: str,
    ) -> list[KnowledgeCategory]:
        del page_identifier
        return [KnowledgeCategory(name="Test")]


def test_knowledge_document_has_immutable_domain_data() -> None:
    document = KnowledgeDocument(
        id="123",
        title="נוהל פתיחת סניף",
        canonical_url="https://wiki.example.test/נוהל_פתיחת_סניף",
        latest_revision_id="987",
        categories=(KnowledgeCategory(name="נהלים"),),
        links=(KnowledgeLink(target_title="צ'קליסט פתיחה"),),
    )

    assert document.categories[0].name == "נהלים"
    assert document.links[0].target_title == "צ'קליסט פתיחה"

    with pytest.raises(FrozenInstanceError):
        document.title = "Changed"  # type: ignore[misc]


def test_fake_adapter_satisfies_knowledge_source_protocol() -> None:
    source = FakeKnowledgeSource()

    assert isinstance(source, KnowledgeSource)
    assert source.source_name == "fake"


@pytest.mark.asyncio
async def test_fake_adapter_returns_domain_models() -> None:
    source = FakeKnowledgeSource()

    assert await source.health() is True

    document = await source.get_page("123")
    revision = await source.get_revision("987")
    categories = await source.get_categories("123")

    assert document.id == "123"
    assert revision.document_id == "1"
    assert categories == [KnowledgeCategory(name="Test")]


def test_not_found_error_keeps_resource_context() -> None:
    error = KnowledgeNotFoundError("document", "Missing Page")

    assert error.resource == "document"
    assert error.identifier == "Missing Page"
    assert str(error) == "document not found: Missing Page"


def test_rate_limit_error_keeps_retry_hint() -> None:
    error = KnowledgeRateLimitError(retry_after_seconds=2.5)

    assert error.retry_after_seconds == 2.5
