from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.knowledge.persistence import DocumentUpsertStatus
from app.services.sync import (
    FetchRevisionStep,
    PersistDocumentStep,
    SyncPageState,
    SyncPipeline,
)


pytestmark = pytest.mark.asyncio


def make_document() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="42",
        title="Test page",
        canonical_url="https://wiki.test/42",
        latest_revision_id="105",
    )


def make_revision() -> KnowledgeDocumentRevision:
    return KnowledgeDocumentRevision(
        id="105",
        document_id="42",
        timestamp=datetime(2026, 7, 24, tzinfo=UTC),
        raw_content="Test content",
    )


class FakeSource:
    source_name = "fake"

    def __init__(
        self,
        revision: KnowledgeDocumentRevision,
    ) -> None:
        self.revision = revision
        self.requested_revision_ids: list[str] = []

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        self.requested_revision_ids.append(revision_id)
        return self.revision


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[
            tuple[KnowledgeDocument, KnowledgeDocumentRevision]
        ] = []

    async def upsert(
        self,
        *,
        document: KnowledgeDocument,
        revision: KnowledgeDocumentRevision,
    ) -> Any:
        self.calls.append((document, revision))

        return SimpleNamespace(
            status=DocumentUpsertStatus.created,
        )


class RecordingStep:
    def __init__(
        self,
        name: str,
        calls: list[str],
    ) -> None:
        self._name = name
        self._calls = calls

    async def execute(
        self,
        state: SyncPageState,
    ) -> None:
        self._calls.append(self._name)


async def test_pipeline_executes_steps_in_order() -> None:
    calls: list[str] = []

    pipeline = SyncPipeline(
        steps=(
            RecordingStep("first", calls),
            RecordingStep("second", calls),
            RecordingStep("third", calls),
        )
    )

    state = await pipeline.run(make_document())

    assert calls == ["first", "second", "third"]
    assert state.document == make_document()


async def test_fetch_revision_step_enriches_state() -> None:
    revision = make_revision()
    source = FakeSource(revision)
    state = SyncPageState(document=make_document())

    step = FetchRevisionStep(source)  # type: ignore[arg-type]
    await step.execute(state)

    assert state.revision is revision
    assert source.requested_revision_ids == ["105"]


async def test_fetch_revision_step_rejects_missing_revision_id() -> None:
    document = KnowledgeDocument(
        id="42",
        title="Test page",
        canonical_url="https://wiki.test/42",
        latest_revision_id=None,
    )
    source = FakeSource(make_revision())
    state = SyncPageState(document=document)

    step = FetchRevisionStep(source)  # type: ignore[arg-type]

    with pytest.raises(
        ValueError,
        match="document.latest_revision_id is required for sync",
    ):
        await step.execute(state)


async def test_persist_document_step_uses_fetched_revision() -> None:
    document = make_document()
    revision = make_revision()
    repository = FakeRepository()

    state = SyncPageState(
        document=document,
        revision=revision,
    )

    step = PersistDocumentStep(
        repository,  # type: ignore[arg-type]
    )
    await step.execute(state)

    assert repository.calls == [(document, revision)]
    assert state.upsert_result is not None
    assert (
        state.upsert_result.status
        is DocumentUpsertStatus.created
    )


async def test_persist_document_step_requires_revision() -> None:
    repository = FakeRepository()
    state = SyncPageState(document=make_document())

    step = PersistDocumentStep(
        repository,  # type: ignore[arg-type]
    )

    with pytest.raises(
        RuntimeError,
        match="sync pipeline state does not contain a revision",
    ):
        await step.execute(state)


async def test_pipeline_requires_at_least_one_step() -> None:
    with pytest.raises(
        ValueError,
        match="sync pipeline must contain at least one step",
    ):
        SyncPipeline(steps=())
