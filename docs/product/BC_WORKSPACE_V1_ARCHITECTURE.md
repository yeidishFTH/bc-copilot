# BC Workspace v1.0 — Product and Architecture Blueprint

**Organization:** Bitcoin Change
**Product:** BC Workspace
**Initial module:** Knowledge Copilot
**Status:** Internal MVP moving toward production
**Primary language:** Hebrew
**Document purpose:** Define the approved architecture, scope, deployment model, security boundaries, rollout plan, and acceptance criteria for BC Workspace v1.0.

---

## 1. Executive Summary

BC Workspace is an internal work assistant for Bitcoin Change employees.

Its first production capability is the **Knowledge Copilot**: an assistant that allows employees to ask operational questions in natural Hebrew and receive grounded answers based on the official Bitcoin Change MediaWiki knowledge base.

The product is available through a browser extension that accompanies the employee across approved work systems. The employee does not need to leave Salesforce, the Wiki, Gmail, or another operational system to search manually for procedures.

The intended interaction is:

```text
Employee
  ↓
Asks an operational question
  ↓
BC Workspace understands the intent
  ↓
Searches official organizational knowledge
  ↓
Generates a grounded answer
  ↓
Shows the supporting Wiki sources
```

BC Workspace is not intended to replace MediaWiki. MediaWiki remains the authoritative source of organizational knowledge.

---

## 2. Business Problem

Employees move between several websites and systems during a shift.

Operational knowledge is distributed across:

- MediaWiki procedures
- guides
- checklists
- training pages
- system documentation
- compliance instructions
- organizational knowledge

The current process requires employees to:

1. remember that a relevant document exists;
2. know where it is located;
3. search using the correct terminology;
4. identify the authoritative page;
5. read and interpret the relevant section.

This creates:

- wasted operational time;
- dependence on experienced employees and managers;
- inconsistent answers;
- onboarding difficulty;
- increased compliance risk;
- repeated questions;
- low utilization of the Wiki.

BC Workspace reduces this friction by bringing the knowledge layer directly into the employee’s active work page.

---

## 3. Product Vision

The long-term vision is:

> BC Workspace will become the operational workspace through which Bitcoin Change employees access knowledge, guidance, checklists, training, and approved AI-assisted actions.

### Version 1.0 — Knowledge assistant

- ask questions;
- receive grounded answers;
- view official sources;
- open the relevant Wiki page;
- access the assistant from the browser extension.

### Version 1.5 — Personal work experience

- conversation history;
- recent searches;
- favorites;
- feedback;
- suggested questions;
- knowledge updates.

### Version 2.0 — Guided operational actions

- interactive checklists;
- employee onboarding flows;
- branch-opening workflows;
- shift procedures;
- training plans;
- approved templates.

### Version 3.0 — Integrated operational workspace

- system-aware assistance;
- approved automations;
- task status;
- organizational memory;
- controlled integrations with company systems.

---

## 4. Current Verified State

The project has passed the proof-of-concept stage.

### 4.1 Backend

The backend is implemented with FastAPI.

Verified capabilities include:

- health endpoints;
- database health checks;
- knowledge search;
- Copilot answer endpoint;
- Copilot streaming endpoint;
- OpenAI integration;
- PostgreSQL persistence;
- MediaWiki API integration.

Primary endpoints include:

```text
GET  /api/health
GET  /api/health/database
POST /api/knowledge/search
POST /api/copilot/ask
POST /api/copilot/ask/stream
```

### 4.2 Knowledge ingestion

The system can retrieve and persist MediaWiki content.

Existing components include:

- MediaWiki authentication;
- MediaWiki API client;
- page repositories;
- revision repositories;
- page and revision mapping;
- Wiki parsing;
- metadata parsing;
- content cleaning;
- chunk construction;
- synchronization CLI.

### 4.3 Retrieval stack

The retrieval system includes:

- lexical retrieval;
- semantic retrieval;
- pgvector search;
- hybrid retrieval;
- reciprocal rank fusion;
- multi-query retrieval;
- query rewriting;
- entity detection;
- alias expansion;
- document-title detection;
- authority scoring;
- document-type scoring;
- exact-title scoring;
- intent-aware title ranking.

