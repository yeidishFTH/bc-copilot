from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.wiki_parser.ast import DocumentNode, SectionNode


_HEADING_PATTERN = re.compile(
    r"^(?P<opening>={1,6})"
    r"(?![=])"
    r"[ \\t]*"
    r"(?P<title>.*?)"
    r"[ \\t]*"
    r"(?P<closing>={1,6})"
    r"[ \\t]*$"
)


@dataclass(slots=True)
class _SectionBuilder:
    """Internal mutable representation used while parsing."""

    title: str
    level: int
    body_lines: list[str] = field(default_factory=list)
    children: list["_SectionBuilder"] = field(default_factory=list)

    def freeze(self) -> SectionNode:
        return SectionNode(
            title=self.title,
            level=self.level,
            body=_normalize_block(self.body_lines),
            children=tuple(child.freeze() for child in self.children),
        )


class WikiDocumentParser:
    """
    Parse MediaWiki headings into a hierarchical document tree.

    This parser intentionally focuses on document structure. Parsing links,
    templates, tables and categories will be added as separate extensions.
    """

    def parse(self, raw_wikitext: str) -> DocumentNode:
        if not isinstance(raw_wikitext, str):
            raise ValueError("raw_wikitext must be a string")

        lead_lines: list[str] = []
        root_sections: list[_SectionBuilder] = []
        section_stack: list[_SectionBuilder] = []
        current_section: _SectionBuilder | None = None

        for line in raw_wikitext.splitlines():
            heading = self._parse_heading(line)

            if heading is None:
                if current_section is None:
                    lead_lines.append(line)
                else:
                    current_section.body_lines.append(line)

                continue

            title, level = heading
            section = _SectionBuilder(
                title=title,
                level=level,
            )

            while (
                section_stack
                and section_stack[-1].level >= section.level
            ):
                section_stack.pop()

            if section_stack:
                section_stack[-1].children.append(section)
            else:
                root_sections.append(section)

            section_stack.append(section)
            current_section = section

        return DocumentNode(
            lead=_normalize_block(lead_lines),
            sections=tuple(
                section.freeze()
                for section in root_sections
            ),
        )

    @staticmethod
    def _parse_heading(
        line: str,
    ) -> tuple[str, int] | None:
        match = _HEADING_PATTERN.fullmatch(line)

        if match is None:
            return None

        opening = match.group("opening")
        closing = match.group("closing")

        if len(opening) != len(closing):
            return None

        title = _normalize_inline(match.group("title"))

        if not title:
            return None

        return title, len(opening)


def _normalize_inline(value: str) -> str:
    """Collapse insignificant whitespace inside a heading."""

    return " ".join(value.split())


def _normalize_block(lines: list[str]) -> str:
    """
    Remove surrounding blank lines while preserving internal formatting.

    Content inside lists, templates and tables is kept unchanged for future
    specialized AST parsers.
    """

    start = 0
    end = len(lines)

    while start < end and not lines[start].strip():
        start += 1

    while end > start and not lines[end - 1].strip():
        end -= 1

    return "\n".join(lines[start:end])
