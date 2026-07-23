from __future__ import annotations

import pytest

from app.services.mediawiki import (
    MediaWikiMapper,
    MediaWikiProtocolError,
)


def test_page_to_document_maps_mediawiki_metadata() -> None:
    document = MediaWikiMapper.page_to_document(
        {
            "pageid": 42,
            "ns": 0,
            "title": "נוהל פתיחת סניף",
            "lastrevid": 987,
            "canonicalurl": (
                "https://wiki.example.test/wiki/"
                "%D7%A0%D7%95%D7%94%D7%9C"
            ),
        }
    )

    assert document.id == "42"
    assert document.title == "נוהל פתיחת סניף"
    assert document.namespace_id == 0
    assert document.latest_revision_id == "987"
    assert document.is_redirect is False
    assert document.canonical_url.startswith(
        "https://wiki.example.test/wiki/"
    )


def test_page_to_document_maps_redirect_flag() -> None:
    document = MediaWikiMapper.page_to_document(
        {
            "pageid": 5,
            "ns": 0,
            "title": "Old title",
            "lastrevid": 10,
            "canonicalurl": (
                "https://wiki.example.test/wiki/Old_title"
            ),
            "redirect": True,
        }
    )

    assert document.is_redirect is True


def test_page_to_document_accepts_presence_style_redirect_flag() -> None:
    document = MediaWikiMapper.page_to_document(
        {
            "pageid": 5,
            "ns": 0,
            "title": "Old title",
            "canonicalurl": (
                "https://wiki.example.test/wiki/Old_title"
            ),
            "redirect": "",
        }
    )

    assert document.is_redirect is True


def test_page_to_document_falls_back_to_full_url() -> None:
    document = MediaWikiMapper.page_to_document(
        {
            "pageid": 8,
            "ns": 2,
            "title": "User:Copilot",
            "fullurl": (
                "https://wiki.example.test/wiki/User:Copilot"
            ),
        }
    )

    assert document.canonical_url == (
        "https://wiki.example.test/wiki/User:Copilot"
    )
    assert document.latest_revision_id is None


@pytest.mark.parametrize(
    ("page", "expected_message"),
    [
        (
            {
                "ns": 0,
                "title": "Page",
                "canonicalurl": "https://example.test/Page",
            },
            "invalid pageid",
        ),
        (
            {
                "pageid": 1,
                "title": "Page",
                "canonicalurl": "https://example.test/Page",
            },
            "invalid namespace",
        ),
        (
            {
                "pageid": 1,
                "ns": 0,
                "canonicalurl": "https://example.test/Page",
            },
            "invalid title",
        ),
        (
            {
                "pageid": 1,
                "ns": 0,
                "title": "Page",
            },
            "no canonical URL",
        ),
        (
            {
                "pageid": 1,
                "ns": 0,
                "title": "Page",
                "canonicalurl": "https://example.test/Page",
                "lastrevid": "invalid",
            },
            "invalid lastrevid",
        ),
    ],
)
def test_page_to_document_rejects_invalid_page_objects(
    page: dict[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(MediaWikiProtocolError) as captured:
        MediaWikiMapper.page_to_document(page)

    assert expected_message in str(captured.value)
