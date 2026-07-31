from __future__ import annotations

from app.api.workspace_dependencies import (
    get_authorized_knowledge_retrieval_service,
)

import pytest

from collections.abc import Sequence

from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge.models import KnowledgeSearchResult

pytestmark = pytest.mark.usefixtures("workspace_access_override")

class FakeKnowledgeRetrievalService:
    def __init__(
        self,
        results: Sequence[KnowledgeSearchResult] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.results = tuple(results)
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        self.calls.append(
            {
                "query": query,
                "limit": limit,
                "namespace_ids": namespace_ids,
            }
        )

        if self.error is not None:
            raise self.error

        return self.results

def make_result() -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        page_id="page-1",
        revision_id="revision-1",
        chunk_id="chunk-1",
        wiki_page_id=101,
        wiki_revision_id=202,
        title="נוהל פתיחת סניף",
        canonical_url="https://wiki.example.test/opening",
        namespace_id=0,
        position=2,
        heading_path=("פתיחת סניף", "ספירת מזומן"),
        content="יש לבצע ספירת מזומן בתחילת המשמרת.",
        token_count=7,
        rank=0.875,
    )

def test_search_endpoint_returns_ranked_results() -> None:
    service = FakeKnowledgeRetrievalService([make_result()])

    app.dependency_overrides[
        get_authorized_knowledge_retrieval_service
    ] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/knowledge/search",
                json={
                    "query": "  ספירת   מזומן  ",
                    "limit": 5,
                    "namespace_ids": [0],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["query"] == "ספירת מזומן"
    assert payload["count"] == 1
    assert payload["results"][0] == {
        "page_id": "page-1",
        "revision_id": "revision-1",
        "chunk_id": "chunk-1",
        "wiki_page_id": 101,
        "wiki_revision_id": 202,
        "title": "נוהל פתיחת סניף",
        "canonical_url": (
            "https://wiki.example.test/opening"
        ),
        "namespace_id": 0,
        "position": 2,
        "heading_path": [
            "פתיחת סניף",
            "ספירת מזומן",
        ],
        "content": (
            "יש לבצע ספירת מזומן בתחילת המשמרת."
        ),
        "token_count": 7,
        "rank": 0.875,
    }

    assert service.calls == [
        {
            "query": "  ספירת   מזומן  ",
            "limit": 5,
            "namespace_ids": [0],
        }
    ]

def test_search_endpoint_validates_request() -> None:
    service = FakeKnowledgeRetrievalService()

    app.dependency_overrides[
        get_authorized_knowledge_retrieval_service
    ] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/knowledge/search",
                json={
                    "query": "",
                    "limit": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert service.calls == []

def test_search_endpoint_returns_503_on_service_failure() -> None:
    service = FakeKnowledgeRetrievalService(
        error=RuntimeError("database unavailable")
    )

    app.dependency_overrides[
        get_authorized_knowledge_retrieval_service
    ] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/knowledge/search",
                json={
                    "query": "פתיחת סניף",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Knowledge search unavailable"
    }
