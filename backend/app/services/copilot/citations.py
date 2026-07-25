from __future__ import annotations

import re
from collections.abc import Sequence


class CitationValidationError(RuntimeError):
    """Raised when a generated answer contains invalid source citations."""


class CitationValidator:
    """Validate source references produced by a text-generation model."""

    _CITATION_PATTERN = re.compile(
        r"\[SOURCE\s+(\d+)\]",
        flags=re.IGNORECASE,
    )

    def validate(
        self,
        answer: str,
        *,
        available_source_indexes: Sequence[int],
        require_citation: bool = True,
    ) -> tuple[int, ...]:
        if not isinstance(answer, str):
            raise CitationValidationError(
                "generated answer must be a string"
            )

        available = self._normalize_available_indexes(
            available_source_indexes
        )
        cited = self.extract(answer)

        if require_citation and available and not cited:
            raise CitationValidationError(
                "generated answer does not cite any available source"
            )

        invalid = tuple(
            index
            for index in cited
            if index not in available
        )

        if invalid:
            invalid_text = ", ".join(
                str(index)
                for index in invalid
            )
            available_text = ", ".join(
                str(index)
                for index in available
            )

            raise CitationValidationError(
                "generated answer cites unavailable source indexes: "
                f"{invalid_text}; available indexes: {available_text}"
            )

        return cited

    def extract(
        self,
        answer: str,
    ) -> tuple[int, ...]:
        if not isinstance(answer, str):
            raise CitationValidationError(
                "generated answer must be a string"
            )

        indexes: list[int] = []

        for match in self._CITATION_PATTERN.finditer(answer):
            index = int(match.group(1))

            if index not in indexes:
                indexes.append(index)

        return tuple(indexes)

    @staticmethod
    def _normalize_available_indexes(
        indexes: Sequence[int],
    ) -> tuple[int, ...]:
        normalized: list[int] = []

        for index in indexes:
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 1
            ):
                raise ValueError(
                    "available_source_indexes must contain "
                    "positive integers"
                )

            if index not in normalized:
                normalized.append(index)

        return tuple(normalized)
