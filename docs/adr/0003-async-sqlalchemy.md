# ADR 0003 — Async SQLAlchemy

## Status

Accepted

## Decision

Use SQLAlchemy's asyncio integration with `asyncpg`.

## Consequences

- FastAPI routes can access PostgreSQL without blocking the event loop;
- migrations use Alembic with an async SQLAlchemy engine;
- database sessions are scoped per request.
