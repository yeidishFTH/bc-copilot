from __future__ import annotations

import pytest

from app.services.copilot.entities import (
    CopilotEntity,
)

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


def test_foreign_customer_entity_adds_existing_kyc_procedure(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "איך מטפלים בלקוח זר?"
    )

    assert (
        "נוהל זיהוי ואימות לקוח"
        in result.search_queries
    )
    assert "KYC" in result.search_queries

    assert (
        CopilotEntity.FOREIGN_CUSTOMER
        in result.detected_entities
    )


def test_passport_entity_adds_customer_identification_procedure(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מתי צריך דרכון?"
    )

    assert (
        "נוהל זיהוי ואימות לקוח"
        in result.search_queries
    )
    assert (
        CopilotEntity.PASSPORT
        in result.detected_entities
    )


def test_atm_entity_adds_usdt_procedure(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מה עושים בכספומט?"
    )

    assert (
        "נוהל מכירת USDT ERC-20 וטיפול בתקלות"
        in result.search_queries
    )
    assert (
        CopilotEntity.ATM
        in result.detected_entities
    )


def test_lamassu_entity_adds_usdt_procedure(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מה עושים ב-Lamassu?"
    )

    assert (
        "נוהל מכירת USDT ERC-20 וטיפול בתקלות"
        in result.search_queries
    )
    assert (
        CopilotEntity.LAMASSU
        in result.detected_entities
    )


def test_compliance_entity_adds_compliance_procedure(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מתי פונים לקצין ציות?"
    )

    assert (
        "נוהל התקשרות עם מחלקת ציות"
        in result.search_queries
    )
    assert (
        CopilotEntity.COMPLIANCE
        in result.detected_entities
    )


def test_unknown_entity_query_remains_single_query(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מי אחראי על ההדרכה?"
    )

    assert result.search_queries == (
        "מי אחראי על ההדרכה?",
    )
    assert result.detected_entities == ()


def test_entity_expansions_respect_final_query_limit(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מחיקת לקוח זיהוי לקוח "
        "כספומט Salesforce ציות"
    )

    assert (
        len(result.search_queries)
        == rewriter.MAX_SEARCH_QUERIES
    )

    assert len(
        {
            query.casefold()
            for query in result.search_queries
        }
    ) == len(result.search_queries)


def test_compliance_overview_prioritizes_knowledge_page(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מה המשמעות של ציות ורגולציה?"
    )

    assert result.search_queries[1] == (
        "ציות ורגולציה"
    )

    assert (
        "נוהל התקשרות עם מחלקת ציות"
        not in result.search_queries
    )


def test_salesforce_accounts_adds_system_queries(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "איך עובדים עם Accounts בסיילספורס?"
    )

    assert (
        "מערכת Salesforce"
        in result.search_queries
    )
    assert "CRM" in result.search_queries

    assert (
        CopilotEntity.SALESFORCE
        in result.detected_entities
    )


def test_morning_shift_adds_branch_opening_checklist(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "מהן המשימות בתחילת משמרת בוקר?"
    )

    assert (
        "צ'קליסט פתיחת ותחזוקת סניף"
        in result.search_queries
    )

    assert (
        CopilotEntity.BRANCH_OPENING
        in result.detected_entities
    )


@pytest.mark.parametrize(
    "question",
    [
        "מה התהליך לקליטת עובד חדש?",
        "איך קולטים עובד חדש?",
        "מה צריך לעשות לפני שעובד חדש מגיע?",
        "איך מבצעים חפיפה לעובדת חדשה?",
        "employee onboarding",
    ],
)
def test_employee_onboarding_expands_queries(
    rewriter: QueryRewriter,
    question: str,
) -> None:
    result = rewriter.rewrite(question)

    assert (
        CopilotEntity.EMPLOYEE_ONBOARDING
        in result.detected_entities
    )
    assert (
        "נוהל קליטת עובד"
        in result.search_queries
    )
    assert (
        "קליטת עובד חדש"
        in result.search_queries
    )
    assert (
        len(result.search_queries) >= 3
    )


def test_employee_onboarding_document_name_is_detected(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "סכם לי את נוהל קליטת עובד"
    )

    assert (
        "נוהל קליטת עובד"
        in result.matched_document_names
    )
    assert (
        "נוהל קליטת עובד"
        in result.search_queries
    )


@pytest.mark.parametrize(
    "question",
    [
        "איך מטפלים בלקוח זר?",
        "איזה מסמכים צריך לקבל מלקוח עם דרכון?",
    ],
)
def test_foreign_customer_priority_fits_query_budget(
    rewriter: QueryRewriter,
    question: str,
) -> None:
    result = rewriter.rewrite(question)

    first_five = result.search_queries[:5]

    assert (
        "נוהל זיהוי ואימות לקוח"
        in first_five
    )
    assert "KYC" in first_five
    assert (
        "דגשים בעת רישום לקוחות זרים"
        in first_five
    )


def test_foreign_customer_expansion_order(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "איך מטפלים בלקוח זר?"
    )

    assert result.search_queries[:5] == (
        "איך מטפלים בלקוח זר?",
        "נוהל זיהוי ואימות לקוח",
        "KYC",
        "דגשים בעת רישום לקוחות זרים",
        "דרכון",
    )


@pytest.mark.parametrize(
    ("question", "expected_entity", "expected_title"),
    [
        (
            "מה עושים כשצריך לפנות את הסניף בחירום?",
            CopilotEntity.EMERGENCY_EVACUATION,
            "נוהל חירום - פינוי בזמן חירום",
        ),
        (
            "איך חונך מדווח על ההתקדמות של עובד חדש?",
            CopilotEntity.MENTOR_REPORT,
            "טופס דיווח חונך",
        ),
        (
            "מה מצופה מנציג במהלך המשמרת?",
            CopilotEntity.REPRESENTATIVE_ROLE,
            "תפקיד הנציג",
        ),
        (
            "איך עובדים עם קופון ללקוח?",
            CopilotEntity.COUPON,
            "נוהל קופונים",
        ),
        (
            "איפה כתובים הכללים למתן הנחה באמצעות קופון?",
            CopilotEntity.COUPON,
            "נוהל קופונים",
        ),
    ],
)
def test_new_coverage_expansions_fit_query_budget(
    rewriter: QueryRewriter,
    question: str,
    expected_entity: CopilotEntity,
    expected_title: str,
) -> None:
    result = rewriter.rewrite(question)

    assert expected_entity in result.detected_entities
    assert expected_title in result.search_queries[:5]


def test_branch_equipment_prioritizes_establishment_procedure(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "איזה ציוד צריך להכין כשפותחים סניף חדש?"
    )

    assert result.search_queries[:5] == (
        "איזה ציוד צריך להכין כשפותחים סניף חדש?",
        "נוהל הקמת סניף",
        "קניית ציוד לסניף",
        "ציוד להקמת סניף",
        "פתיחת סניף חדש",
    )


def test_mentor_report_outranks_generic_onboarding_queries(
    rewriter: QueryRewriter,
) -> None:
    result = rewriter.rewrite(
        "איך חונך מדווח על ההתקדמות של עובד חדש?"
    )

    assert result.search_queries[:5] == (
        "איך חונך מדווח על ההתקדמות של עובד חדש?",
        "טופס דיווח חונך",
        "דיווח חונך",
        "משוב חונך",
        "התקדמות חניך",
    )
