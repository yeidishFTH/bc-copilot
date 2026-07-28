from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class CitationSource(Protocol):
    """Source information required for claim mapping."""

    index: int
    title: str
    heading_path: tuple[str, ...]
    chunk_id: str


@dataclass(frozen=True, slots=True)
class CitationClaim:
    """One answer claim mapped to its supporting sources."""

    index: int
    text: str
    source_indexes: tuple[int, ...]
    source_chunk_ids: tuple[str, ...]
    source_titles: tuple[str, ...]
    source_headings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CitationMapping:
    """Claim-level citation mapping for one answer."""

    claims: tuple[CitationClaim, ...]
    cited_source_indexes: tuple[int, ...]
    uncited_source_indexes: tuple[int, ...]

    @property
    def claim_count(self) -> int:
        return len(self.claims)


class ClaimCitationMapper:
    """
    Convert inline [SOURCE N] markers into structured claim mappings.

    Version 1 treats each Markdown paragraph or list item containing at
    least one citation as an independently supported claim.
    """

    _CITATION_PATTERN = re.compile(
        r"\[SOURCE\s+(\d+)\]",
        flags=re.IGNORECASE,
    )

    _LIST_ITEM_PATTERN = re.compile(
        r"^\s*(?:[-*+]|(?:\d+)[.)])\s+"
    )

    _MARKDOWN_PREFIX_PATTERN = re.compile(
        r"^\s*(?:#{1,6}\s+|>\s*)"
    )

    def map(
        self,
        answer: str,
        *,
        sources: Sequence[CitationSource],
    ) -> CitationMapping:
        normalized_answer = self._normalize_answer(answer)
        source_map = {
            source.index: source
            for source in sources
        }

        claims: list[CitationClaim] = []
        cited_indexes: list[int] = []

        for raw_claim in self._extract_claim_units(
            normalized_answer
        ):
            source_indexes = self._extract_source_indexes(
                raw_claim,
                available_indexes=frozenset(source_map),
            )

            if not source_indexes:
                continue

            claim_text = self._clean_claim_text(
                raw_claim
            )

            if not claim_text:
                continue

            claim_sources = tuple(
                source_map[index]
                for index in source_indexes
            )

            claims.append(
                CitationClaim(
                    index=len(claims) + 1,
                    text=claim_text,
                    source_indexes=source_indexes,
                    source_chunk_ids=tuple(
                        source.chunk_id
                        for source in claim_sources
                    ),
                    source_titles=tuple(
                        source.title
                        for source in claim_sources
                    ),
                    source_headings=tuple(
                        self._format_heading(
                            source.heading_path
                        )
                        for source in claim_sources
                    ),
                )
            )

            cited_indexes.extend(source_indexes)

        unique_cited = tuple(
            dict.fromkeys(cited_indexes)
        )
        cited_set = set(unique_cited)

        uncited_indexes = tuple(
            source.index
            for source in sources
            if source.index not in cited_set
        )

        return CitationMapping(
            claims=tuple(claims),
            cited_source_indexes=unique_cited,
            uncited_source_indexes=uncited_indexes,
        )

    @classmethod
    def _extract_claim_units(
        cls,
        answer: str,
    ) -> tuple[str, ...]:
        units: list[str] = []

        for paragraph in re.split(
            r"\n\s*\n",
            answer,
        ):
            normalized_paragraph = (
                paragraph.strip()
            )

            if not normalized_paragraph:
                continue

            lines = [
                line.strip()
                for line in normalized_paragraph.splitlines()
                if line.strip()
            ]

            list_lines = [
                line
                for line in lines
                if cls._LIST_ITEM_PATTERN.match(line)
            ]

            if list_lines:
                units.extend(list_lines)

                remaining_lines = [
                    line
                    for line in lines
                    if not cls._LIST_ITEM_PATTERN.match(
                        line
                    )
                ]

                if remaining_lines:
                    units.append(
                        " ".join(remaining_lines)
                    )

                continue

            units.append(" ".join(lines))

        return tuple(units)

    @classmethod
    def _extract_source_indexes(
        cls,
        value: str,
        *,
        available_indexes: frozenset[int],
    ) -> tuple[int, ...]:
        indexes = (
            int(match.group(1))
            for match in cls._CITATION_PATTERN.finditer(
                value
            )
        )

        return tuple(
            dict.fromkeys(
                index
                for index in indexes
                if index in available_indexes
            )
        )

    @classmethod
    def _clean_claim_text(
        cls,
        value: str,
    ) -> str:
        without_citations = cls._CITATION_PATTERN.sub(
            "",
            value,
        )
        without_prefix = cls._MARKDOWN_PREFIX_PATTERN.sub(
            "",
            without_citations,
        )
        without_list_marker = cls._LIST_ITEM_PATTERN.sub(
            "",
            without_prefix,
        )

        return " ".join(
            without_list_marker.split()
        ).strip()

    @staticmethod
    def _format_heading(
        heading_path: tuple[str, ...],
    ) -> str:
        if not heading_path:
            return "פתיח העמוד"

        return " > ".join(heading_path)

    @staticmethod
    def _normalize_answer(
        answer: str,
    ) -> str:
        if not isinstance(answer, str):
            raise ValueError(
                "answer must be a string"
            )

        normalized = answer.strip()

        if not normalized:
            raise ValueError(
                "answer cannot be empty"
            )

        return normalized
