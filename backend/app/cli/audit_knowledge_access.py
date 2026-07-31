from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgePage,
    KnowledgeRevision,
    KnowledgeRevisionMetadata,
)
from app.db.session import AsyncSessionFactory
from app.services.knowledge.access_policy import (
    AccessPolicyRecommendation,
    recommend_access_for_portal,
)


OutputFormat = Literal[
    "json",
    "csv",
    "markdown",
]

MISSING_VALUE = "<missing>"
OPEN_ACCESS_LABEL = "<open>"


@dataclass(frozen=True, slots=True)
class KnowledgeAccessAuditRow:
    title: str
    canonical_url: str
    wiki_page_id: int
    wiki_revision_id: int
    namespace_id: int
    is_active: bool
    is_redirect: bool
    status: str | None
    document_type: str | None
    portal: str | None
    category: str | None
    audience: tuple[str, ...]
    owner: str | None
    responsible_department: str | None
    updated_on: date | None
    version: str | None
    current_access_roles: tuple[str, ...]
    recommended_access_roles: tuple[str, ...] | None
    recommendation_source: str
    recommendation_reason: str
    requires_manual_review: bool
    missing_metadata: tuple[str, ...]
    quality_score: int
    risk_level: str


@dataclass(frozen=True, slots=True)
class KnowledgeAccessAuditSummary:
    total_documents: int
    active_documents: int
    redirects: int
    open_documents: int
    restricted_documents: int
    manual_review_required: int
    automatic_recommendations: int
    missing_portal: int
    missing_category: int
    missing_document_type: int
    missing_owner: int
    average_quality_score: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only knowledge access Audit "
            "from the current BC Workspace database."
        )
    )

    parser.add_argument(
        "--format",
        choices=(
            "json",
            "csv",
            "markdown",
        ),
        default="markdown",
        help="Output format.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional output file. When omitted, "
            "the report is printed to stdout."
        ),
    )

    parser.add_argument(
        "--include-redirects",
        action="store_true",
        help="Include redirect pages.",
    )

    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include inactive pages.",
    )

    return parser


def clean_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


def missing_metadata_fields(
    *,
    status: str | None,
    document_type: str | None,
    portal: str | None,
    category: str | None,
    audience: Iterable[str],
    owner: str | None,
    responsible_department: str | None,
) -> tuple[str, ...]:
    missing: list[str] = []

    if clean_optional_text(status) is None:
        missing.append("status")

    if clean_optional_text(document_type) is None:
        missing.append("document_type")

    if clean_optional_text(portal) is None:
        missing.append("portal")

    if clean_optional_text(category) is None:
        missing.append("category")

    if not tuple(audience):
        missing.append("audience")

    if clean_optional_text(owner) is None:
        missing.append("owner")

    if (
        clean_optional_text(
            responsible_department
        )
        is None
    ):
        missing.append(
            "responsible_department"
        )

    return tuple(missing)


def calculate_quality_score(
    missing_fields: Iterable[str],
) -> int:
    weights = {
        "portal": 20,
        "category": 15,
        "document_type": 20,
        "status": 10,
        "audience": 10,
        "owner": 15,
        "responsible_department": 10,
    }

    deduction = sum(
        weights.get(field, 0)
        for field in missing_fields
    )

    return max(
        0,
        100 - deduction,
    )


def determine_risk_level(
    *,
    requires_manual_review: bool,
    missing_fields: Iterable[str],
    current_access_roles: Iterable[str],
    is_redirect: bool,
) -> str:
    missing = set(missing_fields)
    roles = tuple(current_access_roles)

    if is_redirect:
        return "low"

    critical_missing = {
        "portal",
        "document_type",
    }

    if critical_missing & missing:
        return "high"

    if (
        requires_manual_review
        and not roles
    ):
        return "high"

    if requires_manual_review:
        return "medium"

    if len(missing) >= 3:
        return "medium"

    return "low"


def recommendation_source(
    recommendation: AccessPolicyRecommendation,
) -> str:
    if recommendation.access_roles is None:
        return "manual_review"

    return "portal_policy_v1"


