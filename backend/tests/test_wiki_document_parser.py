from __future__ import annotations

import pytest

from app.services.wiki_parser import WikiDocumentParser


def test_parser_extracts_document_lead() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
טקסט פתיחה.

פסקה נוספת.
""".strip()
    )

    assert document.lead == "טקסט פתיחה.\n\nפסקה נוספת."
    assert document.sections == ()


def test_parser_extracts_section_body() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
= פתיחת סניף =

יש לפתוח את הסניף בזמן.
""".strip()
    )

    assert document.lead == ""
    assert len(document.sections) == 1

    section = document.sections[0]

    assert section.title == "פתיחת סניף"
    assert section.level == 1
    assert section.body == "יש לפתוח את הסניף בזמן."
    assert section.children == ()


def test_parser_builds_nested_section_tree() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
= פתיחת סניף =
טקסט ראשי.

== קופה ==
בדיקת הקופה.

=== חריגים ===
דיווח למנהל.

== כספת ==
בדיקת הכספת.
""".strip()
    )

    root = document.sections[0]

    assert root.title == "פתיחת סניף"
    assert [child.title for child in root.children] == [
        "קופה",
        "כספת",
    ]

    register = root.children[0]

    assert register.children[0].title == "חריגים"
    assert register.children[0].body == "דיווח למנהל."


def test_parser_handles_heading_level_jumps() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
= ראשי =
=== תת סעיף עמוק ===
תוכן.
""".strip()
    )

    root = document.sections[0]

    assert root.children[0].title == "תת סעיף עמוק"
    assert root.children[0].level == 3


def test_parser_returns_sibling_after_shallower_heading() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
= ראשי =
== ראשון ==
=== פנימי ===
== שני ==
""".strip()
    )

    root = document.sections[0]

    assert [child.title for child in root.children] == [
        "ראשון",
        "שני",
    ]
    assert root.children[0].children[0].title == "פנימי"


def test_parser_normalizes_heading_whitespace() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        "==   בדיקת    קופה   ==\nתוכן"
    )

    assert document.sections[0].title == "בדיקת קופה"


def test_parser_preserves_internal_body_formatting() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
== משימות ==
* משימה ראשונה
* משימה שנייה

{{תבנית|ערך=בדיקה}}
""".strip()
    )

    assert document.sections[0].body == (
        "* משימה ראשונה\n"
        "* משימה שנייה\n\n"
        "{{תבנית|ערך=בדיקה}}"
    )


def test_parser_treats_malformed_heading_as_content() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        """
== כותרת =
טקסט
""".strip()
    )

    assert document.lead == "== כותרת =\nטקסט"
    assert document.sections == ()


def test_parser_rejects_non_string_input() -> None:
    parser = WikiDocumentParser()

    with pytest.raises(
        ValueError,
        match="raw_wikitext must be a string",
    ):
        parser.parse(None)  # type: ignore[arg-type]


def test_parser_rejects_heading_with_extra_closing_marker() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        "== כותרת ===\nטקסט"
    )

    assert document.lead == "== כותרת ===\nטקסט"
    assert document.sections == ()


def test_parser_rejects_heading_above_level_six() -> None:
    parser = WikiDocumentParser()

    document = parser.parse(
        "======= כותרת =======\nטקסט"
    )

    assert document.lead == "======= כותרת =======\nטקסט"
    assert document.sections == ()
