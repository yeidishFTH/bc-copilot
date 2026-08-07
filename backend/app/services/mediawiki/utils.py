from __future__ import annotations

from urllib.parse import urlsplit


def split_mediawiki_api_url(
    api_url: str,
) -> tuple[str, str]:
    """Split an absolute MediaWiki API URL into HTTP base URL and path."""

    normalized = api_url.strip()

    if not normalized:
        raise ValueError(
            "MEDIAWIKI_API_URL cannot be empty"
        )

    parsed = urlsplit(normalized)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "MEDIAWIKI_API_URL must be an absolute HTTP or HTTPS URL"
        )

    if not parsed.path or parsed.path == "/":
        raise ValueError(
            "MEDIAWIKI_API_URL must include the MediaWiki API path"
        )

    if parsed.query or parsed.fragment:
        raise ValueError(
            "MEDIAWIKI_API_URL cannot contain a query or fragment"
        )

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    api_path = parsed.path

    return base_url, api_path
