from __future__ import annotations

import pytest

from app.services.copilot import (
    CitationValidationError,
    CitationValidator,
)


def test_validator_accepts_available_sources() -> None:
    validator = CitationValidator()

    cited = validator.validate(
        (
            "יש לקבל את הבקשה מהמייל הרשום "
            "[SOURCE 1], ולאחר מכן לבצע בדיקת ציות "
            "[SOURCE 2]."
        ),
        available_source_indexes=(1, 2, 3),
    )

    assert cited == (1, 2)


def test_validator_removes_duplicate_citation_indexes() -> None:
    validator = CitationValidator()

    cited = validator.validate(
        "[SOURCE 1] תוכן נוסף [source 1]",
        available_source_indexes=(1,),
    )

    assert cited == (1,)


def test_validator_rejects_missing_citations() -> None:
    validator = CitationValidator()

    with pytest.raises(
        CitationValidationError,
        match="does not cite",
    ):
        validator.validate(
            "יש לבצע את הפעולה לפי הנוהל.",
            available_source_indexes=(1, 2),
        )


def test_validator_can_allow_answer_without_citation() -> None:
    validator = CitationValidator()

    cited = validator.validate(
        "אין ציטוט.",
        available_source_indexes=(1,),
        require_citation=False,
    )

    assert cited == ()


def test_validator_rejects_unknown_source() -> None:
    validator = CitationValidator()

    with pytest.raises(
        CitationValidationError,
        match="unavailable source indexes: 7",
    ):
        validator.validate(
            "יש לבצע את הפעולה. [SOURCE 7]",
            available_source_indexes=(1, 2, 3),
        )


def test_validator_rejects_zero_source_index() -> None:
    validator = CitationValidator()

    with pytest.raises(
        CitationValidationError,
        match="unavailable source indexes: 0",
    ):
        validator.validate(
            "[SOURCE 0]",
            available_source_indexes=(1,),
        )


@pytest.mark.parametrize(
    "indexes",
    [
        (0,),
        (-1,),
        (True,),
        ("1",),
    ],
)
def test_validator_rejects_invalid_available_indexes(
    indexes: tuple[object, ...],
) -> None:
    validator = CitationValidator()

    with pytest.raises(
        ValueError,
        match="positive integers",
    ):
        validator.validate(
            "[SOURCE 1]",
            available_source_indexes=indexes,  # type: ignore[arg-type]
        )