def build_audit_row(
    *,
    title: str,
    canonical_url: str,
    wiki_page_id: int,
    wiki_revision_id: int,
    namespace_id: int,
    is_active: bool,
    is_redirect: bool,
    status: str | None,
    document_type: str | None,
    portal: str | None,
    category: str | None,
    audience: Iterable[str] | None,
    owner: str | None,
    responsible_department: str | None,
    updated_on: date | None,
    version: str | None,
    access_roles: Iterable[str] | None,
) -> KnowledgeAccessAuditRow:
    normalized_audience = tuple(
        audience or ()
    )

    normalized_roles = tuple(
        access_roles or ()
    )

    normalized_portal = clean_optional_text(
        portal
    )

    recommendation = (
        recommend_access_for_portal(
            normalized_portal
        )
    )

    missing = missing_metadata_fields(
        status=status,
        document_type=document_type,
        portal=normalized_portal,
        category=category,
        audience=normalized_audience,
        owner=owner,
        responsible_department=(
            responsible_department
        ),
    )

    quality_score = calculate_quality_score(
        missing
    )

    risk_level = determine_risk_level(
        requires_manual_review=(
            recommendation
            .requires_manual_review
        ),
        missing_fields=missing,
        current_access_roles=normalized_roles,
        is_redirect=is_redirect,
    )

    return KnowledgeAccessAuditRow(
        title=title,
        canonical_url=canonical_url,
        wiki_page_id=wiki_page_id,
        wiki_revision_id=wiki_revision_id,
        namespace_id=namespace_id,
        is_active=is_active,
        is_redirect=is_redirect,
        status=clean_optional_text(status),
        document_type=clean_optional_text(
            document_type
        ),
        portal=normalized_portal,
        category=clean_optional_text(
            category
        ),
        audience=normalized_audience,
        owner=clean_optional_text(owner),
        responsible_department=(
            clean_optional_text(
                responsible_department
            )
        ),
        updated_on=updated_on,
        version=clean_optional_text(version),
        current_access_roles=normalized_roles,
        recommended_access_roles=(
            recommendation.access_roles
        ),
        recommendation_source=(
            recommendation_source(
                recommendation
            )
        ),
        recommendation_reason=(
            recommendation.reason
        ),
        requires_manual_review=(
            recommendation
            .requires_manual_review
        ),
        missing_metadata=missing,
        quality_score=quality_score,
        risk_level=risk_level,
    )


def summarize_rows(
    rows: Iterable[
        KnowledgeAccessAuditRow
    ],
) -> KnowledgeAccessAuditSummary:
    materialized = tuple(rows)

    total = len(materialized)

    if total:
        average_quality = round(
            sum(
                row.quality_score
                for row in materialized
            )
            / total,
            2,
        )
    else:
        average_quality = 0.0

    return KnowledgeAccessAuditSummary(
        total_documents=total,
        active_documents=sum(
            row.is_active
            for row in materialized
        ),
        redirects=sum(
            row.is_redirect
            for row in materialized
        ),
        open_documents=sum(
            not row.current_access_roles
            for row in materialized
        ),
        restricted_documents=sum(
            bool(row.current_access_roles)
            for row in materialized
        ),
        manual_review_required=sum(
            row.requires_manual_review
            for row in materialized
        ),
        automatic_recommendations=sum(
            not row.requires_manual_review
            for row in materialized
        ),
        missing_portal=sum(
            "portal" in row.missing_metadata
            for row in materialized
        ),
        missing_category=sum(
            "category" in row.missing_metadata
            for row in materialized
        ),
        missing_document_type=sum(
            (
                "document_type"
                in row.missing_metadata
            )
            for row in materialized
        ),
        missing_owner=sum(
            "owner" in row.missing_metadata
            for row in materialized
        ),
        average_quality_score=average_quality,
    )


