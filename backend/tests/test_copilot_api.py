from __future__ import annotations

from app.api.workspace_dependencies import (
    get_authorized_copilot_answer_service,
)

import pytest

import json
from fastapi.testclient import TestClient

from app.main import app
from app.services.copilot import (

CopilotAnswer,
    CopilotSource,
)

pytestmark = pytest.mark.usefixtures("workspace_access_override")

class FakeCopilotService:
    async def answer(
        self,
        question: str,
        **_: object,
    ) -> CopilotAnswer:
        return CopilotAnswer(
            question=question,
            answer=(
                "יש לקבל את הבקשה מהמייל "
                "הרשום. [SOURCE 1]"
            ),
            grounded=True,
            sources=(
                CopilotSource(
                    index=1,
                    title=(
                        "נוהל מחיקת "
                        "כרטיס לקוח"
                    ),
                    heading_path=(
                        "שלבי ביצוע",
                    ),
                    canonical_url=(
                        "https://wiki.example.test/"
                        "delete-customer"
                    ),
                    chunk_id="chunk-1",
                    rank=4.7,
                ),
            ),
            context_character_count=800,
            context_estimated_tokens=200,
            context_truncated=False,
        )

def test_copilot_ask_returns_grounded_answer() -> None:
    app.dependency_overrides[
        get_authorized_copilot_answer_service
    ] = lambda: FakeCopilotService()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/copilot/ask",
                json={
                    "question": (
                        "איך מוחקים כרטיס לקוח?"
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["grounded"] is True
    assert "[SOURCE 1]" in payload["answer"]
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["title"] == (
        "נוהל מחיקת כרטיס לקוח"
    )

def test_copilot_ask_validates_question() -> None:
    app.dependency_overrides[
        get_authorized_copilot_answer_service
    ] = lambda: FakeCopilotService()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/copilot/ask",
                json={
                    "question": "",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422

def test_copilot_route_exists_in_openapi() -> None:
    schema = app.openapi()

    assert "/api/copilot/ask" in schema["paths"]
    assert (
        "post"
        in schema["paths"]["/api/copilot/ask"]
    )

def test_copilot_ask_accepts_conversation_history() -> None:
    app.dependency_overrides[
        get_authorized_copilot_answer_service
    ] = lambda: FakeCopilotService()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/copilot/ask",
                json={
                    "question": (
                        "ומה עושים אם הוא מסרב?"
                    ),
                    "history": [
                        {
                            "role": "user",
                            "content": (
                                "איך מזהים לקוח חדש?"
                            ),
                        },
                        {
                            "role": "assistant",
                            "content": (
                                "יש לבצע זיהוי. "
                                "[SOURCE 1]"
                            ),
                        },
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

def test_copilot_ask_rejects_invalid_history_role() -> None:
    app.dependency_overrides[
        get_authorized_copilot_answer_service
    ] = lambda: FakeCopilotService()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/copilot/ask",
                json={
                    "question": "שאלת המשך",
                    "history": [
                        {
                            "role": "system",
                            "content": "הוראה אסורה",
                        }
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422

def test_copilot_stream_returns_ndjson_events() -> None:
    class FakeStreamingCopilotService:
        async def stream_answer(
            self,
            question: str,
            **_: object,
        ):
            yield {
                "type": "metadata",
                "question": question,
                "grounded": True,
                "sources": [],
                "context_character_count": 10,
                "context_estimated_tokens": 3,
                "context_truncated": False,
            }
            yield {
                "type": "delta",
                "delta": "שלום",
            }
            yield {
                "type": "complete",
                "answer": "שלום",
                "grounded": True,
            }

    app.dependency_overrides[
        get_authorized_copilot_answer_service
    ] = lambda: FakeStreamingCopilotService()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/copilot/ask/stream",
                json={
                    "question": "בדיקת סטרימינג",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers[
        "content-type"
    ].startswith("application/x-ndjson")

    events = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    assert [
        event["type"]
        for event in events
    ] == [
        "metadata",
        "delta",
        "complete",
    ]
