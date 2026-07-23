# Release 0.2 Design

## Goal

Create a durable database and migration foundation for the Knowledge Engine.

## Update 2.1 scope

- PostgreSQL development service
- SQLAlchemy async access
- Alembic migrations
- first knowledge schema
- database health route
- backend integration tests
- CI
- update and rollback automation

## Out of scope

- MediaWiki authentication
- Wiki synchronization
- parsing
- search API
- frontend search integration

## Acceptance criteria

- PostgreSQL reaches healthy state.
- Alembic applies the initial migration.
- all expected tables exist.
- `/api/health` succeeds.
- `/api/health/database` succeeds while PostgreSQL is available.
- backend tests pass.
- secrets remain untracked.
- rollback can restore the pre-update source tree.
