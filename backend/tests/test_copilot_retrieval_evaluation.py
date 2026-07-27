from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli.evaluate_copilot_retrieval import (
    RankedResult,
    accuracy_percentage,
    first_matching_position,
    load_golden_questions,
)


def ranked(
    position: int,
    title: str,
) -> RankedResult:
    return RankedResult(
        position=position,
        title=title,
        heading_path=(),
        chunk_id=f"chunk-{position}",
        rank=10.0 - position,
    )


def test_loads_valid_golden_dataset(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "questions.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "id": "delete",
                    "question": "איך מוחקים לקוח?",
                    "expected_titles": [
                        "נוהל מחיקת כרטיס לקוח"
                    ],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    questions = load_golden_questions(dataset)

    assert len(questions) == 1
    assert questions[0].id == "delete"
    assert questions[0].expected_titles == (
        "נוהל מחיקת כרטיס לקוח",
    )


def test_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "questions.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "id": "same",
                    "question": "שאלה ראשונה",
                    "expected_titles": ["מסמך א"],
                },
                {
                    "id": "same",
                    "question": "שאלה שנייה",
                    "expected_titles": ["מסמך ב"],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate golden question id",
    ):
        load_golden_questions(dataset)


def test_preferred_title_must_be_expected(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "questions.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "id": "atm",
                    "question": "כספומט",
                    "expected_titles": ["מסמך א"],
                    "preferred_title": "מסמך ב",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="must also appear",
    ):
        load_golden_questions(dataset)


def test_finds_first_expected_position() -> None:
    results = (
        ranked(1, "מסמך אחר"),
        ranked(2, "נוהל סגירת יום"),
        ranked(3, "מסמך נוסף"),
    )

    position = first_matching_position(
        results,
        ("נוהל סגירת יום",),
    )

    assert position == 2


def test_title_matching_normalizes_case_and_spaces() -> None:
    results = (
        ranked(
            1,
            "  מערכת   Salesforce  ",
        ),
    )

    position = first_matching_position(
        results,
        ("מערכת salesforce",),
    )

    assert position == 1


def test_missing_expected_title_returns_none() -> None:
    position = first_matching_position(
        (ranked(1, "מסמך אחר"),),
        ("מסמך צפוי",),
    )

    assert position is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([True, True, False], 66.67),
        ([True, True], 100.0),
        ([False, False], 0.0),
        ([], 0.0),
    ],
)
def test_accuracy_percentage(
    values: list[bool],
    expected: float,
) -> None:
    assert accuracy_percentage(values) == expected
