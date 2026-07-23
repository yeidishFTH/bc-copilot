from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MediaWikiCredentials:
    """Credentials created through MediaWiki Special:BotPasswords."""

    username: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class MediaWikiSession:
    """Authenticated MediaWiki user information."""

    user_id: int
    username: str
    groups: tuple[str, ...] = ()
    rights: tuple[str, ...] = ()
