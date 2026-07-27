from __future__ import annotations

import pytest

from app.services.copilot.query_rewriter import (
    QueryRewriter,
)


@pytest.fixture
def rewriter() -> QueryRewriter:
    return QueryRewriter()


def test_preserves_original_and_normalizes_query(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "  איך   מוחקים   לקוח?  "
    )

    assert result.original_query == (
        "  איך   מוחקים   לקוח?  "
    )
    assert result.normalized_query == (
        "איך מוחקים לקוח?"
    )
    assert result.search_queries[0] == (
        "איך מוחקים לקוח?"
    )


@pytest.mark.parametrize(
    ("query", "expected_query"),
    [
        (
            "איך מוחקים לקוח?",
            "מחיקת כרטיס לקוח",
        ),
        (
            "מה עושים במחיקת חשבון?",
            "נוהל מחיקת כרטיס לקוח",
        ),
        (
            "איך מזהים לקוח?",
            "זיהוי ואימות לקוח",
        ),
        (
            "איפה כתוב שצריך צילום תעודת זהות?",
            "KYC",
        ),
        (
            "איך מטפלים בלקוח זר?",
            "דגשים בעת רישום לקוחות זרים",
        ),
        (
            "איך עובדים עם Salesforce?",
            "CRM",
        ),
        (
            "מה עושים בכספומט?",
            "Lamassu",
        ),
        (
            "מהן משימות הפתיחה?",
            "פתיחת סניף",
        ),
        (
            "איך מבצעים ספירה סופית?",
            "נוהל סגירת יום",
        ),
        (
            "מתי פונים לקצין ציות?",
            "נוהל התקשרות עם מחלקת ציות",
        ),
        (
            "איך מבצעים עסקה?",
            "יצירת עסקה",
        ),
    ],
)
def test_expands_domain_aliases(
    rewriter: QueryRewriter,
    query: str,
    expected_query: str,
) -> None:
    result = rewriter.rewrite(query)

    assert expected_query in result.search_queries
    assert result.matched_aliases


def test_detects_known_document_name(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "סכם לי את נוהל סגירת יום"
    )

    assert (
        "נוהל סגירת יום"
        in result.matched_document_names
    )
    assert (
        "נוהל סגירת יום"
        in result.search_queries
    )


def test_does_not_duplicate_queries(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "Salesforce CRM"
    )

    normalized = [
        item.casefold()
        for item in result.search_queries
    ]

    assert len(normalized) == len(set(normalized))


def test_limits_number_of_search_queries(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מחיקת לקוח זיהוי לקוח "
        "כספומט Salesforce ציות"
    )

    assert (
        len(result.search_queries)
        <= rewriter.MAX_SEARCH_QUERIES
    )


def test_unknown_query_is_left_unchanged(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מי אחראי על ההדרכה?"
    )

    assert result.search_queries == (
        "מי אחראי על ההדרכה?",
    )
    assert result.matched_aliases == ()
    assert result.matched_document_names == ()


@pytest.mark.parametrize(
    "invalid_query",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_query(
    rewriter: QueryRewriter,
    invalid_query: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="query cannot be empty",
    ):
        rewriter.rewrite(invalid_query)


def test_rejects_non_string_query(
    rewriter: QueryRewriter,
) -> None:
    with pytest.raises(
        ValueError,
        match="query must be a string",
    ):
        rewriter.rewrite(123)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "צריך למחוק את הלקוח",
            "מחיקת כרטיס לקוח",
        ),
        (
            "איך מזהים את הלקוחה?",
            "זיהוי ואימות לקוח",
        ),
        (
            "מה עושים בכספומטים?",
            "Lamassu",
        ),
        (
            "איך פונים לקצינת הציות?",
            "נוהל התקשרות עם מחלקת ציות",
        ),
        (
            "איך פותחים את הסניף?",
            "פתיחת סניף",
        ),
        (
            "איך יוצרים עסקה?",
            "יצירת עסקה",
        ),
    ],
)
def test_matches_hebrew_inflections_and_prefixes(
    rewriter: QueryRewriter,
    query: str,
    expected: str,
) -> None:
    result = rewriter.rewrite(query)

    assert expected in result.search_queries
