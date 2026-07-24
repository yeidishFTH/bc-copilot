from datetime import UTC, datetime

import pytest

from app.services.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.knowledge.persistence import (
    KnowledgePersistenceMapper,
)


def make_document() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="42",
        title="  נוהל   פתיחת סניף  ",
        canonical_url="https://wiki.example.test/page/42",
        namespace_id=0,
        latest_revision_id="105",
        is_redirect=False,
    )


def make_revision() -> KnowledgeDocumentRevision:
    return KnowledgeDocumentRevision(
        id="105",
        document_id="42",
        timestamp=datetime(2026, 7, 24, 8, 30, tzinfo=UTC),
        raw_content="תוכן הנוהל",
        parent_id="104",
        author_name="Test User",
        comment="Updated procedure",
        rendered_html="<p>תוכן הנוהל</p>",
    )


def test_document_to_page_maps_domain_metadata() -> None:
    page = KnowledgePersistenceMapper.document_to_page(
        make_document()
    )

    assert page.wiki_page_id == 42
    assert page.namespace_id == 0
    assert page.title == "  נוהל   פתיחת סניף  "
    assert page.normalized_title == "נוהל פתיחת סניף"
    assert page.canonical_url == "https://wiki.example.test/page/42"
    assert page.latest_revision_id == 105
    assert page.is_redirect is False
    assert page.is_active is True


def test_revision_to_models_maps_revision_and_content() -> None:
    page = KnowledgePersistenceMapper.document_to_page(
        make_document()
    )

    revision, content = (
        KnowledgePersistenceMapper.revision_to_models(
            make_revision(),
            page=page,
        )
    )

    assert revision.wiki_revision_id == 105
    assert revision.parent_revision_id == 104
    assert revision.page is page
    assert len(revision.content_sha256) == 64

    assert content.revision is revision
    assert content.raw_wikitext == "תוכן הנוהל"
    assert content.rendered_html == "<p>תוכן הנוהל</p>"
    assert content.plain_text == "תוכן הנוהל"
    assert content.language_code == "he"


def test_validate_document_revision_pair_rejects_other_document() -> None:
    revision = KnowledgeDocumentRevision(
        id="105",
        document_id="999",
        timestamp=datetime.now(UTC),
        raw_content="content",
    )

    with pytest.raises(
        ValueError,
        match="revision.document_id does not match document.id",
    ):
        KnowledgePersistenceMapper.validate_document_revision_pair(
            make_document(),
            revision,
        )


def test_validate_document_revision_pair_rejects_non_latest_revision() -> None:
    revision = KnowledgeDocumentRevision(
        id="999",
        document_id="42",
        timestamp=datetime.now(UTC),
        raw_content="content",
    )

    with pytest.raises(
        ValueError,
        match="revision.id does not match document.latest_revision_id",
    ):
        KnowledgePersistenceMapper.validate_document_revision_pair(
            make_document(),
            revision,
        )


@pytest.mark.parametrize(
    "value",
    ["", "0", "-1", "1.5", "abc", True],
)
def test_parse_positive_integer_rejects_invalid_values(
    value: object,
) -> None:
    with pytest.raises(ValueError):
        KnowledgePersistenceMapper.parse_positive_integer(
            value,  # type: ignore[arg-type]
            field_name="test",
        )
