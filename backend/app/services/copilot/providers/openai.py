from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping

import httpx

from app.services.openai import (
    OpenAIClientBase,
    OpenAIConfigurationError,
    OpenAIResponseError,
)


class OpenAITextGenerationClient(OpenAIClientBase):
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
        super().__init__(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            base_url=base_url,
            transport=transport,
        )

        if not isinstance(model, str):
            raise OpenAIConfigurationError(
                "OpenAI model must be a string"
            )

        normalized_model = model.strip()

        if not normalized_model:
            raise OpenAIConfigurationError(
                "OpenAI model cannot be empty"
            )

        self._model = normalized_model

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

        payload = await self._post_json(
            self.RESPONSES_PATH,
            body=self._build_request_body(
                system_prompt=normalized_system_prompt,
                user_prompt=normalized_user_prompt,
                stream=False,
            ),
            timeout_message=(
                "OpenAI request timed out"
            ),
            connection_message=(
                "OpenAI could not be reached"
            ),
        )

        return self._extract_output_text(payload)

    async def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        normalized_system_prompt = self._normalize_prompt(
            system_prompt,
            field_name="system_prompt",
        )
        normalized_user_prompt = self._normalize_prompt(
            user_prompt,
            field_name="user_prompt",
        )

        async with self._build_client() as client:
            try:
                async with client.stream(
                    "POST",
                    self.RESPONSES_PATH,
                    json=self._build_request_body(
                        system_prompt=normalized_system_prompt,
                        user_prompt=normalized_user_prompt,
                        stream=True,
                    ),
                ) as response:
                    if response.is_error:
                        body = await response.aread()
                        error_response = httpx.Response(
                            status_code=response.status_code,
                            headers=response.headers,
                            content=body,
                            request=response.request,
                        )
                        raise OpenAIResponseError(
                            self._format_http_error(
                                error_response
                            )
                        )

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue

                        data = line[5:].strip()

                        if not data or data == "[DONE]":
                            continue

                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError as error:
                            raise OpenAIResponseError(
                                "OpenAI returned invalid streaming JSON"
                            ) from error

                        if not isinstance(event, Mapping):
                            continue

                        event_type = event.get("type")

                        if event_type == "response.output_text.delta":
                            delta = event.get("delta")

                            if isinstance(delta, str) and delta:
                                yield delta

                        elif event_type in {
                            "response.failed",
                            "response.incomplete",
                            "error",
                        }:
                            raise OpenAIResponseError(
                                self._format_stream_error(event)
                            )

            except httpx.TimeoutException as error:
                raise OpenAIResponseError(
                    "OpenAI streaming request timed out"
                ) from error
            except httpx.RequestError as error:
                raise OpenAIResponseError(
                    "OpenAI streaming connection failed"
                ) from error

    def _build_request_body(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": self._model,
            "instructions": system_prompt,
            "input": user_prompt,
            "reasoning": {
                "effort": "low",
            },
            "stream": stream,
        }

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
    def _format_stream_error(
        event: Mapping[str, Any],
    ) -> str:
        error = event.get("error")

        if isinstance(error, Mapping):
            message = error.get("message")

            if isinstance(message, str) and message.strip():
                return (
                    "OpenAI streaming failed: "
                    f"{message.strip()}"
                )

        event_type = event.get("type")

        return (
            "OpenAI streaming failed"
            if not isinstance(event_type, str)
            else f"OpenAI streaming failed: {event_type}"
        )