### 4.4 Embeddings

The project includes:

- OpenAI embedding generation;
- configurable embedding model;
- configurable vector dimensions;
- resumable embedding backfill;
- dry-run mode;
- batch processing;
- PostgreSQL vector storage;
- exclusion of Archive, Sandbox, and redirect content.

The verified local database state contained:

```text
Total knowledge chunks: 291
Valid embedded chunks: 250
Embedding dimensions: 1536
```

### 4.5 Retrieval evaluation

A Golden Dataset containing 50 organizational questions is implemented.

Latest verified lexical retrieval result:

```text
Top-1 accuracy:           100%
Top-3 accuracy:           100%
Top-5 accuracy:           100%
Preferred Top-1 accuracy: 100%
```

The complete backend test suite passed:

```text
680 tests passed
```

This result validates document retrieval for the current evaluation set. It does not yet prove that every generated answer is complete, safe, or fully faithful.

### 4.6 Frontend

The frontend is implemented with Next.js.

Existing functionality includes:

- question input;
- suggested questions;
- grounded answers;
- Markdown rendering;
- source presentation;
- connection to the FastAPI backend.

### 4.7 Browser extension

A Chrome Manifest V3 extension MVP exists.

Current capabilities include:

- extension action;
- Chrome Side Panel;
- floating button injected into web pages;
- expandable in-page panel;
- isolated styling;
- iframe loading of the existing frontend;
- availability across normal HTTP and HTTPS pages.

The extension currently points to local services and therefore is not yet production-ready.

---

## 5. Product Boundaries

### 5.1 MediaWiki is authoritative

The authoritative source remains:

```text
https://wiki.bitcoinchange.co.il
```

BC Workspace must not silently override or replace official Wiki content.

Answers should be treated as an accessible representation of the source, not as a new independent policy.

### 5.2 Retrieval and answer generation are separate quality layers

The following questions must be evaluated separately:

1. Was the correct document retrieved?
2. Was the correct section retrieved?
3. Was the answer grounded in the source?
4. Were all mandatory steps included?
5. Was unsupported information introduced?
6. Were citations and links correct?

The existing 100% benchmark verifies the first layer for the current dataset.

### 5.3 Initial release is read-only

Version 1.0 must remain read-only regarding operational systems.

It may:

- answer;
- search;
- summarize;
- link;
- recommend an official procedure.

It must not automatically:

- modify Salesforce records;
- send email;
- send WhatsApp messages;
- change Wiki content;
- approve compliance cases;
- perform financial transactions.

Actions may be added only through separate approval-controlled development phases.

---

## 6. Recommended Production Architecture

```text
Employee Browser
│
├── BC Workspace Chrome Extension
│   ├── Floating Button
│   ├── Expandable Workspace Panel
│   ├── User Session
│   └── Approved Page Context
│
└── HTTPS
    │
    ▼
Reverse Proxy
│
├── Frontend Service — Next.js
├── Backend Service — FastAPI
└── Internal Network
    ├── PostgreSQL + pgvector
    ├── Background Sync Worker
    └── Scheduled Backup Worker
```

### 6.1 Recommended infrastructure

Initial production deployment:

- Ubuntu VPS;
- Docker Engine;
- Docker Compose;
- Caddy or Nginx;
- managed DNS;
- HTTPS;
- encrypted backups.

Suggested public address:

```text
https://copilot.bitcoinchange.co.il
```

The public hostname can later be routed behind the Wiki domain if server access permits.

### 6.2 Services

Recommended Compose services:

```text
bc-workspace-frontend
bc-workspace-backend
bc-workspace-postgres
bc-workspace-sync
bc-workspace-proxy
```

Optional later services:

```text
bc-workspace-worker
bc-workspace-monitoring
bc-workspace-analytics
```

### 6.3 Network exposure

Only the reverse proxy should be publicly exposed.

```text
Public:
80 / 443

Private:
Frontend port
Backend port
PostgreSQL port
Worker communication
```

PostgreSQL must never be exposed directly to the public internet.

---

## 7. Environment Separation

The project should use three environments.

### Local

Purpose:

