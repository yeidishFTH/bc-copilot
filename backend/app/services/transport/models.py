from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Transport-neutral representation of an HTTP response."""

    status_code: int
    headers: Mapping[str, str]
    content: bytes
    url: str

    @property
    def text(self) -> str:
        """Decode the response body as UTF-8 with safe replacement."""
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Decode the response body as JSON."""
        return json.loads(self.content)
