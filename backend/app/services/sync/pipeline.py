from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.services.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentRevision,
    KnowledgeSource,
)
from app.services.knowledge.persistence import (
    DocumentUpsertResult,
    KnowledgeDocumentRepository,
)


@dataclass(slots=True)
class SyncPageState:
    """
    Mutable state passed between pipeline steps for one knowledge page.

    Every step may enrich the state without knowing how the other steps
    are implemented.
    """

    document: KnowledgeDocument
    revision: KnowledgeDocumentRevision | None = None
    upsert_result: DocumentUpsertResult | None = None

    def require_revision(self) -> KnowledgeDocumentRevision:
        """Return the fetched revision or fail with a clear pipeline error."""

        if self.revision is None:
            raise RuntimeError(
                "sync pipeline state does not contain a revision"
            )

        return self.revision

    def require_upsert_result(self) -> DocumentUpsertResult:
        """Return the persistence result or fail with a clear pipeline error."""

        if self.upsert_result is None:
            raise RuntimeError(
                "sync pipeline state does not contain an upsert result"
            )

        return self.upsert_result


@runtime_checkable
class SyncPipelineStep(Protocol):
    """One independently testable operation in the page sync pipeline."""

    async def execute(self, state: SyncPageState) -> None:
        """Process and optionally enrich one page state."""
        ...


class FetchRevisionStep:
    """Fetch the latest immutable revision for one knowledge document."""

    def __init__(self, source: KnowledgeSource) -> None:
        self._source = source

    async def execute(self, state: SyncPageState) -> None:
        revision_id = state.document.latest_revision_id

        if revision_id is None or not revision_id.strip():
            raise ValueError(
                "document.latest_revision_id is required for sync"
            )

        state.revision = await self._source.get_revision(revision_id)


class PersistDocumentStep:
    """Persist the fetched document aggregate."""

    def __init__(
        self,
        repository: KnowledgeDocumentRepository,
    ) -> None:
        self._repository = repository

    async def execute(self, state: SyncPageState) -> None:
        revision = state.require_revision()

        state.upsert_result = await self._repository.upsert(
            document=state.document,
            revision=revision,
        )


class SyncPipeline:
    """Execute an ordered collection of page-processing steps."""

    def __init__(
        self,
        steps: Sequence[SyncPipelineStep],
    ) -> None:
        if not steps:
            raise ValueError(
                "sync pipeline must contain at least one step"
            )

        self._steps = tuple(steps)

    @property
    def steps(self) -> tuple[SyncPipelineStep, ...]:
        """Return the immutable ordered pipeline definition."""

        return self._steps

    async def run(
        self,
        document: KnowledgeDocument,
    ) -> SyncPageState:
        """Run every configured step for one knowledge document."""

        state = SyncPageState(document=document)

        for step in self._steps:
            await step.execute(state)

        return state


def build_default_sync_pipeline(
    *,
    source: KnowledgeSource,
    documents: KnowledgeDocumentRepository,
) -> SyncPipeline:
    """Build the default fetch-and-persist pipeline."""

    return SyncPipeline(
        steps=(
            FetchRevisionStep(source),
            PersistDocumentStep(documents),
        )
    )
