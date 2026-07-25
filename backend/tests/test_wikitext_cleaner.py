from __future__ import annotations

import pytest

from app.services.wiki_parser import clean_wikitext_block


def test_cleaner_removes_portal_presentation_noise() -> None:
    raw = """
<div dir="rtl" lang="he" class="portal-shell">
__NOTOC__
{{Metadata
|סטטוס=טיוטה
|סוג מסמך=נוהל
|פורטל=ציות ורגולציה
}}
{{Breadcrumb
|פורטל=ציות ורגולציה
|קטגוריה=לקוחות
}}

'''מטרת הנוהל'''

יש לבצע [[זיהוי לקוח|זיהוי ואימות]] לפני השירות.
</div>
"""

    assert clean_wikitext_block(raw) == (
        "מטרת הנוהל\n\n"
        "יש לבצע זיהוי ואימות לפני השירות."
    )


def test_cleaner_preserves_list_content() -> None:
    raw = """
# יש לזהות את הלקוח.
# יש לבדוק תעודה מזהה.
* יש לתעד את הבדיקה.
"""

    assert clean_wikitext_block(raw) == (
        "# יש לזהות את הלקוח.\n"
        "# יש לבדוק תעודה מזהה.\n"
        "* יש לתעד את הבדיקה."
    )


def test_cleaner_converts_wikitable_cells_to_readable_text() -> None:
    raw = """
{| class="wikitable"
! שלב !! אחריות
|-
| זיהוי לקוח || נציג
|-
| בדיקת ציות || מנהל
|}
"""

    assert clean_wikitext_block(raw) == (
        "שלב | אחריות\n"
        "זיהוי לקוח | נציג\n"
        "בדיקת ציות | מנהל"
    )


def test_cleaner_preserves_unknown_template_content() -> None:
    raw = "{{Important|יש לפנות למחלקת ציות}}"

    assert clean_wikitext_block(raw) == raw


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        [],
    ],
)
def test_cleaner_rejects_non_string_values(
    value: object,
) -> None:
    with pytest.raises(ValueError, match="value must be a string"):
        clean_wikitext_block(value)  # type: ignore[arg-type]
