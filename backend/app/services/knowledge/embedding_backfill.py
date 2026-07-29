from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.services.knowledge.embeddings import (
    EmbeddingGenerator,
    EmbeddingVector,
)
from app.services.knowledge.persistence.repositories.embeddings import (
    KnowledgeEmbeddingCandidate,
)


@runtime_checkable
class EmbeddingBackfillRepository(Protocol):
    async def fetch_pending(
        self,
        *,
        limit: int,
    ) -> tuple[KnowledgeEmbeddingCandidate, ...]:
        ...

    async def store_embeddings(
        self,
        embeddings: dict[
            object,
            EmbeddingVector,
        ],
    ) -> int:
        ...


@runtime_checkable
class EmbeddingBackfillSession(Protocol):
    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


@dataclass(frozen=True, slots=True)
class EmbeddingBackfillResult:
    dry_run: bool
    processed: int
    stored: int
    batches: int
    remaining_limit: int | None


class EmbeddingTextBuilder:
    """
    Build stable embedding text from persisted knowledge context.

    The order is deliberate:
    page title, heading hierarchy, then chunk content.
    """

    @staticmethod
    def build(
        candidate: KnowledgeEmbeddingCandidate,
    ) -> str:
        sections: list[str] = []

        title = " ".join(candidate.title.split())

        if title:
            sections.append(title)

        heading_path = tuple(
            " ".join(heading.split())
            for heading in candidate.heading_path
            if " ".join(heading.split())
        )

        if heading_path:
            sections.append(" > ".join(heading_path))

        content = " ".join(
            candidate.content.split()
        )

        if content:
            sections.append(content)

        result = "\n\n".join(sections).strip()

        if not result:
            raise ValueError(
                "embedding candidate contains no usable text"
            )

        return result


class EmbeddingBackfillService:
    """
    Generate and persist embeddings in resumable committed batches.

    Each successful batch is committed independently. If generation or
    persistence fails, only the active batch is rolled back and the error
    is propagated to the caller.
    """

    DEFAULT_BATCH_SIZE = 50
    MAX_BATCH_SIZE = 500

    def __init__(
        self,
        *,
        repository: EmbeddingBackfillRepository,
        generator: EmbeddingGenerator,
        session: EmbeddingBackfillSession,
        text_builder: type[
            EmbeddingTextBuilder
        ] = EmbeddingTextBuilder,
    ) -> None:
        self._repository = repository
        self._generator = generator
        self._session = session
        self._text_builder = text_builder

    async def run(
        self,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> EmbeddingBackfillResult:
        normalized_batch_size = (
            self._normalize_batch_size(
                batch_size
            )
        )
        normalized_limit = self._normalize_limit(
            limit
        )

        processed = 0
        stored = 0
        batches = 0
        remaining_limit = normalized_limit

        while True:
            current_batch_size = (
                normalized_batch_size
                if remaining_limit is None
                else min(
                    normalized_batch_size,
                    remaining_limit,
                )
            )

            if current_batch_size == 0:
                break

            candidates = (
                await self._repository.fetch_pending(
                    limit=current_batch_size
                )
            )

            if not candidates:
                break

            texts = tuple(
                self._text_builder.build(candidate)
                for candidate in candidates
            )

            processed += len(candidates)
            batches += 1

            if dry_run:
                await self._session.rollback()
            else:
                try:
                    vectors = await self._generator.generate(
                        texts
                    )

                    if len(vectors) != len(candidates):
                        raise RuntimeError(
                            "embedding generator returned "
                            "an unexpected number of vectors"
                        )

                    embedding_map = {
                        candidate.chunk_id: vector
                        for candidate, vector in zip(
                            candidates,
                            vectors,
                            strict=True,
                        )
                    }

                    stored_in_batch = (
                        await self._repository.store_embeddings(
                            embedding_map
                        )
                    )

                    if stored_in_batch != len(candidates):
                        raise RuntimeError(
                            "embedding repository stored "
                            "an unexpected number of vectors"
                        )

                    await self._session.commit()
                    stored += stored_in_batch

                except Exception:
                    await self._session.rollback()
                    raise

            if remaining_limit is not None:
                remaining_limit -= len(candidates)

                if remaining_limit <= 0:
                    remaining_limit = 0
                    break

            if dry_run:
                break

        return EmbeddingBackfillResult(
            dry_run=dry_run,
            processed=processed,
            stored=stored,
            batches=batches,
            remaining_limit=remaining_limit,
        )

    @classmethod
    def _normalize_batch_size(
        cls,
        batch_size: int,
    ) -> int:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
        ):
            raise ValueError(
                "batch_size must be an integer"
            )

        if (
            batch_size < 1
            or batch_size > cls.MAX_BATCH_SIZE
        ):
            raise ValueError(
                "batch_size must be between "
                f"1 and {cls.MAX_BATCH_SIZE}"
            )

        return batch_size

    @staticmethod
    def _normalize_limit(
        limit: int | None,
    ) -> int | None:
        if limit is None:
            return None

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
        ):
            raise ValueError(
                "limit must be an integer or None"
            )

        if limit < 1:
            raise ValueError(
                "limit must be greater than zero"
            )

        return limit
