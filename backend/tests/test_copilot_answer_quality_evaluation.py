from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli.evaluate_copilot_answers import (
    AnswerQualityCase,
    evaluate_payload,
    load_answer_quality_cases,
)


def make_case() -> AnswerQualityCase:
    return AnswerQualityCase(
        id="delete",
        question="איך מוחקים לקוח?",
        expected_source_titles=(
            "נוהל מחיקת כרטיס לקוח",
        ),
        required_any_terms=(
            "מחיק",
            "כרטיס לקוח",
        ),
        required_all_terms=(),
        forbidden_terms=(),
    )


def test_loads_valid_dataset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.json"

    path.write_text(
        json.dumps(
            [
                {
                    "id": "one",
                    "question": "שאלה",
                    "expected_source_titles": [
                        "מסמך"
                    ],
                    "required_any_terms": [],
                    "required_all_terms": [],
                    "forbidden_terms": []
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_answer_quality_cases(path)

    assert len(cases) == 1
    assert cases[0].id == "one"


def test_rejects_duplicate_case_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cases.json"

    path.write_text(
        json.dumps(
            [
                {
                    "id": "same",
                    "question": "שאלה א",
                    "expected_source_titles": [
                        "מסמך א"
                    ]
                },
                {
                    "id": "same",
                    "question": "שאלה ב",
                    "expected_source_titles": [
                        "מסמך ב"
                    ]
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate answer-quality case id",
    ):
        load_answer_quality_cases(path)


def test_valid_payload_passes() -> None:
    result = evaluate_payload(
        case=make_case(),
        status_code=200,
        payload={
            "answer": (
                "למחיקת כרטיס לקוח יש לפעול "
                "לפי שלבי הנוהל."
            ),
            "grounded": True,
            "sources": [
                {
                    "title": (
                        "נוהל מחיקת כרטיס לקוח"
                    )
                }
            ],
        },
        latency_ms=100,
    )

    assert result.passed is True
    assert result.errors == ()


def test_missing_expected_source_fails() -> None:
    result = evaluate_payload(
        case=make_case(),
        status_code=200,
        payload={
            "answer": "יש לבצע מחיקה.",
            "grounded": True,
            "sources": [
                {
                    "title": "מסמך אחר"
                }
            ],
        },
        latency_ms=100,
    )

    assert result.passed is False
    assert (
        "Expected source was not returned"
        in result.errors
    )


def test_ungrounded_answer_fails() -> None:
    result = evaluate_payload(
        case=make_case(),
        status_code=200,
        payload={
            "answer": "יש לבצע מחיקת לקוח.",
            "grounded": False,
            "sources": [
                {
                    "title": (
                        "נוהל מחיקת כרטיס לקוח"
                    )
                }
            ],
        },
        latency_ms=100,
    )

    assert result.passed is False
    assert (
        "Answer is not marked as grounded"
        in result.errors
    )


def test_missing_required_all_term_fails() -> None:
    case = AnswerQualityCase(
        id="usdt",
        question="איך מוכרים USDT?",
        expected_source_titles=("נוהל USDT",),
        required_any_terms=(),
        required_all_terms=("USDT", "ERC-20"),
        forbidden_terms=(),
    )

    result = evaluate_payload(
        case=case,
        status_code=200,
        payload={
            "answer": "יש לבחור USDT.",
            "grounded": True,
            "sources": [
                {
                    "title": "נוהל USDT"
                }
            ],
        },
        latency_ms=100,
    )

    assert result.passed is False
    assert result.missing_required_all_terms == (
        "ERC-20",
    )


def test_forbidden_term_fails() -> None:
    case = AnswerQualityCase(
        id="forbidden",
        question="שאלה",
        expected_source_titles=("מסמך",),
        required_any_terms=(),
        required_all_terms=(),
        forbidden_terms=("מידע מומצא",),
    )

    result = evaluate_payload(
        case=case,
        status_code=200,
        payload={
            "answer": "זהו מידע מומצא.",
            "grounded": True,
            "sources": [
                {
                    "title": "מסמך"
                }
            ],
        },
        latency_ms=100,
    )

    assert result.passed is False
    assert result.matched_forbidden_terms == (
        "מידע מומצא",
    )
