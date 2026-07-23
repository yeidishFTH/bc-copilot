from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from app.services.transport.exceptions import (
    TransportClosedError,
    TransportConnectionError,
    TransportHTTPError,
    TransportTimeoutError,
)
from app.services.transport.models import HttpResponse
from app.services.transport.retry import RetryPolicy, parse_retry_after

SleepFunction = Callable[[float], Awaitable[None]]


class HttpTransport:
    """Reusable asynchronous HTTP transport with bounded retry behavior."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        default_headers: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
        http_transport: httpx.AsyncBaseTransport | None = None,
        sleep: SleepFunction = asyncio.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        client_arguments: dict[str, Any] = {
            "timeout": httpx.Timeout(timeout_seconds),
            "headers": dict(default_headers or {}),
            "follow_redirects": True,
        }

        if base_url is not None:
            client_arguments["base_url"] = base_url

        if http_transport is not None:
            client_arguments["transport"] = http_transport

        self._client = httpx.AsyncClient(**client_arguments)
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    async def __aenter__(self) -> HttpTransport:
        if self._closed:
            raise TransportClosedError("HTTP transport is closed")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc_value, traceback
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        await self._client.aclose()

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        retry: bool | None = None,
    ) -> HttpResponse:
        return await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            retry=retry,
        )

    async def post(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, Any] | None = None,
        json_body: Any = None,
        retry: bool | None = None,
    ) -> HttpResponse:
        return await self.request(
            "POST",
            url,
            params=params,
            headers=headers,
            data=data,
            json_body=json_body,
            retry=retry,
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        content: bytes | str | None = None,
        data: Mapping[str, Any] | None = None,
        json_body: Any = None,
        retry: bool | None = None,
    ) -> HttpResponse:
        if self._closed:
            raise TransportClosedError("HTTP transport is closed")

        normalized_method = method.upper()
        retry_enabled = (
            self._retry_policy.supports_method(normalized_method)
            if retry is None
            else retry
        )
        maximum_attempts = (
            self._retry_policy.max_attempts if retry_enabled else 1
        )

        for attempt in range(1, maximum_attempts + 1):
            try:
                response = await self._client.request(
                    normalized_method,
                    url,
                    params=params,
                    headers=headers,
                    content=content,
                    data=data,
                    json=json_body,
                )
            except httpx.TimeoutException as error:
                if attempt < maximum_attempts:
                    await self._sleep(
                        self._retry_policy.delay_seconds(
                            failed_attempt=attempt
                        )
                    )
                    continue

                raise TransportTimeoutError(
                    "HTTP request timed out",
                    method=normalized_method,
                    url=self._absolute_url(url),
                ) from error
            except httpx.RequestError as error:
                if attempt < maximum_attempts:
                    await self._sleep(
                        self._retry_policy.delay_seconds(
                            failed_attempt=attempt
                        )
                    )
                    continue

                raise TransportConnectionError(
                    "HTTP request failed because the remote service "
                    "could not be reached",
                    method=normalized_method,
                    url=self._absolute_url(url),
                ) from error

            retry_after_seconds = parse_retry_after(
                response.headers.get("Retry-After")
            )

            if (
                retry_enabled
                and self._retry_policy.supports_status(response.status_code)
                and attempt < maximum_attempts
            ):
                await self._sleep(
                    self._retry_policy.delay_seconds(
                        failed_attempt=attempt,
                        retry_after_seconds=retry_after_seconds,
                    )
                )
                continue

            if response.is_error:
                raise TransportHTTPError(
                    status_code=response.status_code,
                    method=normalized_method,
                    url=str(response.url),
                    body_preview=self._body_preview(response.content),
                    retry_after_seconds=retry_after_seconds,
                )

            return HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                content=response.content,
                url=str(response.url),
            )

        raise RuntimeError("HTTP request loop ended unexpectedly")

    def _absolute_url(self, url: str) -> str:
        try:
            return str(self._client.base_url.join(url))
        except Exception:
            return url

    @staticmethod
    def _body_preview(content: bytes, *, maximum_length: int = 500) -> str | None:
        if not content:
            return None

        return content[:maximum_length].decode(
            "utf-8",
            errors="replace",
        )
