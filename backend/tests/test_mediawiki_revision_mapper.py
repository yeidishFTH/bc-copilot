from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.mediawiki import (
    MediaWikiProtocolError,
    MediaWikiRevisionMapper,
)


def build_revision(**overrides: object) -> dict[str, object]:
    revision: dict[str, object] = {
        "revid": 200,
        "parentid": 199,
        "timestamp": "2026-07-24T08:30:45Z",
        "user": "Wiki Editor",
        "comment": "Updated procedure",
        "slots": {
            "main": {
                "contentmodel": "wikitext",
                "contentformat": "text/x-wiki",
                "content": "== Procedure ==\nRevision content",
            }
        },
    }
    revision.update(overrides)
    return revision


def test_maps_revision_into_domain_model() -> None:
    mapped = MediaWikiRevisionMapper.revision_to_document_revision(
        build_revision(),
        document_id=42,
    )

    assert mapped.id == "200"
    assert mapped.document_id == "42"
    assert mapped.timestamp == datetime(
        2026,
        7,
        24,
        8,
        30,
        45,
        tzinfo=timezone.utc,
    )
    assert mapped.raw_content == (
        "== Procedure ==\nRevision content"
    )
    assert mapped.parent_id == "199"
    assert mapped.author_name == "Wiki Editor"
    assert mapped.comment == "Updated procedure"
    assert mapped.rendered_html is None


def test_maps_first_revision_without_parent() -> None:
    mapped = MediaWikiRevisionMapper.revision_to_document_revision(
        build_revision(parentid=0),
        document_id="42",
    )

    assert mapped.parent_id is None


def test_maps_missing_optional_author_and_comment() -> None:
    revision = build_revision()
    revision.pop("user")
    revision.pop("comment")

    mapped = MediaWikiRevisionMapper.revision_to_document_revision(
        revision,
        document_id="42",
    )

    assert mapped.author_name is None
    assert mapped.comment is None


def test_preserves_empty_content() -> None:
    revision = build_revision(
        slots={
            "main": {
                "content": "",
            }
        }
    )

    mapped = MediaWikiRevisionMapper.revision_to_document_revision(
        revision,
        document_id="42",
    )

    assert mapped.raw_content == ""


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_document_id(
    document_id: str,
) -> None:
    with pytest.raises(ValueError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(),
            document_id=document_id,
        )

    assert "document_id cannot be empty" in str(captured.value)


@pytest.mark.parametrize(
    "revision_id",
    [
        None,
        True,
        0,
        -1,
        "200",
    ],
)
def test_rejects_invalid_revision_id(
    revision_id: object,
) -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(revid=revision_id),
            document_id="42",
        )

    assert "invalid revid" in str(captured.value)


@pytest.mark.parametrize(
    "timestamp",
    [
        None,
        "",
        "not-a-timestamp",
        "2026-07-24T08:30:45",
        123,
    ],
)
def test_rejects_invalid_timestamp(
    timestamp: object,
) -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(timestamp=timestamp),
            document_id="42",
        )

    assert "timestamp" in str(captured.value)


@pytest.mark.parametrize(
    "parent_id",
    [
        True,
        -1,
        "199",
    ],
)
def test_rejects_invalid_parent_id(
    parent_id: object,
) -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(parentid=parent_id),
            document_id="42",
        )

    assert "invalid parentid" in str(captured.value)


@pytest.mark.parametrize(
    "slots",
    [
        None,
        [],
        "invalid",
    ],
)
def test_rejects_invalid_slots(
    slots: object,
) -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(slots=slots),
            document_id="42",
        )

    assert "invalid slots" in str(captured.value)


@pytest.mark.parametrize(
    "main_slot",
    [
        None,
        [],
        "invalid",
    ],
)
def test_rejects_invalid_main_slot(
    main_slot: object,
) -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(
                slots={
                    "main": main_slot,
                }
            ),
            document_id="42",
        )

    assert "no main slot" in str(captured.value)


def test_rejects_missing_content() -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(
                slots={
                    "main": {},
                }
            ),
            document_id="42",
        )

    assert "invalid content" in str(captured.value)


def test_rejects_hidden_content() -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(
                slots={
                    "main": {
                        "contenthidden": True,
                    }
                }
            ),
            document_id="42",
        )

    assert "content is hidden" in str(captured.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user", 123),
        ("comment", []),
    ],
)
def test_rejects_invalid_optional_text_fields(
    field: str,
    value: object,
) -> None:
    with pytest.raises(MediaWikiProtocolError):
        MediaWikiRevisionMapper.revision_to_document_revision(
            build_revision(**{field: value}),
            document_id="42",
        )


def test_mapper_is_exported_from_mediawiki_package() -> None:
    from app.services.mediawiki.mappers.revisions import (
        MediaWikiRevisionMapper as DirectRevisionMapper,
    )

    assert MediaWikiRevisionMapper is DirectRevisionMapper
