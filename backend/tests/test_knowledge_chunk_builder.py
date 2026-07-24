from __future__ import annotations

from app.services.wiki_parser import (
    KnowledgeChunkBuilder,
    WikiDocumentParser,
)


def parse_and_build(
    content: str,
):
    document = WikiDocumentParser().parse(content)
    return KnowledgeChunkBuilder().build(document)


def test_builder_creates_lead_chunk() -> None:
    chunks = parse_and_build(
        """
זהו טקסט הפתיחה.

== סעיף ==
תוכן הסעיף.
""".strip()
    )

    assert chunks[0].heading_path == ()
    assert chunks[0].content == "זהו טקסט הפתיחה."


def test_builder_creates_hierarchical_heading_paths() -> None:
    chunks = parse_and_build(
        """
= פתיחת סניף =
הנחיות כלליות.

== קופה ==
בדיקת קופה.

=== חריגים ===
דיווח למנהל.
""".strip()
    )

    assert [chunk.heading_path for chunk in chunks] == [
        ("פתיחת סניף",),
        ("פתיחת סניף", "קופה"),
        ("פתיחת סניף", "קופה", "חריגים"),
    ]


def test_builder_preserves_document_order() -> None:
    chunks = parse_and_build(
        """
== ראשון ==
אחד.

== שני ==
שתיים.

== שלישי ==
שלוש.
""".strip()
    )

    assert [chunk.content for chunk in chunks] == [
        "אחד.",
        "שתיים.",
        "שלוש.",
    ]


def test_builder_skips_empty_sections() -> None:
    chunks = parse_and_build(
        """
= פתיחת סניף =

== קופה ==
בדיקת קופה.
""".strip()
    )

    assert len(chunks) == 1
    assert chunks[0].heading_path == (
        "פתיחת סניף",
        "קופה",
    )


def test_builder_keeps_children_of_empty_sections() -> None:
    chunks = parse_and_build(
        """
= פתיחת סניף =
== קופה ==
=== חריגים ===
יש לדווח למנהל.
""".strip()
    )

    assert len(chunks) == 1
    assert chunks[0].heading_path == (
        "פתיחת סניף",
        "קופה",
        "חריגים",
    )


def test_builder_returns_empty_tuple_for_empty_document() -> None:
    chunks = parse_and_build("")

    assert chunks == ()


def test_drafts_do_not_contain_persistence_fields() -> None:
    chunks = parse_and_build(
        "== קופה ==\nבדיקת קופה."
    )

    chunk = chunks[0]

    assert chunk.token_count is None
    assert not hasattr(chunk, "id")
    assert not hasattr(chunk, "revision_id")
    assert not hasattr(chunk, "content_sha256")
