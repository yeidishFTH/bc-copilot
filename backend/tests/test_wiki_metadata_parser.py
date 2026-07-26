from datetime import date

from app.services.wiki_parser import (
    WikiDocumentMetadata,
    WikiMetadataParser,
)


def test_parse_complete_metadata_template() -> None:
    parser = WikiMetadataParser()

    result = parser.parse(
        """
<div dir="rtl">

{{Metadata
|סטטוס=טיוטה
|סוג מסמך=נוהל
|פורטל=ציות ורגולציה
|קטגוריה=KYC
|קהל יעד=נציגים, חונכים, מנהלי סניפים
|בעלים=מחלקת ציות
|מחלקה אחראית=ציות
|עדכון אחרון=26/06/2024
|גרסה=1.2
}}

= כותרת =
תוכן
"""
    )

    assert result == WikiDocumentMetadata(
        status="טיוטה",
        document_type="נוהל",
        portal="ציות ורגולציה",
        category="KYC",
        audience=(
            "נציגים",
            "חונכים",
            "מנהלי סניפים",
        ),
        owner="מחלקת ציות",
        responsible_department="ציות",
        updated_on=date(2024, 6, 26),
        version="1.2",
    )


def test_parse_missing_template_returns_empty() -> None:
    parser = WikiMetadataParser()

    assert parser.parse(
        "= כותרת =\nתוכן"
    ) == WikiDocumentMetadata()


def test_parse_ignores_unknown_fields() -> None:
    parser = WikiMetadataParser()

    result = parser.parse(
        """
{{Metadata
|סטטוס=מאושר
|שדה לא מוכר=ערך כלשהו
|סוג מסמך=מדריך
}}
"""
    )

    assert result.status == "מאושר"
    assert result.document_type == "מדריך"


def test_parse_invalid_date_returns_none() -> None:
    parser = WikiMetadataParser()

    result = parser.parse(
        """
{{Metadata
|עדכון אחרון=מועד לא תקין
}}
"""
    )

    assert result.updated_on is None


def test_parse_supports_iso_date() -> None:
    parser = WikiMetadataParser()

    result = parser.parse(
        """
{{Metadata
|עדכון אחרון=2026-07-26
}}
"""
    )

    assert result.updated_on == date(
        2026,
        7,
        26,
    )


def test_parse_audience_removes_duplicates() -> None:
    parser = WikiMetadataParser()

    result = parser.parse(
        """
{{Metadata
|קהל יעד=נציגים, מנהלים, נציגים
}}
"""
    )

    assert result.audience == (
        "נציגים",
        "מנהלים",
    )


def test_parser_rejects_non_string_input() -> None:
    parser = WikiMetadataParser()

    try:
        parser.parse(None)  # type: ignore[arg-type]
    except ValueError as error:
        assert "must be a string" in str(error)
    else:
        raise AssertionError(
            "Expected ValueError"
        )
