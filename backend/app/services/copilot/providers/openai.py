from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx


class OpenAIConfigurationError(RuntimeError):
    """Raised when the OpenAI client configuration is invalid."""


class OpenAIResponseError(RuntimeError):
    """Raised when OpenAI rejects a request or returns invalid data."""


class OpenAITextGenerationClient:
    """Generate grounded text through the OpenAI Responses API."""

    DEFAULT_BASE_URL = "https://api.openai.com"
    RESPONSES_PATH = "/v1/responses"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5.6",
        timeout_seconds: float = 60.0,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        normalized_api_key = api_key.strip()
        normalized_model = model.strip()
        normalized_base_url = base_url.rstrip("/")

        if not normalized_api_key:
            raise OpenAIConfigurationError(
                "OpenAI API key cannot be empty"
            )

        if not normalized_model:
            raise OpenAIConfigurationError(
                "OpenAI model cannot be empty"
            )

        if timeout_seconds <= 0:
            raise OpenAIConfigurationError(
                "OpenAI timeout must be greater than zero"
            )

        if not normalized_base_url.startswith(
            ("https://", "http://")
        ):
            raise OpenAIConfigurationError(
                "OpenAI base URL must be an absolute HTTP URL"
            )

        self._api_key = normalized_api_key
        self._model = normalized_model
        self._timeout_seconds = timeout_seconds
        self._base_url = normalized_base_url
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        normalized_system_prompt = self._normalize_prompt(
            system_prompt,
            field_name="system_prompt",
        )
        normalized_user_prompt = self._normalize_prompt(
            user_prompt,
            field_name="user_prompt",
        )

        client_arguments: dict[str, Any] = {
            "base_url": self._base_url,
            "timeout": httpx.Timeout(
                self._timeout_seconds
            ),
            "headers": {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        }

        if self._transport is not None:
            client_arguments["transport"] = self._transport

        async with httpx.AsyncClient(
            **client_arguments
        ) as client:
            try:
                response = await client.post(
                    self.RESPONSES_PATH,
                    json={
                        "model": self._model,
                        "instructions": (
                            normalized_system_prompt
                        ),
                        "input": normalized_user_prompt,
                        "reasoning": {
                            "effort": "low",
                        },
                    },
                )
            except httpx.TimeoutException as error:
                raise OpenAIResponseError(
                    "OpenAI request timed out"
                ) from error
            except httpx.RequestError as error:
                raise OpenAIResponseError(
                    "OpenAI could not be reached"
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

        return self._extract_output_text(payload)

    @classmethod
    def _extract_output_text(
        cls,
        payload: Mapping[str, Any],
    ) -> str:
        output = payload.get("output")

        if not isinstance(output, list):
            raise OpenAIResponseError(
                "OpenAI response contains no output array"
            )

        text_parts: list[str] = []

        for item in output:
            if not isinstance(item, Mapping):
                continue

            if item.get("type") != "message":
                continue

            content = item.get("content")

            if not isinstance(content, list):
                continue

            for content_item in content:
                if not isinstance(
                    content_item,
                    Mapping,
                ):
                    continue

                if (
                    content_item.get("type")
                    != "output_text"
                ):
                    continue

                text = content_item.get("text")

                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())

        generated_text = "\n".join(text_parts).strip()

        if not generated_text:
            raise OpenAIResponseError(
                "OpenAI response contains no generated text"
            )

        return generated_text

    @staticmethod
    def _normalize_prompt(
        value: str,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string"
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty"
            )

        return normalized

    @staticmethod
    def _format_http_error(
        response: httpx.Response,
    ) -> str:
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
