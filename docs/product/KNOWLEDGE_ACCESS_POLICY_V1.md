# BC Workspace — Knowledge Access Policy v1

## Purpose

This policy defines how MediaWiki knowledge should be classified for access
through BC Workspace.

MediaWiki remains the authoritative source.

Runtime authorization is enforced only by the explicit `access_roles`
persisted for each document. Portal recommendations are advisory and are used
only for Audit and classification.

## Current roles

- `branch_user` — account used by an approved branch workstation
- `management` — approved individual management account
- `administrator` — BC Workspace system administrator

## Runtime semantics

An empty access-role list means that the document is available to every
authenticated and activated Workspace account:

    access_roles = []

A non-empty list requires an explicit matching account role:

    access_roles = ["management", "administrator"]

Roles are not implicitly hierarchical.

For example, `administrator` does not automatically receive a document that
contains only:

    access_roles = ["management"]

To allow both roles, both roles must be listed explicitly.

## Standard profiles

### All Workspace users

    branch_user, management, administrator

Use for normal employee-facing operational knowledge.

### Management and administrator

    management, administrator

Use for management procedures, internal controls and management information.

### Administrator only

    administrator

Use for infrastructure, deployment, security configuration, backups,
credentials and system administration.

## Portal recommendations

The following portals normally recommend access to all Workspace roles:

- תפעול סניף
- לקוחות
- עובדים והדרכה
- סניפים
- מלאי וציוד
- טפסים
- ידע ארגוני

Recommended roles:

    branch_user, management, administrator

The following portal normally recommends management and administrator access:

- הנהלה

Recommended roles:

    management, administrator

The following portals require document-level manual review:

- ציות ורגולציה
- מערכות מידע
- Back Office
- משאבי אנוש
- שיווק
- פורטלים
- Sandbox

These portals may contain both employee-facing and sensitive knowledge.
Permissions must not be assigned solely from the portal name.

## Sensitive departmental knowledge

The current account model does not yet contain dedicated roles such as:

- `compliance`
- `human_resources`
- `back_office`
- `marketing`
- `trainer`

Sensitive departmental knowledge must not be exposed through an approximate
role.

Employee-facing compliance or HR instructions may be classified after manual
review.

Internal investigations, personal employee records, salary information,
disciplinary records and department-only material should wait for dedicated
roles and a separate authorization decision.

## Metadata examples

### Operational document

    {{Metadata
    | סוג מסמך = נוהל
    | פורטל = תפעול סניף
    | הרשאות גישה = branch_user, management, administrator
    }}

### Management document

    {{Metadata
    | סוג מסמך = נוהל
    | פורטל = הנהלה
    | הרשאות גישה = management, administrator
    }}

### Administrator-only document

    {{Metadata
    | סוג מסמך = מערכת
    | פורטל = מערכות מידע
    | הרשאות גישה = administrator
    }}

## Safe rollout

1. Generate a read-only Audit for all existing knowledge documents.
2. Review every recommendation.
3. Begin with 3–5 low-risk documents.
4. Add explicit `הרשאות גישה` metadata in MediaWiki.
5. Synchronize the Wiki.
6. Verify the persisted roles in PostgreSQL.
7. Test with branch, management and administrator accounts.
8. Expand only in reviewed batches.

## Fail-safe principles

- Explicit Wiki metadata remains authoritative.
- Unknown roles are invalid.
- Unknown portals require manual review.
- Mixed or sensitive portals receive no automatic permission.
- Authorization is enforced in SQL before results reach Copilot or OpenAI.
- Policy recommendations never overwrite explicit document metadata.
- Existing documents remain open until reviewed and explicitly classified.
