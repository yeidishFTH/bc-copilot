# ADR 0002 — Only Sync Service Accesses MediaWiki

## Status

Accepted

## Decision

No frontend, search, AI, or general API component may communicate directly with MediaWiki.

## Consequences

- MediaWiki credentials remain isolated;
- indexing is deterministic;
- search stays available independently of Wiki latency;
- additional sources can later enter the same Knowledge Pipeline.
