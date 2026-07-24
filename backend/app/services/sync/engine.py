from __future__ import annotations

from app.db.models import SyncMode, SyncRun, SyncStatus
from app.services.knowledge.models import KnowledgeDocument
from app.services.knowledge.persistence import DocumentUpsertStatus
from app.services.sync.exceptions import (
    SyncRunFinishError,
    SyncRunStartError,
)
from app.services.sync.models import (
    SyncContext,
    SyncCounters,
    SyncExecutionResult,
)
from app.services.sync.pipeline import (
    SyncPipeline,
    build_default_sync_pipeline,
)


class SyncEngine:
    """
    Orchestrate synchronization from a KnowledgeSource into persistence.

    Page-specific processing is delegated to SyncPipeline.

    Transaction boundaries:
    - Sync run creation is committed independently.
    - Every page is committed independently.
    - Failed pages are rolled back without affecting successful pages.
    - Final run status is committed independently.
    """

    def __init__(
        self,
        context: SyncContext,
        *,
        pipeline: SyncPipeline | None = None,
    ) -> None:
        self._context = context
        self._pipeline = pipeline or build_default_sync_pipeline(
            source=context.source,
            documents=context.documents,
        )

    async def full_sync(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> SyncExecutionResult:
        """Synchronize all pages returned by the configured source."""

        self._validate_arguments(
            namespace_id=namespace_id,
            limit=limit,
        )

        run = await self._start_run(SyncMode.full)
        counters = SyncCounters()

        final_status = SyncStatus.succeeded
        error_summary: str | None = None
        source_connected = False

        try:
            await self._context.source.connect()
            source_connected = True

            pages = await self._context.source.list_pages(
                namespace_id=namespace_id,
                limit=limit,
            )

            for document in pages:
                await self._sync_document(
                    run=run,
                    document=document,
                    counters=counters,
                )

            if counters.pages_failed > 0:
                final_status = SyncStatus.partial

        except Exception as error:
            await self._context.session.rollback()

            final_status = SyncStatus.failed
            error_summary = self._format_error(error)

        finally:
            if source_connected:
                try:
                    await self._context.source.close()
                except Exception as error:
                    close_error = self._format_error(error)

                    if error_summary:
                        error_summary = (
                            f"{error_summary}; source close failed: "
                            f"{close_error}"
                        )
                    else:
                        error_summary = (
                            f"source close failed: {close_error}"
                        )

                    final_status = SyncStatus.failed

        return await self._finish_run(
            run=run,
            status=final_status,
            counters=counters,
            error_summary=error_summary,
        )

    async def _sync_document(
        self,
        *,
        run: SyncRun,
        document: KnowledgeDocument,
        counters: SyncCounters,
    ) -> None:
        counters.pages_seen += 1

        try:
            state = await self._pipeline.run(document)

            revision = state.require_revision()
            result = state.require_upsert_result()

            self._increment_success_counter(
                counters,
                result.status,
            )

            await self._context.sync.record_event(
                run,
                status=result.status.value,
                wiki_page_id=self._parse_optional_integer(
                    document.id
                ),
                title=document.title,
                revision_id=self._parse_optional_integer(
                    revision.id
                ),
            )

            await self._context.session.commit()

        except Exception as error:
            await self._context.session.rollback()
            counters.pages_failed += 1

            await self._context.sync.record_event(
                run,
                status="failed",
                wiki_page_id=self._parse_optional_integer(
                    document.id
                ),
                title=document.title,
                revision_id=self._parse_optional_integer(
                    document.latest_revision_id
                ),
                message=self._format_error(error),
            )

            await self._context.session.commit()

    async def _start_run(
        self,
        mode: SyncMode,
    ) -> SyncRun:
        try:
            run = await self._context.sync.start(mode)
            await self._context.session.commit()
            return run
        except Exception as error:
            await self._context.session.rollback()
            raise SyncRunStartError(
                f"Could not start sync run: "
                f"{self._format_error(error)}"
            ) from error

    async def _finish_run(
        self,
        *,
        run: SyncRun,
        status: SyncStatus,
        counters: SyncCounters,
        error_summary: str | None,
    ) -> SyncExecutionResult:
        try:
            finished_run = await self._context.sync.finish(
                run,
                status=status,
                pages_seen=counters.pages_seen,
                pages_created=counters.pages_created,
                pages_updated=counters.pages_updated,
                pages_unchanged=counters.pages_unchanged,
                pages_failed=counters.pages_failed,
                error_summary=error_summary,
            )

            await self._context.session.commit()

        except Exception as error:
            await self._context.session.rollback()
            raise SyncRunFinishError(
                f"Could not finish sync run: "
                f"{self._format_error(error)}"
            ) from error

        return SyncExecutionResult(
            run_id=finished_run.id,
            status=finished_run.status,
            pages_seen=finished_run.pages_seen,
            pages_created=finished_run.pages_created,
            pages_updated=finished_run.pages_updated,
            pages_unchanged=finished_run.pages_unchanged,
            pages_failed=finished_run.pages_failed,
            error_summary=finished_run.error_summary,
        )

    @staticmethod
    def _increment_success_counter(
        counters: SyncCounters,
        status: DocumentUpsertStatus,
    ) -> None:
        if status is DocumentUpsertStatus.created:
            counters.pages_created += 1
            return

        if status is DocumentUpsertStatus.updated:
            counters.pages_updated += 1
            return

        if status is DocumentUpsertStatus.unchanged:
            counters.pages_unchanged += 1
            return

        raise ValueError(
            f"Unsupported document upsert status: {status!r}"
        )

    @staticmethod
    def _validate_arguments(
        *,
        namespace_id: int,
        limit: int | None,
    ) -> None:
        if isinstance(namespace_id, bool) or not isinstance(
            namespace_id,
            int,
        ):
            raise ValueError("namespace_id must be an integer")

        if limit is not None:
            if (
                isinstance(limit, bool)
                or not isinstance(limit, int)
                or limit < 1
            ):
                raise ValueError(
                    "limit must be a positive integer or None"
                )

    @staticmethod
    def _parse_optional_integer(
        value: str | int | None,
    ) -> int | None:
        if value is None or isinstance(value, bool):
            return None

        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None

        return parsed if parsed > 0 else None

    @staticmethod
    def _format_error(error: Exception) -> str:
        message = str(error).strip()

        if message:
            return f"{type(error).__name__}: {message}"

        return type(error).__name__
