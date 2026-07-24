from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    SyncMode,
    SyncPageEvent,
    SyncRun,
    SyncStatus,
)


class SyncRepository:
    """Persist sync runs and their page-level events without committing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(
        self,
        mode: SyncMode,
    ) -> SyncRun:
        if not isinstance(mode, SyncMode):
            raise ValueError("mode must be a SyncMode value")

        run = SyncRun(
            status=SyncStatus.running,
            mode=mode,
            pages_seen=0,
            pages_created=0,
            pages_updated=0,
            pages_unchanged=0,
            pages_failed=0,
        )

        self._session.add(run)
        await self._session.flush()

        return run

    async def record_event(
        self,
        run: SyncRun,
        *,
        status: str,
        wiki_page_id: int | None = None,
        title: str | None = None,
        revision_id: int | None = None,
        message: str | None = None,
    ) -> SyncPageEvent:
        normalized_status = status.strip()

        if not normalized_status:
            raise ValueError("status cannot be empty")

        if len(normalized_status) > 32:
            raise ValueError("status cannot exceed 32 characters")

        event = SyncPageEvent(
            sync_run_id=run.id,
            wiki_page_id=wiki_page_id,
            title=title,
            status=normalized_status,
            revision_id=revision_id,
            message=message,
        )

        self._session.add(event)
        await self._session.flush()

        return event

    async def finish(
        self,
        run: SyncRun,
        *,
        status: SyncStatus,
        pages_seen: int,
        pages_created: int,
        pages_updated: int,
        pages_unchanged: int,
        pages_failed: int,
        error_summary: str | None = None,
    ) -> SyncRun:
        if status is SyncStatus.running:
            raise ValueError("a finished sync run cannot remain running")

        if not isinstance(status, SyncStatus):
            raise ValueError("status must be a SyncStatus value")

        counters = {
            "pages_seen": pages_seen,
            "pages_created": pages_created,
            "pages_updated": pages_updated,
            "pages_unchanged": pages_unchanged,
            "pages_failed": pages_failed,
        }

        for field_name, value in counters.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"{field_name} must be a non-negative integer"
                )

        accounted_pages = (
            pages_created
            + pages_updated
            + pages_unchanged
            + pages_failed
        )

        if accounted_pages != pages_seen:
            raise ValueError(
                "page outcome counters must add up to pages_seen"
            )

        run.status = status
        run.finished_at = datetime.now(UTC)
        run.pages_seen = pages_seen
        run.pages_created = pages_created
        run.pages_updated = pages_updated
        run.pages_unchanged = pages_unchanged
        run.pages_failed = pages_failed
        run.error_summary = error_summary

        await self._session.flush()

        return run
