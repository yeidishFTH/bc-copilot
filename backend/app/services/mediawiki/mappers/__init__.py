from app.services.mediawiki.mappers.pages import (
    MediaWikiPageMapper,
)
from app.services.mediawiki.mappers.revisions import (
    MediaWikiRevisionMapper,
)

MediaWikiMapper = MediaWikiPageMapper

__all__ = [
    "MediaWikiMapper",
    "MediaWikiPageMapper",
    "MediaWikiRevisionMapper",
]
