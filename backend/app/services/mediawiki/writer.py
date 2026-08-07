from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.mediawiki.auth import (
    MediaWikiAuthenticator,
)
from app.services.mediawiki.exceptions import (
    MediaWikiAPIError,
    MediaWikiProtocolError,
)
from app.services.transport import (
    HttpResponse,
    HttpTransport,
)


class MediaWikiWriter:
    """
    Writes pages through the MediaWiki Action API.
    """

    def __init__(
        self,
        *,
        transport: HttpTransport,
        authenticator: MediaWikiAuthenticator,
        api_path: str = "",
    ) -> None:
        self._transport = transport
        self._authenticator = authenticator
        self._api_path = api_path

    async def edit_page(
        self,
        *,
        title: str,
        content: str,
        summary: str,
    ) -> dict[str, Any]:

        if not title.strip():
            raise ValueError(
                "MediaWiki page title cannot be empty"
            )

        if not self._authenticator.is_authenticated:
            raise MediaWikiProtocolError(
                "MediaWiki authentication is required"
            )

        token = await self._authenticator.get_csrf_token()

        response = await self._transport.post(
            self._api_path,
            data={
                "action": "edit",
                "title": title,
                "text": content,
                "summary": summary,
                "token": token,
                "format": "json",
                "formatversion": "2",
            },
            retry=False,
        )

        payload = self._decode_payload(response)

        self._raise_api_error(payload)

        edit = payload.get("edit")

        if not isinstance(edit, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki edit response missing edit object"
            )

        return dict(edit)

    @staticmethod
    def _decode_payload(
        response: HttpResponse,
    ) -> Mapping[str, Any]:

        try:
            payload = response.json()

        except (UnicodeDecodeError, ValueError) as error:
            raise MediaWikiProtocolError(
                "MediaWiki returned invalid JSON"
            ) from error

        if not isinstance(payload, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki returned non-object JSON"
            )

        return payload

    @staticmethod
    def _raise_api_error(
        payload: Mapping[str, Any],
    ) -> None:

        error = payload.get("error")

        if error is None:
            return

        if not isinstance(error, Mapping):
            raise MediaWikiProtocolError(
                "Invalid MediaWiki error object"
            )

        raise MediaWikiAPIError(
            code=str(error.get("code", "unknown")),
            message=str(
                error.get("info")
                or "Unknown MediaWiki error"
            ),
        )