- active development;
- testing;
- experimentation.

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
Database: localhost:5432
```

### Staging

Purpose:

- realistic deployment testing;
- internal QA;
- extension testing;
- synchronization validation.

```text
https://staging-copilot.bitcoinchange.co.il
```

### Production

Purpose:

- approved employee use.

```text
https://copilot.bitcoinchange.co.il
```

Production data and credentials must not be reused for local development unless explicitly authorized.

---

## 8. Authentication

Version 1.0 requires authentication before organizational rollout.

### Initial acceptable solution

A controlled internal user database with:

- email;
- display name;
- password hash;
- role;
- active status;
- optional branch;
- optional department.

### Preferred long-term solution

SSO through the company identity provider, such as:

- Google Workspace;
- Microsoft Entra ID;
- another approved organizational provider.

### Session requirements

- secure HTTP-only cookies;
- HTTPS only;
- session expiration;
- logout;
- account disabling;
- server-side authorization;
- CSRF protection where relevant;
- brute-force protection;
- audit logging for authentication failures.

The Chrome extension must not store raw passwords or long-lived API secrets.

---

## 9. Authorization and Document Access

Authentication answers:

> Who is the user?

Authorization answers:

> What may the user access?

Suggested access model:

```text
all_employees
representatives
branch_managers
regional_managers
back_office
compliance
human_resources
marketing
senior_management
administrators
```

Each page or chunk should eventually support access metadata.

Example:

```yaml
visibility:
  - all_employees

allowed_roles:
  - representatives
  - branch_managers

allowed_departments:
  - operations
```

Retrieval filtering must occur before results are returned to the answer generator.

It is not sufficient to hide restricted sources only in the frontend.

---

## 10. MediaWiki Synchronization

The production system must synchronize automatically.

```text
Scheduled job
  ↓
Authenticate with MediaWiki API
  ↓
Identify changed pages and revisions
  ↓
Fetch authoritative content
  ↓
Parse metadata
  ↓
Clean Wikitext
  ↓
Create chunks
  ↓
Persist current revision
  ↓
Generate missing embeddings
  ↓
Mark synchronization result
```

Recommended initial frequency:

```text
Every 10–15 minutes
```

Each run should record:

- start time;
- finish time;
- pages checked;
- pages changed;
- chunks created;
- chunks removed;
- embeddings generated;
- failures;
- retry count;
- final status.

If one page fails:

- the full sync should not necessarily fail;
- the previous valid revision must remain available;
- the failed page should be logged;
- the system should retry;
- administrators should be alerted after repeated failure.

---

## 11. Embedding Lifecycle

When an active page changes:

1. fetch the new revision;
2. parse and chunk it;
3. create embeddings for new chunks;
4. activate the new revision only after successful processing;
5. retire the previous revision from active retrieval;
6. retain history according to the retention policy.

Excluded content should include:

- Archive pages;
- Sandbox pages;
- redirects;
- inactive pages;
- obsolete revisions.

Embedding configuration must remain centralized:

```text
model
dimensions
batch size
provider
version
```

Changing the embedding model or dimensions requires a controlled re-indexing process.

---

## 12. Answer Safety

The assistant must prioritize correctness over fluency.

The answer should:

- rely on retrieved organizational sources;
- show the source title;
- link to the Wiki page;
- clearly separate policy from general explanation;
- state when the source is insufficient;
- avoid inventing steps, limits, permissions, or approvals;
- recommend escalation when the source requires it.

Additional safeguards are required for:

- KYC;
- AML;
- customer identification;
- compliance escalation;
- cash handling;
- transaction limits;
- customer deletion;
- emergencies;
- financial transactions;
- system security.

For high-risk topics, the answer should include the authoritative source and avoid presenting uncertain information as mandatory policy.

---

## 13. Answer Evaluation

A second evaluation layer must be created.

Each evaluation case should define:

```text
Question
Expected source
Required facts
Forbidden claims
Required escalation
Preferred format
Risk level
```

Example:

```yaml
id: foreign-customer-handling
question: איך מטפלים בלקוח זר?
expected_titles:
  - דגשים בעת רישום לקוחות זרים
