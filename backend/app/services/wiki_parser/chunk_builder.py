from __future__ import annotations

from app.services.knowledge.models import KnowledgeChunkDraft
from app.services.wiki_parser.ast import DocumentNode, SectionNode


class KnowledgeChunkBuilder:
    """
    Build semantically structured chunks from a parsed wiki document.

    One draft is created for the lead and for each non-empty section body.
    Empty container sections are skipped while their descendants are kept.
    """

    def build(
        self,
        document: DocumentNode,
    ) -> tuple[KnowledgeChunkDraft, ...]:
        chunks: list[KnowledgeChunkDraft] = []

        lead = document.lead.strip()

        if lead:
            chunks.append(
                KnowledgeChunkDraft(
                    heading_path=(),
                    content=lead,
                )
            )

        for section in document.sections:
            self._append_section_chunks(
                section=section,
                parent_path=(),
                chunks=chunks,
            )

        return tuple(chunks)

    def _append_section_chunks(
        self,
        *,
        section: SectionNode,
        parent_path: tuple[str, ...],
        chunks: list[KnowledgeChunkDraft],
    ) -> None:
        heading_path = (*parent_path, section.title)
        content = section.body.strip()

        if content:
            chunks.append(
                KnowledgeChunkDraft(
                    heading_path=heading_path,
                    content=content,
                )
            )

        for child in section.children:
            self._append_section_chunks(
                section=child,
                parent_path=heading_path,
                chunks=chunks,
            )
