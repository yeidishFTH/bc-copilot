from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParagraphNode:
    """A plain text block in a parsed wiki document."""

    text: str


@dataclass(frozen=True, slots=True)
class SectionNode:
    """A hierarchical MediaWiki section."""

    title: str
    level: int
    body: str
    children: tuple["SectionNode", ...] = field(default_factory=tuple)

    def walk(self) -> Iterator["SectionNode"]:
        """Yield this section and every descendant in document order."""

        yield self

        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True, slots=True)
class DocumentNode:
    """Parsed MediaWiki document root."""

    lead: str
    sections: tuple[SectionNode, ...] = field(default_factory=tuple)

    def walk_sections(self) -> Iterator[SectionNode]:
        """Yield every section in document order."""

        for section in self.sections:
            yield from section.walk()
