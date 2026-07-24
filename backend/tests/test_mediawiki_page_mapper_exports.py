from __future__ import annotations

from app.services.mediawiki import (
    MediaWikiMapper,
    MediaWikiPageMapper,
)
from app.services.mediawiki.mapper import (
    MediaWikiMapper as LegacyMediaWikiMapper,
)
from app.services.mediawiki.mappers import (
    MediaWikiMapper as PackageMediaWikiMapper,
)
from app.services.mediawiki.mappers.pages import (
    MediaWikiPageMapper as DirectMediaWikiPageMapper,
)


def test_page_mapper_is_exported_from_all_supported_paths() -> None:
    assert MediaWikiPageMapper is DirectMediaWikiPageMapper
    assert MediaWikiMapper is MediaWikiPageMapper
    assert LegacyMediaWikiMapper is MediaWikiPageMapper
    assert PackageMediaWikiMapper is MediaWikiPageMapper


def test_legacy_mapper_maps_pages_through_page_mapper() -> None:
    document = LegacyMediaWikiMapper.page_to_document(
        {
            "pageid": 42,
            "ns": 0,
            "title": "Test Page",
            "lastrevid": 99,
            "canonicalurl": (
                "https://wiki.example.test/wiki/Test_Page"
            ),
        }
    )

    assert document.id == "42"
    assert document.latest_revision_id == "99"
