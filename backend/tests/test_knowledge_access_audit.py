from __future__ import annotations

import csv
import io
import json
from datetime import date

from app.cli.audit_knowledge_access import (
    KnowledgeAccessAuditRow,
    build_audit_row,
    calculate_quality_score,
    determine_risk_level,
    missing_metadata_fields,
    render_csv,
    render_json,
    render_markdown,
    summarize_rows,
)


def make_row(
    **overrides,
) -> KnowledgeAccessAuditRow:
    values = {
        "title": "נוהל פתיחת סניף",
        "canonical_url": (
            "https://wiki.example/"
            "נוהל_פתיחת_סניף"
        ),
        "wiki_page_id": 10,
        "wiki_revision_id": 20,
        "namespace_id": 0,
        "is_active": True,
        "is_redirect": False,
        "status": "מאושר",
        "document_type": "נוהל",
        "portal": "תפעול סניף",
        "category": "פתיחה וסגירה",
        "audience": (
            "נציגים",
        ),
        "owner": "תפעול",
        "responsible_department": (
            "תפעול"
        ),
        "updated_on": date(
            2026,
            7,
            31,
        ),
        "version": "1.0",
        "current_access_roles": (),
        "recommended_access_roles": (
            "branch_user",
            "management",
            "administrator",
        ),
        "recommendation_source": (
            "portal_policy_v1"
        ),
        "recommendation_reason": (
            "Portal recommendation"
        ),
        "requires_manual_review": False,
        "missing_metadata": (),
        "quality_score": 100,
        "risk_level": "low",
    }

    values.update(overrides)

    return KnowledgeAccessAuditRow(
        **values
    )


def test_missing_metadata_fields_detects_gaps() -> None:
    missing = missing_metadata_fields(
        status=None,
        document_type=None,
        portal=None,
        category=None,
        audience=(),
        owner=None,
        responsible_department=None,
    )

    assert missing == (
        "status",
        "document_type",
        "portal",
        "category",
        "audience",
        "owner",
        "responsible_department",
    )


def test_complete_metadata_has_full_score() -> None:
    assert calculate_quality_score(
        ()
    ) == 100


def test_missing_critical_metadata_reduces_score() -> None:
    assert calculate_quality_score(
        (
            "portal",
            "document_type",
            "owner",
        )
    ) == 45


def test_missing_portal_is_high_risk() -> None:
    assert determine_risk_level(
        requires_manual_review=True,
        missing_fields=(
            "portal",
        ),
        current_access_roles=(),
        is_redirect=False,
    ) == "high"


def test_redirect_is_low_risk() -> None:
    assert determine_risk_level(
        requires_manual_review=True,
        missing_fields=(
            "portal",
            "document_type",
        ),
        current_access_roles=(),
        is_redirect=True,
    ) == "low"


def test_operational_portal_gets_policy_recommendation() -> None:
    row = build_audit_row(
        title="נוהל",
        canonical_url="https://example.test",
        wiki_page_id=1,
        wiki_revision_id=2,
        namespace_id=0,
        is_active=True,
        is_redirect=False,
        status="מאושר",
        document_type="נוהל",
        portal="תפעול סניף",
        category="פתיחה",
        audience=("נציגים",),
        owner="תפעול",
        responsible_department="תפעול",
        updated_on=None,
        version="1.0",
        access_roles=(),
    )

    assert row.recommended_access_roles == (
        "branch_user",
        "management",
        "administrator",
    )
    assert (
        row.requires_manual_review
        is False
    )
    assert (
        row.recommendation_source
        == "portal_policy_v1"
    )


def test_sensitive_portal_requires_review() -> None:
    row = build_audit_row(
        title="מסמך ציות",
        canonical_url="https://example.test",
        wiki_page_id=1,
        wiki_revision_id=2,
        namespace_id=0,
        is_active=True,
        is_redirect=False,
        status="מאושר",
        document_type="נוהל",
        portal="ציות ורגולציה",
        category="KYC",
        audience=("נציגים",),
        owner="ציות",
        responsible_department="ציות",
        updated_on=None,
        version="1.0",
        access_roles=(),
    )

    assert (
        row.recommended_access_roles
        is None
    )
    assert (
        row.requires_manual_review
        is True
    )
    assert (
        row.recommendation_source
        == "manual_review"
    )
    assert row.risk_level == "high"


def test_unknown_portal_requires_review() -> None:
    row = build_audit_row(
        title="מסמך",
        canonical_url="https://example.test",
        wiki_page_id=1,
        wiki_revision_id=2,
        namespace_id=0,
        is_active=True,
        is_redirect=False,
        status="מאושר",
        document_type="נוהל",
        portal="פורטל לא מוכר",
        category="כללי",
        audience=("עובדים",),
        owner="הנהלה",
        responsible_department="הנהלה",
        updated_on=None,
        version="1.0",
        access_roles=(),
    )

    assert (
        row.requires_manual_review
        is True
    )
    assert (
        row.recommended_access_roles
        is None
    )


def test_summary_counts_documents() -> None:
    rows = (
        make_row(),
        make_row(
            title="מסמך מוגבל",
            current_access_roles=(
                "management",
                "administrator",
            ),
            requires_manual_review=True,
            recommended_access_roles=None,
            missing_metadata=(
                "category",
            ),
            quality_score=85,
            risk_level="medium",
        ),
    )

    summary = summarize_rows(rows)

    assert summary.total_documents == 2
    assert summary.open_documents == 1
    assert summary.restricted_documents == 1
    assert summary.manual_review_required == 1
    assert summary.automatic_recommendations == 1
    assert (
        summary.average_quality_score
        == 92.5
    )


def test_json_report_is_valid() -> None:
    payload = json.loads(
        render_json(
            (make_row(),)
        )
    )

    assert (
        payload["summary"]
        ["total_documents"]
        == 1
    )
    assert (
        payload["documents"][0]
        ["title"]
        == "נוהל פתיחת סניף"
    )


def test_csv_report_is_valid() -> None:
    report = render_csv(
        (make_row(),)
    )

    rows = list(
        csv.DictReader(
            io.StringIO(report)
        )
    )

    assert len(rows) == 1
    assert (
        rows[0]["current_access_roles"]
        == "<open>"
    )
    assert (
        rows[0][
            "recommended_access_roles"
        ]
        == (
            "branch_user, management, "
            "administrator"
        )
    )


def test_markdown_report_contains_summary_and_table() -> None:
    report = render_markdown(
        (make_row(),)
    )

    assert "# Knowledge Access Audit" in report
    assert "## Summary" in report
    assert "## Documents" in report
    assert "נוהל פתיחת סניף" in report
    assert "portal_policy_v1" not in report


def test_csv_report_uses_lf_line_endings() -> None:
    report = render_csv(
        (make_row(),)
    )

    assert "\r" not in report
    assert report.endswith("\n")

    lines = report.splitlines()

    assert len(lines) == 2
    assert lines[0].startswith(
        "title,canonical_url,"
    )
