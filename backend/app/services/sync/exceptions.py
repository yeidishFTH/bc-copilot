from __future__ import annotations


class SyncEngineError(Exception):
    """Base exception for sync orchestration failures."""


class SyncRunStartError(SyncEngineError):
    """Raised when a sync run cannot be created in persistence."""


class SyncRunFinishError(SyncEngineError):
    """Raised when the final sync state cannot be persisted."""
