from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.services.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.sync import (
    BuildChunksStep,
    FetchRevisionStep,
    PersistChunksStep,
    PersistDocumentStep,
    build_default_sync_pipeline,
)


class FakeKnowledgeSource:
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


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.persistence_revision = SimpleNamespace(id="database-revision-id")

    async def upsert(
        self,
        *,
        document: KnowledgeDocument,
        revision: KnowledgeDocumentRevision,
    ) -> Any:
        self.calls.append(
            (
                "upsert",
                {
                    "document": document,
                    "revision": revision,
                },
            )
        )

        return SimpleNamespace(
            status=SimpleNamespace(value="created"),
            page=SimpleNamespace(id="database-page-id"),
            revision=self.persistence_revision,
        )

    async def replace_chunks(
        self,
        *,
        revision: object,
        chunks: object,
    ) -> list[object]:
        self.calls.append(
            (
                "replace_chunks",
                {
                    "revision": revision,
                    "chunks": chunks,
                },
            )
        )
        return []


@pytest.mark.asyncio
async def test_default_pipeline_builds_and_persists_chunks() -> None:
    document = KnowledgeDocument(
        id="10",
        title="פתיחת סניף",
        canonical_url=(
            "https://wiki.example.test/"
            "%D7%A4%D7%AA%D7%99%D7%97%D7%AA_%D7%A1%D7%A0%D7%99%D7%A3"
        ),
        latest_revision_id="20",
    )
    revision = KnowledgeDocumentRevision(
        id="20",
        document_id="10",
        timestamp=datetime(2026, 7, 24, tzinfo=UTC),
        raw_content=(
            "טקסט פתיחה.\n\n"
            "== קופה ==\n"
            "בדיקת קופה.\n\n"
            "=== חריגים ===\n"
            "דיווח למנהל."
        ),
    )

    source = FakeKnowledgeSource(revision)
    repository = FakeDocumentRepository()

    pipeline = build_default_sync_pipeline(
        source=cast(Any, source),
        documents=cast(Any, repository),
    )

    state = await pipeline.run(document)

    assert source.requested_revision_ids == ["20"]
    assert state.revision is revision

    assert [chunk.heading_path for chunk in state.chunks] == [
        (),
        ("קופה",),
        ("קופה", "חריגים"),
    ]
    assert [chunk.content for chunk in state.chunks] == [
        "טקסט פתיחה.",
        "בדיקת קופה.",
        "דיווח למנהל.",
    ]

    assert [name for name, _ in repository.calls] == [
        "upsert",
        "replace_chunks",
    ]

    upsert_call = cast(dict[str, object], repository.calls[0][1])
    assert upsert_call == {
        "document": document,
        "revision": revision,
    }

    replace_call = cast(dict[str, object], repository.calls[1][1])
    assert replace_call["revision"] is repository.persistence_revision
    assert replace_call["chunks"] == state.chunks


def test_default_pipeline_has_expected_step_order() -> None:
    revision = KnowledgeDocumentRevision(
        id="20",
        document_id="10",
        timestamp=datetime(2026, 7, 24, tzinfo=UTC),
        raw_content="",
    )

    pipeline = build_default_sync_pipeline(
        source=cast(Any, FakeKnowledgeSource(revision)),
        documents=cast(Any, FakeDocumentRepository()),
    )

    assert [type(step) for step in pipeline.steps] == [
        FetchRevisionStep,
        BuildChunksStep,
        PersistDocumentStep,
        PersistChunksStep,
    ]