async def load_audit_rows(
    session: AsyncSession,
    *,
    include_redirects: bool,
    include_inactive: bool,
) -> list[KnowledgeAccessAuditRow]:
    statement = (
        select(
            KnowledgePage.title,
            KnowledgePage.canonical_url,
            KnowledgePage.wiki_page_id,
            KnowledgePage.namespace_id,
            KnowledgePage.is_active,
            KnowledgePage.is_redirect,
            KnowledgeRevision.wiki_revision_id,
            KnowledgeRevisionMetadata.status,
            KnowledgeRevisionMetadata.document_type,
            KnowledgeRevisionMetadata.portal,
            KnowledgeRevisionMetadata.category,
            KnowledgeRevisionMetadata.audience,
            KnowledgeRevisionMetadata.owner,
            (
                KnowledgeRevisionMetadata
                .responsible_department
            ),
            KnowledgeRevisionMetadata.updated_on,
            KnowledgeRevisionMetadata.version,
            KnowledgeRevisionMetadata.access_roles,
        )
        .join(
            KnowledgeRevision,
            (
                KnowledgeRevision.page_id
                == KnowledgePage.id
            )
            & (
                KnowledgeRevision.wiki_revision_id
                == KnowledgePage.latest_revision_id
            ),
        )
        .outerjoin(
            KnowledgeRevisionMetadata,
            (
                KnowledgeRevisionMetadata
                .revision_id
                == KnowledgeRevision.id
            ),
        )
        .order_by(
            KnowledgePage.title.asc(),
            KnowledgePage.wiki_page_id.asc(),
        )
    )

    if not include_redirects:
        statement = statement.where(
            KnowledgePage.is_redirect.is_(False)
        )

    if not include_inactive:
        statement = statement.where(
            KnowledgePage.is_active.is_(True)
        )

    result = await session.execute(
        statement
    )

    rows: list[KnowledgeAccessAuditRow] = []

    for record in result.mappings():
        rows.append(
            build_audit_row(
                title=record["title"],
                canonical_url=(
                    record["canonical_url"]
                ),
                wiki_page_id=(
                    record["wiki_page_id"]
                ),
                wiki_revision_id=(
                    record["wiki_revision_id"]
                ),
                namespace_id=(
                    record["namespace_id"]
                ),
                is_active=(
                    record["is_active"]
                ),
                is_redirect=(
                    record["is_redirect"]
                ),
                status=record["status"],
                document_type=(
                    record["document_type"]
                ),
                portal=record["portal"],
                category=record["category"],
                audience=record["audience"],
                owner=record["owner"],
                responsible_department=(
                    record[
                        "responsible_department"
                    ]
                ),
                updated_on=(
                    record["updated_on"]
                ),
                version=record["version"],
                access_roles=(
                    record["access_roles"]
                ),
            )
        )

    return rows


def serialize_value(
    value: Any,
) -> Any:
    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if isinstance(value, tuple):
        return list(value)

    return value


def row_to_dict(
    row: KnowledgeAccessAuditRow,
) -> dict[str, Any]:
    return {
        key: serialize_value(value)
        for key, value in asdict(
            row
        ).items()
    }


