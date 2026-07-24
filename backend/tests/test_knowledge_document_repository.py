from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.sql.dml import Delete

from app.db.models import KnowledgeChunk, KnowledgeRevision
from app.services.knowledge import KnowledgeChunkDraft
from app.services.knowledge.persistence.repositories.documents import (
    KnowledgeDocumentRepository,
)


pytestmark = pytest.mark.asyncio


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.added_batches: list[list[Any]] = []
        self.flushes = 0

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    def add_all(self, instances: list[Any]) -> None:
        self.added_batches.append(instances)

    async def flush(self) -> None:
        self.flushes += 1


def make_revision() -> KnowledgeRevision:
    return KnowledgeRevision(
        id=uuid4(),
        page_id=uuid4(),
        wiki_revision_id=105,
        parent_revision_id=104,
        revision_timestamp=datetime(2026, 7, 24, tzinfo=UTC),
        author_name="Wiki User",
        comment="Updated",
        content_sha256="a" * 64,
    )


async def test_replace_chunks_deletes_existing_and_inserts_ordered_chunks() -> None:
    session = FakeSession()
    repository = KnowledgeDocumentRepository(session)  # type: ignore[arg-type]
    revision = make_revision()

    drafts = (
        KnowledgeChunkDraft(
            heading_path=("Introduction",),
            content="First chunk",
            token_count=2,
        ),
        KnowledgeChunkDraft(
            heading_path=("Operations", "Opening"),
            content="Second chunk",
            token_count=3,
        ),
    )

    result = await repository.replace_chunks(
        revision=revision,
        chunks=drafts,
    )

    assert len(session.executed) == 1
    statement = session.executed[0]

    assert isinstance(statement, Delete)
    assert statement.table.name == KnowledgeChunk.__tablename__

    assert session.flushes == 1
    assert len(session.added_batches) == 1
    assert session.added_batches[0] == result

    assert [chunk.position for chunk in result] == [0, 1]
    assert [chunk.content for chunk in result] == [
        "First chunk",
        "Second chunk",
    ]
    assert result[0].revision is revision
    assert result[1].revision is revision


async def test_replace_chunks_with_empty_sequence_only_deletes_existing() -> None:
    session = FakeSession()
    repository = KnowledgeDocumentRepository(session)  # type: ignore[arg-type]
    revision = make_revision()

    result = await repository.replace_chunks(
        revision=revision,
        chunks=(),
    )

    assert result == []
    assert len(session.executed) == 1
    assert session.added_batches == []
    assert session.flushes == 1


async def test_replace_chunks_rejects_revision_without_identifier() -> None:
    session = FakeSession()
    repository = KnowledgeDocumentRepository(session)  # type: ignore[arg-type]

    revision = KnowledgeRevision(
        page_id=uuid4(),
        wiki_revision_id=105,
        revision_timestamp=datetime(2026, 7, 24, tzinfo=UTC),
        content_sha256="a" * 64,
    )

    with pytest.raises(
        ValueError,
        match="revision.id is required before replacing chunks",
    ):
        await repository.replace_chunks(
            revision=revision,
            chunks=(),
        )

    assert session.executed == []
    assert session.added_batches == []
    assert session.flushes == 0
