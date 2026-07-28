from __future__ import annotations

import pytest

from app.services.copilot.entities import (
    CopilotEntity,
    EntityDetector,
)


@pytest.fixture
def detector() -> EntityDetector:
    return EntityDetector()


@pytest.mark.parametrize(
    ("question", "expected_entities"),
    [
        (
            "איך מטפלים בלקוח זר?",
            {
                CopilotEntity.FOREIGN_CUSTOMER,
                CopilotEntity.CUSTOMER,
            },
        ),
        (
            "מתי צריך לצלם דרכון?",
            {
                CopilotEntity.PASSPORT,
            },
        ),
        (
            "איך מבצעים זיהוי לקוח?",
            {
                CopilotEntity.KYC,
                CopilotEntity.CUSTOMER,
            },
        ),
        (
            "מתי פונים לקצין ציות בנושא AML?",
            {
                CopilotEntity.COMPLIANCE,
                CopilotEntity.AML,
            },
        ),
        (
            "איך מוחקים לקוח מ-Salesforce?",
            {
                CopilotEntity.CUSTOMER_DELETION,
                CopilotEntity.CUSTOMER,
                CopilotEntity.SALESFORCE,
            },
        ),
        (
            "איך עובדים עם הכספומט של Lamassu?",
            {
                CopilotEntity.ATM,
                CopilotEntity.LAMASSU,
            },
        ),
        (
            "איך מבצעים עסקת USDT ERC-20?",
            {
                CopilotEntity.TRANSACTION,
                CopilotEntity.USDT,
            },
        ),
        (
            "איך פותחים סניף בבוקר?",
            {
                CopilotEntity.BRANCH_OPENING,
                CopilotEntity.BRANCH,
            },
        ),
        (
            "מה עושים בסגירת יום?",
            {
                CopilotEntity.DAY_CLOSING,
            },
        ),
        (
            "איך מבצעים ספירת מזומן?",
            {
                CopilotEntity.CASH_COUNT,
            },
        ),
        (
            "איך עונים ללקוחות בוואטסאפ?",
            {
                CopilotEntity.WHATSAPP,
                CopilotEntity.CUSTOMER,
            },
        ),
    ],
)
def test_detects_expected_entities(
    detector: EntityDetector,
    question: str,
    expected_entities: set[CopilotEntity],
) -> None:
    detection = detector.detect(question)

    assert expected_entities.issubset(
        set(detection.entity_ids)
    )

    assert all(
        0.0 < entity.confidence <= 1.0
        for entity in detection.entities
    )


def test_detects_foreign_customer_from_resident_abroad(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "מה צריך מתושב חוץ?"
    )

    assert detection.contains(
        CopilotEntity.FOREIGN_CUSTOMER
    )


def test_detects_attached_hebrew_prefixes(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "מה עושים בכספומט?"
    )

    assert detection.contains(
        CopilotEntity.ATM
    )


def test_preserves_original_and_normalized_text(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "  איך   מוחקים   לקוח?  "
    )

    assert detection.original_text == (
        "  איך   מוחקים   לקוח?  "
    )
    assert detection.normalized_text == (
        "איך מוחקים לקוח?"
    )


def test_orders_entities_by_confidence(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "איך מוחקים לקוח מ-Salesforce?"
    )

    confidences = [
        item.confidence
        for item in detection.entities
    ]

    assert confidences == sorted(
        confidences,
        reverse=True,
    )


def test_unknown_question_returns_no_entities(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "מי אחראי על ההדרכה?"
    )

    assert detection.entities == ()
    assert detection.entity_ids == ()


@pytest.mark.parametrize(
    "invalid_text",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_text(
    detector: EntityDetector,
    invalid_text: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="text cannot be empty",
    ):
        detector.detect(invalid_text)


def test_rejects_non_string_text(
    detector: EntityDetector,
) -> None:
    with pytest.raises(
        ValueError,
        match="text must be a string",
    ):
        detector.detect(123)  # type: ignore[arg-type]


def test_detects_salesforce_from_hebrew_spelling_and_accounts(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "איך עובדים עם Accounts בסיילספורס?"
    )

    assert detection.contains(
        CopilotEntity.SALESFORCE
    )


def test_detects_branch_opening_from_morning_shift(
    detector: EntityDetector,
) -> None:
    detection = detector.detect(
        "מהן המשימות בתחילת משמרת בוקר?"
    )

    assert detection.contains(
        CopilotEntity.BRANCH_OPENING
    )
