"""Backward-compatible MediaWiki mapper exports.

New source-specific mappers live under app.services.mediawiki.mappers.
"""

from app.services.mediawiki.mappers import (
    MediaWikiMapper,
    MediaWikiPageMapper,
)

__all__ = [
    "MediaWikiMapper",
    "MediaWikiPageMapper",
]
