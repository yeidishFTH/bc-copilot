from __future__ import annotations

import pytest

from app.services.copilot.intent import (
    CopilotIntent,
    IntentClassifier,
)


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "איך עושים פתיחת סניף?",
            CopilotIntent.PROCEDURE,
        ),
        (
            "מה צריך לעשות כשלקוח מבקש למחוק כרטיס?",
            CopilotIntent.PROCEDURE,
        ),
        (
            "מהם השלבים לזיהוי לקוח?",
            CopilotIntent.PROCEDURE,
        ),
        (
            "מצא לי את נוהל מחיקת כרטיס לקוח",
            CopilotIntent.DOCUMENT_LOOKUP,
        ),
        (
            "איזה מדריך מסביר על Salesforce?",
            CopilotIntent.DOCUMENT_LOOKUP,
        ),
        (
            "איפה כתוב שחייבים לקבל בקשה במייל?",
            CopilotIntent.CITATION,
        ),
        (
            "תן לי את המקור לדרישת הזיהוי",
            CopilotIntent.CITATION,
        ),
        (
            "סכם לי את נוהל סגירת היום",
            CopilotIntent.SUMMARY,
        ),
        (
            "תן תקציר של מדריך יצירת עסקה",
            CopilotIntent.SUMMARY,
        ),
        (
            "השווה בין נוהל הפתיחה לנוהל הסגירה",
            CopilotIntent.COMPARISON,
        ),
        (
            "מה ההבדל בין מנהל סניף למנהל אזור?",
            CopilotIntent.COMPARISON,
        ),
        (
            "מה השתנה בגרסה האחרונה של הנוהל?",
            CopilotIntent.CHANGE_LOG,
        ),
        (
            "אילו שינויים חדשים נעשו במסמך?",
            CopilotIntent.CHANGE_LOG,
        ),
        (
            "מה התפקיד של מחלקת הציות?",
            CopilotIntent.GENERAL_QUESTION,
        ),
        (
            "מי אחראי על ההדרכות?",
            CopilotIntent.GENERAL_QUESTION,
        ),
    ],
)
def test_classifies_hebrew_questions(
    classifier: IntentClassifier,
    question: str,
    expected: CopilotIntent,
) -> None:
    result = classifier.classify(question)

    assert result.intent is expected
    assert 0.5 <= result.confidence <= 0.98


def test_comparison_wins_over_document_noun(
    classifier: IntentClassifier,
) -> None:
    result = classifier.classify(
        "השווה בין שני נהלים לפתיחת סניף"
    )

    assert result.intent is CopilotIntent.COMPARISON
    assert "comparison_phrase" in (
        result.matched_signals
    )


def test_summary_wins_over_document_lookup_noun(
    classifier: IntentClassifier,
) -> None:
    result = classifier.classify(
        "סכם לי את המסמך על זיהוי לקוחות"
    )

    assert result.intent is CopilotIntent.SUMMARY


def test_document_noun_alone_is_not_confident_enough(
    classifier: IntentClassifier,
) -> None:
    result = classifier.classify(
        "נוהל לקוחות"
    )

    assert result.intent is (
        CopilotIntent.GENERAL_QUESTION
    )


def test_normalizes_whitespace(
    classifier: IntentClassifier,
) -> None:
    result = classifier.classify(
        "  איך   עושים   פתיחת סניף?  "
    )

    assert result.intent is CopilotIntent.PROCEDURE


@pytest.mark.parametrize(
    "invalid_question",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_question(
    classifier: IntentClassifier,
    invalid_question: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="question cannot be empty",
    ):
        classifier.classify(invalid_question)


def test_rejects_non_string_question(
    classifier: IntentClassifier,
) -> None:
    with pytest.raises(
        ValueError,
        match="question must be a string",
    ):
        classifier.classify(123)  # type: ignore[arg-type]
