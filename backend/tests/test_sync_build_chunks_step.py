from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.sync.pipeline import (
    BuildChunksStep,
    SyncPageState,
)


@pytest.mark.asyncio
async def test_build_chunks_step_builds_chunks() -> None:
    state = SyncPageState(
        document=KnowledgeDocument(
            id="1",
            title="Test",
            canonical_url="https://wiki.example.test/Test",
            latest_revision_id="2",
        ),
        revision=KnowledgeDocumentRevision(
            id="2",
            document_id="1",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            raw_content="== קופה ==\nבדיקת קופה.",
        ),
    )

    await BuildChunksStep().execute(state)

    assert len(state.chunks) == 1
    assert state.chunks[0].heading_path == ("קופה",)
    assert state.chunks[0].content == "בדיקת קופה."


@pytest.mark.asyncio
async def test_build_chunks_requires_revision() -> None:
    state = SyncPageState(
        document=KnowledgeDocument(
            id="1",
            title="Test",
            canonical_url="https://wiki.example.test/Test",
            latest_revision_id="2",
        ),
    )

    with pytest.raises(RuntimeError):
        await BuildChunksStep().execute(state)
