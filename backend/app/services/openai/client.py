from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx


class OpenAIConfigurationError(RuntimeError):
    """Raised when OpenAI client configuration is invalid."""


class OpenAIResponseError(RuntimeError):
    """Raised when OpenAI rejects a request or returns invalid data."""


class OpenAIClientBase:
    """
    Shared asynchronous HTTP foundation for OpenAI service clients.

    Responsibilities:
    - validate API and transport configuration;
    - construct authenticated HTTP clients;
    - normalize network and timeout errors;
    - validate JSON object responses;
    - preserve useful OpenAI HTTP error details.

    Endpoint-specific request and response handling belongs in subclasses.
    """

    DEFAULT_BASE_URL = "https://api.openai.com"

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 60.0,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not isinstance(api_key, str):
            raise OpenAIConfigurationError(
                "OpenAI API key must be a string"
            )

        normalized_api_key = api_key.strip()

        if not normalized_api_key:
            raise OpenAIConfigurationError(
                "OpenAI API key cannot be empty"
            )

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(
                timeout_seconds,
                (int, float),
            )
            or timeout_seconds <= 0
        ):
            raise OpenAIConfigurationError(
                "OpenAI timeout must be greater than zero"
            )

        if not isinstance(base_url, str):
            raise OpenAIConfigurationError(
                "OpenAI base URL must be a string"
            )

        normalized_base_url = base_url.rstrip("/")

        if not normalized_base_url.startswith(
            ("https://", "http://")
        ):
            raise OpenAIConfigurationError(
                "OpenAI base URL must be an absolute HTTP URL"
            )

        self._api_key = normalized_api_key
        self._timeout_seconds = float(timeout_seconds)
        self._base_url = normalized_base_url
        self._transport = transport

    def _build_client(self) -> httpx.AsyncClient:
        """Build one authenticated asynchronous OpenAI HTTP client."""

        client_arguments: dict[str, Any] = {
            "base_url": self._base_url,
            "timeout": httpx.Timeout(
                self._timeout_seconds
            ),
            "headers": {
                "Authorization": (
                    f"Bearer {self._api_key}"
                ),
                "Content-Type": "application/json",
            },
        }

        if self._transport is not None:
            client_arguments["transport"] = self._transport

        return httpx.AsyncClient(**client_arguments)

    async def _post_json(
        self,
        path: str,
        *,
        body: Mapping[str, Any],
        timeout_message: str,
        connection_message: str,
    ) -> Mapping[str, Any]:
        """
        POST JSON and return a validated JSON object response.

        Subclasses remain responsible for interpreting the response fields.
        """

        async with self._build_client() as client:
            try:
                response = await client.post(
                    path,
                    json=dict(body),
                )
            except httpx.TimeoutException as error:
                raise OpenAIResponseError(
                    timeout_message
                ) from error
            except httpx.RequestError as error:
                raise OpenAIResponseError(
                    connection_message
                ) from error

        if response.is_error:
            raise OpenAIResponseError(
                self._format_http_error(response)
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise OpenAIResponseError(
                "OpenAI returned invalid JSON"
            ) from error

        if not isinstance(payload, Mapping):
            raise OpenAIResponseError(
                "OpenAI returned a non-object response"
            )

        return payload

    @staticmethod
    def _format_http_error(
        response: httpx.Response,
    ) -> str:
        """Return a safe OpenAI HTTP error with an optional API detail."""

        message = (
            f"OpenAI returned HTTP "
            f"{response.status_code}"
        )

        try:
            payload = response.json()
        except ValueError:
            return message

        if not isinstance(payload, Mapping):
            return message

        error = payload.get("error")

        if not isinstance(error, Mapping):
            return message

        detail = error.get("message")

        if isinstance(detail, str) and detail.strip():
            return f"{message}: {detail.strip()}"

        return message
