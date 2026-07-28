from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_live_api_exposes_claim_level_citations() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/copilot/ask",
            json={
                "question": "איך מוחקים לקוח?",
                "namespace_ids": [0],
            },
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["grounded"] is True
    assert payload["citation_claims"]

    first_claim = payload["citation_claims"][0]

    assert first_claim["text"]
    assert first_claim["source_indexes"]
    assert first_claim["source_chunk_ids"]
    assert first_claim["source_titles"]
    assert first_claim["source_headings"]

    first_source = payload["sources"][0]

    assert first_source["page_id"]
    assert first_source["revision_id"]
    assert isinstance(
        first_source["wiki_page_id"],
        int,
    )
    assert isinstance(
        first_source["wiki_revision_id"],
        int,
    )