required_facts:
  - passport validation
  - document validity
  - KYC requirement
  - compliance checks
forbidden_claims:
  - unsupported transaction limits
  - guaranteed approval
risk_level: high
```

Evaluation categories:

- source correctness;
- factual completeness;
- groundedness;
- citation correctness;
- forbidden-content rate;
- answer usefulness;
- response latency.

---

## 14. Browser Extension Architecture

The extension is the primary employee entry point.

### Version 1.0 behavior

- inject a floating button into approved pages;
- open a large readable workspace panel;
- load the production frontend;
- preserve the current web page;
- allow minimize and reopen;
- show connection status;
- handle offline and timeout states;
- support logout;
- avoid reading page content by default.

### Permissions principle

Initial production mode:

```text
No automatic customer-data extraction.
No DOM scraping.
No password-field access.
No background reading of page content.
```

### Context levels

#### Level 0 — No context

The extension sends only the user’s question.

#### Level 1 — Basic context

With organizational approval:

- hostname;
- page title;
- application name;
- route category.

#### Level 2 — Explicit user-provided context

The employee selects text and chooses:

```text
Ask BC Workspace about selected text
```

#### Level 3 — Approved structured integration

Future controlled adapters for specific systems.

Level 3 must be reviewed separately for privacy, security, and data-protection impact.

---

## 15. Extension Distribution

The current unpacked extension is suitable only for development.

Production options:

1. private Chrome Web Store listing;
2. managed enterprise extension deployment;
3. approved internal distribution package.

Required capabilities:

- signed version;
- controlled updates;
- version reporting;
- rollback;
- minimum browser version;
- installation instructions;
- support contact.

---

## 16. Observability

### Application metrics

- request count;
- answer count;
- error rate;
- response latency;
- OpenAI latency;
- retrieval latency;
- database latency;
- synchronization status;
- embedding failures.

### Product metrics

- active users;
- questions per user;
- feedback rate;
- positive feedback;
- unanswered questions;
- source-open rate;
- frequent topics;
- documents with repeated confusion.

### Logging

Recommended logging:

- request ID;
- user ID;
- endpoint;
- duration;
- status;
- retrieval document IDs;
- error category.

Avoid logging:

- passwords;
- API keys;
- full authentication tokens;
- unnecessary customer-identifying data;
- full page contents without a defined need.

---

## 17. Backups and Recovery

Required backups:

- PostgreSQL database;
- Wiki-derived knowledge records;
- configuration;
- extension release packages;
- deployment manifests.

Recommended initial policy:

```text
Daily encrypted database backup
Weekly full backup
30-day retention
Monthly restore test
```

A backup is not considered valid until restoration is tested.

Recovery documentation must include:

- restore database;
- restore secrets;
- restart services;
- verify embeddings;
- verify health endpoints;
- verify synchronization;
- verify extension connectivity.

---

## 18. Deployment Requirements

Production deployment should support:

- repeatable build;
- pinned dependencies;
- automatic restart;
- health checks;
- non-root containers where practical;
- immutable application images;
- persistent database volume;
- secret injection;
- rollback to previous image;
- database migration execution;
- post-deployment smoke tests.

Deployment order:

```text
1. Backup
2. Database migration
3. Backend deployment
4. Worker deployment
5. Frontend deployment
6. Health verification
7. Retrieval smoke test
8. Copilot answer smoke test
9. Extension validation
```

---

## 19. Pilot Plan

The first pilot should include 3–5 employees.

Recommended participants:

- project owner;
- one branch manager;
- one experienced representative;
- one newer representative;
- one compliance or Back Office representative.

Recommended duration:

```text
One working week
```

### Pilot goals

- validate daily usefulness;
- identify missing procedures;
- measure answer quality;
- test production stability;
- test authentication;
- test extension usability;
- detect security issues;
- gather realistic questions.

### Pilot success indicators

```text
System availability:       ≥ 99% during work hours
Positive feedback:         ≥ 80%
Answers with source:       ≥ 95%
Median response time:      < 10 seconds
Unauthorized access:      0
Critical hallucinations:  0
```

---

## 20. Rollout Gates

### Infrastructure

- [ ] Production server exists
- [ ] HTTPS enabled
- [ ] Database is private
- [ ] Automatic restart enabled
- [ ] Daily backups enabled
- [ ] Restore test completed

### Security

- [ ] Authentication enabled
- [ ] Account disabling works
- [ ] Authorization model approved
- [ ] Secrets removed from source control
- [ ] Extension permissions reviewed
- [ ] Logging privacy reviewed

### Knowledge

- [ ] Automatic Wiki sync enabled
- [ ] Sync failures visible
- [ ] Embedding updates automatic
- [ ] Archive/Sandbox/redirect policy verified
- [ ] Source links verified

### Quality

- [ ] Retrieval benchmark passes
- [ ] Answer evaluation suite exists
- [ ] High-risk questions tested
- [ ] Refusal/fallback behavior tested
- [ ] No-source behavior tested

### Product

- [ ] Extension production URL configured
- [ ] Offline state implemented
- [ ] Feedback available
- [ ] Pilot completed
- [ ] Pilot findings reviewed
- [ ] Rollout approved

---

## 21. Recommended Implementation Sprints

### Sprint 1 — Production Foundation

Goal:

> Make BC Workspace available 24/7 without dependence on a local computer.

Tasks:

- Dockerize frontend;
- Dockerize backend;
- production PostgreSQL with pgvector;
- reverse proxy;
- HTTPS;
- production environment configuration;
- database migration;
- database transfer;
- embedding verification;
- health checks;
- automatic restart;
- initial backup.

### Sprint 2 — Production Extension

Goal:

> Connect the browser extension to the permanent production service.

Tasks:

- replace localhost URLs;
- add online/offline status;
- add retry behavior;
- configure production CSP;
- reduce permissions;
- version extension;
- create installation package;
- install on pilot computers.

### Sprint 3 — Authentication and Authorization

Goal:

> Allow only approved users to access authorized knowledge.

Tasks:

- user model;
- login;
- session management;
- role model;
- active/inactive account state;
- protected API routes;
- frontend login;
- extension session handling;
- initial document access filtering.

### Sprint 4 — Automatic Wiki Synchronization

Goal:

> Ensure Wiki changes appear automatically in BC Workspace.

Tasks:

- scheduled synchronization;
- incremental revision detection;
- embedding generation;
- sync status;
- failure retry;
- admin visibility;
- stale-data warning.

### Sprint 5 — Answer Quality

Goal:

> Validate answer correctness, not only document retrieval.

Tasks:

- answer Golden Dataset;
- required-fact assertions;
- forbidden-claim assertions;
- high-risk test cases;
- citation validation;
- no-source behavior;
- evaluation report.

### Sprint 6 — Pilot

Goal:

> Validate actual employee use.

Tasks:

- choose participants;
- install extension;
- collect feedback;
- measure usage;
- review unanswered questions;
- fix critical gaps;
- approve or reject wider rollout.

---

## 22. Immediate Next Step

The next engineering task is:

> Build a production-ready containerized deployment for the existing frontend, backend, and PostgreSQL database.

The next code changes should focus on:

```text
Dockerfile — backend
Dockerfile — frontend
docker-compose.production.yml
reverse-proxy configuration
production environment template
deployment documentation
backup script
health-check script
```

No additional product features should be prioritized before the production foundation is stable.

---

## 23. Definition of BC Workspace v1.0

BC Workspace v1.0 is complete when:

1. the service is available independently of the developer’s computer;
2. approved employees can authenticate;
3. the extension opens the production workspace;
4. questions receive grounded answers with official Wiki sources;
5. Wiki updates synchronize automatically;
6. restricted information is access-controlled;
7. backups and restoration are tested;
8. monitoring identifies failures;
9. answer-quality tests pass;
10. a controlled pilot is completed successfully.

---

## 24. Final Product Statement

BC Workspace v1.0 is not an autonomous employee and does not replace organizational responsibility.

It is:

> A secure organizational knowledge assistant that brings Bitcoin Change’s authoritative operational knowledge directly into the employee’s active workspace.

Its purpose is to reduce search time, improve answer consistency, support onboarding, reduce dependence on individual knowledge holders, and make official procedures easier to use during real work.
