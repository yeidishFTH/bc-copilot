from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from app.services.mediawiki.exceptions import (
    MediaWikiAPIError,
    MediaWikiProtocolError,
)
from app.services.transport import HttpResponse, HttpTransport


class MediaWikiAPI:
    """Low-level client for MediaWiki Action API query requests.

    This layer is intentionally source-specific. It is responsible for
    transport interaction, response validation, API errors, and continuation.

    Domain mapping belongs in higher-level repositories and mappers.
    """

    _RESERVED_PARAMETERS = frozenset(
        {
            "action",
            "format",
            "formatversion",
        }
    )

    def __init__(
        self,
        *,
        transport: HttpTransport,
        api_path: str = "",
        max_continuation_requests: int = 10_000,
    ) -> None:
        if max_continuation_requests < 1:
            raise ValueError(
                "max_continuation_requests must be at least 1"
            )

        self._transport = transport
        self._api_path = api_path
        self._max_continuation_requests = max_continuation_requests

    async def query(
        self,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Execute one action=query request and return a validated payload."""

        request_params = self._build_query_params(params)

        response = await self._transport.get(
            self._api_path,
            params=request_params,
        )

        payload = self._decode_payload(response)
        self._raise_api_error(payload)

        return payload

    async def iter_query(
        self,
        params: Mapping[str, Any],
    ) -> AsyncIterator[Mapping[str, Any]]:
        """Yield every response page while following MediaWiki continuation."""

        base_params = dict(params)
        continuation: dict[str, Any] = {}

        for _ in range(self._max_continuation_requests):
            request_params = {
                **base_params,
                **continuation,
            }

            payload = await self.query(request_params)
            yield payload

            next_continuation = payload.get("continue")

            if next_continuation is None:
                return

            if not isinstance(next_continuation, Mapping):
                raise MediaWikiProtocolError(
                    "MediaWiki continuation value must be an object"
                )

            if not next_continuation:
                raise MediaWikiProtocolError(
                    "MediaWiki returned an empty continuation object"
                )

            continuation = dict(next_continuation)

        raise MediaWikiProtocolError(
            "MediaWiki continuation exceeded the configured request limit"
        )

    @classmethod
    def _build_query_params(
        cls,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        conflicting_parameters = cls._RESERVED_PARAMETERS.intersection(
            params
        )

        if conflicting_parameters:
            conflicting_names = ", ".join(
                sorted(conflicting_parameters)
            )
            raise ValueError(
                "MediaWiki query parameters contain reserved fields: "
                f"{conflicting_names}"
            )

        return {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            **params,
        }

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
                "MediaWiki returned a non-object JSON response"
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
                "MediaWiki returned an invalid API error object"
            )

        code = str(error.get("code", "unknown"))
        message = str(
            error.get("info")
            or error.get("*")
            or "Unknown MediaWiki API error"
        )

        raise MediaWikiAPIError(
            code=code,
            message=message,
        )
