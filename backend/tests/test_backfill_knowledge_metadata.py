from datetime import date

from app.cli.backfill_knowledge_metadata import (
    has_meaningful_metadata,
    metadata_values,
)


def test_metadata_values_extracts_template() -> None:
    values = metadata_values(
        """
{{Metadata
|סטטוס=מאושר
|סוג מסמך=נוהל
|פורטל=ציות ורגולציה
|קטגוריה=KYC
|קהל יעד=נציגים, מנהלי סניפים
|בעלים=מחלקת ציות
|מחלקה אחראית=ציות
|עדכון אחרון=26/07/2026
|גרסה=1.0
}}
"""
    )

    assert values == {
        "status": "מאושר",
        "document_type": "נוהל",
        "portal": "ציות ורגולציה",
        "category": "KYC",
        "audience": [
            "נציגים",
            "מנהלי סניפים",
        ],
        "access_roles": [],
        "owner": "מחלקת ציות",
        "responsible_department": "ציות",
        "updated_on": date(2026, 7, 26),
        "version": "1.0",
    }


def test_empty_metadata_is_not_meaningful() -> None:
    values = metadata_values(
        "= מסמך ללא Metadata ="
    )

    assert has_meaningful_metadata(values) is False


def test_partial_metadata_is_meaningful() -> None:
    values = metadata_values(
        """
{{Metadata
|סוג מסמך=מדריך
}}
"""
    )

    assert has_meaningful_metadata(values) is True
