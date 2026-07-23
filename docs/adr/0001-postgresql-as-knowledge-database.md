# ADR 0001 — PostgreSQL as the Knowledge Database

## Status

Accepted

## Decision

Use PostgreSQL as the durable Knowledge Engine database.

## Consequences

- supports relational metadata and revision history;
- supports native full-text search;
- supports trigram search;
- can later support vectors through an extension;
- requires managed migrations and operational backups.