def render_json(
    rows: Iterable[
        KnowledgeAccessAuditRow
    ],
) -> str:
    materialized = tuple(rows)

    payload = {
        "summary": asdict(
            summarize_rows(
                materialized
            )
        ),
        "documents": [
            row_to_dict(row)
            for row in materialized
        ],
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def format_roles(
    roles: Iterable[str] | None,
) -> str:
    if roles is None:
        return MISSING_VALUE

    materialized = tuple(roles)

    if not materialized:
        return OPEN_ACCESS_LABEL

    return ", ".join(materialized)


def format_list(
    values: Iterable[str],
) -> str:
    materialized = tuple(values)

    if not materialized:
        return MISSING_VALUE

    return ", ".join(materialized)


def render_csv(
    rows: Iterable[
        KnowledgeAccessAuditRow
    ],
) -> str:
    output = io.StringIO()

    fieldnames = (
        "title",
        "canonical_url",
        "wiki_page_id",
        "wiki_revision_id",
        "namespace_id",
        "is_active",
        "is_redirect",
        "status",
        "document_type",
        "portal",
        "category",
        "audience",
        "owner",
        "responsible_department",
        "updated_on",
        "version",
        "current_access_roles",
        "recommended_access_roles",
        "recommendation_source",
        "recommendation_reason",
        "requires_manual_review",
        "missing_metadata",
        "quality_score",
        "risk_level",
    )

    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for row in rows:
        payload = row_to_dict(row)

        payload["audience"] = format_list(
            row.audience
        )

        payload[
            "current_access_roles"
        ] = format_roles(
            row.current_access_roles
        )

        payload[
            "recommended_access_roles"
        ] = format_roles(
            row.recommended_access_roles
        )

        payload[
            "missing_metadata"
        ] = format_list(
            row.missing_metadata
        )

        writer.writerow(payload)

    return output.getvalue()


def escape_markdown(
    value: Any,
) -> str:
    if value is None:
        return MISSING_VALUE

    text = str(value)

    return (
        text
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def render_markdown(
    rows: Iterable[
        KnowledgeAccessAuditRow
    ],
) -> str:
    materialized = tuple(rows)
    summary = summarize_rows(
        materialized
    )

    lines = [
        "# Knowledge Access Audit",
        "",
        "## Summary",
        "",
        (
            f"- Total documents: "
            f"{summary.total_documents}"
        ),
        (
            f"- Active documents: "
            f"{summary.active_documents}"
        ),
        (
            f"- Redirects: "
            f"{summary.redirects}"
        ),
        (
            f"- Open documents: "
            f"{summary.open_documents}"
        ),
        (
            f"- Restricted documents: "
            f"{summary.restricted_documents}"
        ),
        (
            f"- Manual review required: "
            f"{summary.manual_review_required}"
        ),
        (
            f"- Automatic recommendations: "
            f"{summary.automatic_recommendations}"
        ),
        (
            f"- Missing portal: "
            f"{summary.missing_portal}"
        ),
        (
            f"- Missing category: "
            f"{summary.missing_category}"
        ),
        (
            f"- Missing document type: "
            f"{summary.missing_document_type}"
        ),
        (
            f"- Missing owner: "
            f"{summary.missing_owner}"
        ),
        (
            f"- Average quality score: "
            f"{summary.average_quality_score}"
        ),
        "",
        "## Documents",
        "",
        (
            "| Title | Portal | Category | "
            "Document type | Current roles | "
            "Recommended roles | Manual review | "
            "Missing metadata | Score | Risk |"
        ),
        (
            "|---|---|---|---|---|---|"
            "---:|---|---:|---|"
        ),
    ]

    for row in materialized:
        lines.append(
            "| "
            + " | ".join(
                (
                    escape_markdown(
                        row.title
                    ),
                    escape_markdown(
                        row.portal
                    ),
                    escape_markdown(
                        row.category
                    ),
                    escape_markdown(
                        row.document_type
                    ),
                    escape_markdown(
                        format_roles(
                            row.current_access_roles
                        )
                    ),
                    escape_markdown(
                        format_roles(
                            row.recommended_access_roles
                        )
                    ),
                    (
                        "yes"
                        if row.requires_manual_review
                        else "no"
                    ),
                    escape_markdown(
                        format_list(
                            row.missing_metadata
                        )
                    ),
                    str(row.quality_score),
                    row.risk_level,
                )
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def render_report(
    rows: Iterable[
        KnowledgeAccessAuditRow
    ],
    output_format: OutputFormat,
) -> str:
    if output_format == "json":
        return render_json(rows)

    if output_format == "csv":
        return render_csv(rows)

    if output_format == "markdown":
        return render_markdown(rows)

    raise ValueError(
        f"unsupported output format: "
        f"{output_format}"
    )


async def run_audit(
    *,
    output_format: OutputFormat,
    output: Path | None,
    include_redirects: bool,
    include_inactive: bool,
) -> str:
    async with AsyncSessionFactory() as session:
        rows = await load_audit_rows(
            session,
            include_redirects=(
                include_redirects
            ),
            include_inactive=(
                include_inactive
            ),
        )

        await session.rollback()

    report = render_report(
        rows,
        output_format,
    )

    if output is not None:
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            report,
            encoding="utf-8",
        )

    return report


async def async_main() -> int:
    args = build_parser().parse_args()

    report = await run_audit(
        output_format=args.format,
        output=args.output,
        include_redirects=(
            args.include_redirects
        ),
        include_inactive=(
            args.include_inactive
        ),
    )

    if args.output is None:
        print(
            report,
            end="",
        )
    else:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "format": args.format,
                    "output": str(
                        args.output
                    ),
                    "read_only": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
