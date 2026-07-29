from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import pytest

from app.services.knowledge import (
    DeterministicEmbeddingGenerator,
    EmbeddingVector,
)
from app.services.knowledge.embedding_backfill import (
    EmbeddingBackfillService,
    EmbeddingTextBuilder,
)
from app.services.knowledge.persistence import (
    KnowledgeEmbeddingCandidate,
)


def candidate(
    *,
    title: str = "נוהל מחיקת כרטיס לקוח",
    heading_path: tuple[str, ...] = (
        "שלבי ביצוע",
        "מחיקה",
    ),
    content: str = "יש לאתר את כרטיס הלקוח.",
    position: int = 0,
) -> KnowledgeEmbeddingCandidate:
    return KnowledgeEmbeddingCandidate(
        chunk_id=uuid.uuid4(),
        title=title,
        heading_path=heading_path,
        content=content,
        position=position,
    )


class FakeRepository:
    def __init__(
        self,
        batches: Sequence[
            Sequence[KnowledgeEmbeddingCandidate]
        ],
    ) -> None:
        self._batches = [
            tuple(batch)
            for batch in batches
        ]
        self.fetch_limits: list[int] = []
        self.stored: list[
            dict[object, EmbeddingVector]
        ] = []

    async def fetch_pending(
        self,
        *,
        limit: int,
    ) -> tuple[
        KnowledgeEmbeddingCandidate,
        ...,
    ]:
        self.fetch_limits.append(limit)

        if not self._batches:
            return ()

        batch = self._batches.pop(0)

        return batch[:limit]

    async def store_embeddings(
        self,
        embeddings: dict[
            object,
            EmbeddingVector,
        ],
    ) -> int:
        self.stored.append(dict(embeddings))
        return len(embeddings)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class RecordingGenerator:
    model_id = "recording"
    dimensions = 1536

    def __init__(self) -> None:
        self.calls: list[
            tuple[str, ...]
        ] = []

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        normalized = tuple(texts)
        self.calls.append(normalized)

        return tuple(
            EmbeddingVector(
                tuple(
                    float(index + 1)
                    for _ in range(1536)
                )
            )
            for index, _ in enumerate(normalized)
        )


class FailingGenerator:
    model_id = "failing"
    dimensions = 1536

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        del texts
        raise RuntimeError("generation failed")


def test_text_builder_combines_context() -> None:
    text = EmbeddingTextBuilder.build(
        candidate()
    )

    assert text == (
        "נוהל מחיקת כרטיס לקוח\n\n"
        "שלבי ביצוע > מחיקה\n\n"
        "יש לאתר את כרטיס הלקוח."
    )


def test_text_builder_normalizes_whitespace() -> None:
    text = EmbeddingTextBuilder.build(
        candidate(
            title="  נוהל   לקוח ",
            heading_path=(
                " שלב   ראשון ",
                " ",
            ),
            content="  תוכן   המסמך ",
        )
    )

    assert text == (
        "נוהל לקוח\n\n"
        "שלב ראשון\n\n"
        "תוכן המסמך"
    )


def test_text_builder_rejects_empty_candidate() -> None:
    with pytest.raises(
        ValueError,
        match="no usable text",
    ):
        EmbeddingTextBuilder.build(
            candidate(
                title=" ",
                heading_path=(),
                content=" ",
            )
        )


@pytest.mark.asyncio
async def test_run_processes_and_commits_batches() -> None:
    first = candidate(position=0)
    second = candidate(position=1)
    third = candidate(position=2)

    repository = FakeRepository(
        [
            (first, second),
            (third,),
            (),
        ]
    )
    session = FakeSession()
    generator = RecordingGenerator()

    service = EmbeddingBackfillService(
        repository=repository,
        generator=generator,
        session=session,
    )

    result = await service.run(
        batch_size=2
    )

    assert result.dry_run is False
    assert result.processed == 3
    assert result.stored == 3
    assert result.batches == 2
    assert result.remaining_limit is None

    assert repository.fetch_limits == [
        2,
        2,
        2,
    ]
    assert session.commits == 2
    assert session.rollbacks == 0
    assert len(repository.stored) == 2
    assert len(generator.calls) == 2


@pytest.mark.asyncio
async def test_run_respects_limit() -> None:
    items = tuple(
        candidate(position=index)
        for index in range(4)
    )

    repository = FakeRepository(
        [
            items[:2],
            items[2:3],
        ]
    )
    session = FakeSession()
    generator = RecordingGenerator()

    service = EmbeddingBackfillService(
        repository=repository,
        generator=generator,
        session=session,
    )

    result = await service.run(
        batch_size=2,
        limit=3,
    )

    assert result.processed == 3
    assert result.stored == 3
    assert result.batches == 2
    assert result.remaining_limit == 0
    assert repository.fetch_limits == [
        2,
        1,
    ]


@pytest.mark.asyncio
async def test_dry_run_does_not_generate_or_store() -> None:
    item = candidate()
    repository = FakeRepository(
        [(item,)]
    )
    session = FakeSession()
    generator = RecordingGenerator()

    service = EmbeddingBackfillService(
        repository=repository,
        generator=generator,
        session=session,
    )

    result = await service.run(
        dry_run=True
    )

    assert result.dry_run is True
    assert result.processed == 1
    assert result.stored == 0
    assert result.batches == 1
    assert generator.calls == []
    assert repository.stored == []
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_generation_failure_rolls_back() -> None:
    repository = FakeRepository(
        [(candidate(),)]
    )
    session = FakeSession()

    service = EmbeddingBackfillService(
        repository=repository,
        generator=FailingGenerator(),
        session=session,
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        await service.run()

    assert session.commits == 0
    assert session.rollbacks == 1
    assert repository.stored == []


@pytest.mark.asyncio
async def test_empty_repository_returns_empty_result() -> None:
    repository = FakeRepository([()])
    session = FakeSession()

    service = EmbeddingBackfillService(
        repository=repository,
        generator=(
            DeterministicEmbeddingGenerator(
                dimensions=1536
            )
        ),
        session=session,
    )

    result = await service.run()

    assert result.processed == 0
    assert result.stored == 0
    assert result.batches == 0
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.parametrize(
    "batch_size",
    [
        0,
        501,
        True,
        1.5,
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_batch_size(
    batch_size: Any,
) -> None:
    service = EmbeddingBackfillService(
        repository=FakeRepository([()]),
        generator=RecordingGenerator(),
        session=FakeSession(),
    )

    with pytest.raises(
        ValueError,
        match="batch_size",
    ):
        await service.run(
            batch_size=batch_size
        )


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        True,
        1.5,
    ],
)
@pytest.mark.asyncio
async def test_rejects_invalid_limit(
    limit: Any,
) -> None:
    service = EmbeddingBackfillService(
        repository=FakeRepository([()]),
        generator=RecordingGenerator(),
        session=FakeSession(),
    )

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        await service.run(limit=limit)
