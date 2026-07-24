from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.db.models import SyncMode, SyncStatus
from app.services.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
)
from app.services.knowledge.persistence import (
    DocumentUpsertStatus,
)
from app.services.sync import SyncContext, SyncEngine


pytestmark = pytest.mark.asyncio


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeSource:
    source_name = "fake"

    def __init__(
        self,
        pages: list[KnowledgeDocument],
        revisions: dict[str, KnowledgeDocumentRevision],
        *,
        list_error: Exception | None = None,
    ) -> None:
        self.pages = pages
        self.revisions = revisions
        self.list_error = list_error
        self.connected = False
        self.closed = False
        self.requested_revisions: list[str] = []

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def health(self) -> bool:
        return True

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> list[KnowledgeDocument]:
        if self.list_error is not None:
            raise self.list_error

        pages = [
            page
            for page in self.pages
            if page.namespace_id == namespace_id
        ]

        if limit is not None:
            return pages[:limit]

        return pages

    async def get_page(
        self,
        identifier: str,
    ) -> KnowledgeDocument:
        raise NotImplementedError

    async def get_revision(
        self,
        revision_id: str,
    ) -> KnowledgeDocumentRevision:
        self.requested_revisions.append(revision_id)
        return self.revisions[revision_id]

    async def get_categories(
        self,
        page_identifier: str,
    ) -> list[Any]:
        return []


class FakeDocumentRepository:
    def __init__(
        self,
        statuses: dict[str, DocumentUpsertStatus],
        *,
        failures: dict[str, Exception] | None = None,
    ) -> None:
        self.statuses = statuses
        self.failures = failures or {}
        self.calls: list[str] = []

    async def upsert(
        self,
        *,
        document: KnowledgeDocument,
        revision: KnowledgeDocumentRevision,
    ) -> Any:
        self.calls.append(document.id)

        if document.id in self.failures:
            raise self.failures[document.id]

        return SimpleNamespace(
            status=self.statuses[document.id],
            revision=SimpleNamespace(
                id=f"revision-{document.id}"
            ),
        )

    async def replace_chunks(
        self,
        *,
        revision: Any,
        chunks: Any,
    ) -> list[Any]:
        return []


class FakeSyncRepository:
    def __init__(self) -> None:
        self.run = SimpleNamespace(
            id=uuid4(),
            status=SyncStatus.running,
            pages_seen=0,
            pages_created=0,
            pages_updated=0,
            pages_unchanged=0,
            pages_failed=0,
            error_summary=None,
        )
        self.started_modes: list[SyncMode] = []
        self.events: list[dict[str, Any]] = []
        self.finish_arguments: dict[str, Any] | None = None

    async def start(self, mode: SyncMode) -> Any:
        self.started_modes.append(mode)
        return self.run

    async def record_event(
        self,
        run: Any,
        **values: Any,
    ) -> Any:
        self.events.append(values)
        return SimpleNamespace(**values)

    async def finish(
        self,
        run: Any,
        **values: Any,
    ) -> Any:
        self.finish_arguments = values

        for key, value in values.items():
            setattr(run, key, value)

        return run


def make_page(
    page_id: int,
    revision_id: int,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=str(page_id),
        title=f"Page {page_id}",
        canonical_url=f"https://wiki.test/{page_id}",
        latest_revision_id=str(revision_id),
    )


def make_revision(
    page_id: int,
    revision_id: int,
) -> KnowledgeDocumentRevision:
    return KnowledgeDocumentRevision(
        id=str(revision_id),
        document_id=str(page_id),
        timestamp=datetime(2026, 7, 24, tzinfo=UTC),
        raw_content=f"Content {page_id}",
    )


async def test_full_sync_persists_successful_pages() -> None:
    pages = [
        make_page(1, 101),
        make_page(2, 102),
        make_page(3, 103),
    ]
    revisions = {
        "101": make_revision(1, 101),
        "102": make_revision(2, 102),
        "103": make_revision(3, 103),
    }

    source = FakeSource(pages, revisions)
    documents = FakeDocumentRepository(
        {
            "1": DocumentUpsertStatus.created,
            "2": DocumentUpsertStatus.updated,
            "3": DocumentUpsertStatus.unchanged,
        }
    )
    sync = FakeSyncRepository()
    session = FakeSession()

    engine = SyncEngine(
        SyncContext(
            source=source,
            documents=documents,  # type: ignore[arg-type]
            sync=sync,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )
    )

    result = await engine.full_sync()

    assert result.status is SyncStatus.succeeded
    assert result.pages_seen == 3
    assert result.pages_created == 1
    assert result.pages_updated == 1
    assert result.pages_unchanged == 1
    assert result.pages_failed == 0

    assert source.connected is True
    assert source.closed is True
    assert source.requested_revisions == ["101", "102", "103"]

    assert [event["status"] for event in sync.events] == [
        "created",
        "updated",
        "unchanged",
    ]

    assert session.commits == 5
    assert session.rollbacks == 0


async def test_full_sync_continues_after_page_failure() -> None:
    pages = [
        make_page(1, 101),
        make_page(2, 102),
    ]
    revisions = {
        "101": make_revision(1, 101),
        "102": make_revision(2, 102),
    }

    source = FakeSource(pages, revisions)
    documents = FakeDocumentRepository(
        {
            "1": DocumentUpsertStatus.created,
            "2": DocumentUpsertStatus.updated,
        },
        failures={
            "2": RuntimeError("database write failed"),
        },
    )
    sync = FakeSyncRepository()
    session = FakeSession()

    engine = SyncEngine(
        SyncContext(
            source=source,
            documents=documents,  # type: ignore[arg-type]
            sync=sync,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )
    )

    result = await engine.full_sync()

    assert result.status is SyncStatus.partial
    assert result.pages_seen == 2
    assert result.pages_created == 1
    assert result.pages_updated == 0
    assert result.pages_unchanged == 0
    assert result.pages_failed == 1

    assert sync.events[0]["status"] == "created"
    assert sync.events[1]["status"] == "failed"
    assert (
        sync.events[1]["message"]
        == "RuntimeError: database write failed"
    )

    assert session.rollbacks == 1


async def test_full_sync_marks_fatal_source_failure() -> None:
    source = FakeSource(
        [],
        {},
        list_error=RuntimeError("source unavailable"),
    )
    documents = FakeDocumentRepository({})
    sync = FakeSyncRepository()
    session = FakeSession()

    engine = SyncEngine(
        SyncContext(
            source=source,
            documents=documents,  # type: ignore[arg-type]
            sync=sync,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )
    )

    result = await engine.full_sync()

    assert result.status is SyncStatus.failed
    assert result.pages_seen == 0
    assert result.pages_failed == 0
    assert (
        result.error_summary
        == "RuntimeError: source unavailable"
    )

    assert source.connected is True
    assert source.closed is True
    assert session.rollbacks == 1


async def test_full_sync_rejects_invalid_limit() -> None:
    source = FakeSource([], {})
    documents = FakeDocumentRepository({})
    sync = FakeSyncRepository()
    session = FakeSession()

    engine = SyncEngine(
        SyncContext(
            source=source,
            documents=documents,  # type: ignore[arg-type]
            sync=sync,  # type: ignore[arg-type]
            session=session,  # type: ignore[arg-type]
        )
    )

    with pytest.raises(
        ValueError,
        match="limit must be a positive integer or None",
    ):
        await engine.full_sync(limit=0)

    assert sync.started_modes == []
    assert session.commits == 0
