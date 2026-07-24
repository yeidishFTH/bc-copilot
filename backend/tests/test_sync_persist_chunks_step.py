from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.services.knowledge.models import (
    KnowledgeChunkDraft,
    KnowledgeDocument,
)
from app.services.sync.pipeline import (
    PersistChunksStep,
    SyncPageState,
)


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def replace_chunks(
        self,
        *,
        revision: object,
        chunks: tuple[KnowledgeChunkDraft, ...],
    ) -> list[object]:
        self.calls.append(
            {
                "revision": revision,
                "chunks": chunks,
            }
        )
        return []


def make_document() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="1",
        title="Test",
        canonical_url="https://wiki.example.test/Test",
        latest_revision_id="2",
    )


@pytest.mark.asyncio
async def test_persist_chunks_step_replaces_revision_chunks() -> None:
    repository = FakeDocumentRepository()
    persistence_revision = object()

    chunks = (
        KnowledgeChunkDraft(
            heading_path=("קופה",),
            content="בדיקת קופה.",
        ),
        KnowledgeChunkDraft(
            heading_path=("כספת",),
            content="בדיקת כספת.",
        ),
    )

    state = SyncPageState(
        document=make_document(),
        chunks=chunks,
    )
    state.upsert_result = cast(
        Any,
        SimpleNamespace(revision=persistence_revision),
    )

    await PersistChunksStep(
        cast(Any, repository)
    ).execute(state)

    assert repository.calls == [
        {
            "revision": persistence_revision,
            "chunks": chunks,
        }
    ]


@pytest.mark.asyncio
async def test_persist_chunks_step_persists_empty_replacement() -> None:
    repository = FakeDocumentRepository()
    persistence_revision = object()

    state = SyncPageState(document=make_document())
    state.upsert_result = cast(
        Any,
        SimpleNamespace(revision=persistence_revision),
    )

    await PersistChunksStep(
        cast(Any, repository)
    ).execute(state)

    assert repository.calls == [
        {
            "revision": persistence_revision,
            "chunks": (),
        }
    ]


@pytest.mark.asyncio
async def test_persist_chunks_step_requires_upsert_result() -> None:
    repository = FakeDocumentRepository()
    state = SyncPageState(document=make_document())

    with pytest.raises(
        RuntimeError,
        match="sync pipeline state does not contain an upsert result",
    ):
        await PersistChunksStep(
            cast(Any, repository)
        ).execute(state)

    assert repository.calls == []
