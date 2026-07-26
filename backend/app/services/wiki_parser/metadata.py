from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class WikiDocumentMetadata:
    """Structured values extracted from the MediaWiki Metadata template."""

    status: str | None = None
    document_type: str | None = None
    portal: str | None = None
    category: str | None = None
    audience: tuple[str, ...] = ()
    owner: str | None = None
    responsible_department: str | None = None
    updated_on: date | None = None
    version: str | None = None


class WikiMetadataParser:
    """Extract the first top-level {{Metadata ...}} template."""

    _START_PATTERN = re.compile(
        r"\{\{\s*Metadata\b",
        flags=re.IGNORECASE,
    )

    _FIELD_MAP = {
        "סטטוס": "status",
        "סוג מסמך": "document_type",
        "פורטל": "portal",
        "קטגוריה": "category",
        "קהל יעד": "audience",
        "בעלים": "owner",
        "מחלקה אחראית": "responsible_department",
        "עדכון אחרון": "updated_on",
        "גרסה": "version",
    }

    _DATE_FORMATS = (
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
    )

    def parse(
        self,
        raw_wikitext: str,
    ) -> WikiDocumentMetadata:
        if not isinstance(raw_wikitext, str):
            raise ValueError(
                "raw_wikitext must be a string"
            )

        template = self._extract_template(raw_wikitext)

        if template is None:
            return WikiDocumentMetadata()

        fields = self._parse_fields(template)

        return WikiDocumentMetadata(
            status=self._optional_value(
                fields.get("status")
            ),
            document_type=self._optional_value(
                fields.get("document_type")
            ),
            portal=self._optional_value(
                fields.get("portal")
            ),
            category=self._optional_value(
                fields.get("category")
            ),
            audience=self._parse_audience(
                fields.get("audience")
            ),
            owner=self._optional_value(
                fields.get("owner")
            ),
            responsible_department=self._optional_value(
                fields.get("responsible_department")
            ),
            updated_on=self._parse_date(
                fields.get("updated_on")
            ),
            version=self._optional_value(
                fields.get("version")
            ),
        )

    def _extract_template(
        self,
        raw_wikitext: str,
    ) -> str | None:
        match = self._START_PATTERN.search(
            raw_wikitext
        )

        if match is None:
            return None

        start = match.start()
        cursor = start
        depth = 0

        while cursor < len(raw_wikitext) - 1:
            pair = raw_wikitext[
                cursor:cursor + 2
            ]

            if pair == "{{":
                depth += 1
                cursor += 2
                continue

            if pair == "}}":
                depth -= 1
                cursor += 2

                if depth == 0:
                    return raw_wikitext[
                        start:cursor
                    ]

                continue

            cursor += 1

        return None

    def _parse_fields(
        self,
        template: str,
    ) -> dict[str, str]:
        inner = template[2:-2]
        lines = inner.splitlines()

        fields: dict[str, str] = {}
        current_key: str | None = None
        current_value: list[str] = []

        for raw_line in lines[1:]:
            line = raw_line.strip()

            if line.startswith("|"):
                if current_key is not None:
                    fields[current_key] = (
                        "\n".join(current_value)
                        .strip()
                    )

                field = line[1:]

                if "=" not in field:
                    current_key = None
                    current_value = []
                    continue

                raw_key, raw_value = field.split(
                    "=",
                    1,
                )
                normalized_key = (
                    " ".join(raw_key.split())
                )
                mapped_key = self._FIELD_MAP.get(
                    normalized_key
                )

                current_key = mapped_key
                current_value = (
                    [raw_value.strip()]
                    if mapped_key is not None
                    else []
                )

                continue

            if (
                current_key is not None
                and line
            ):
                current_value.append(line)

        if current_key is not None:
            fields[current_key] = (
                "\n".join(current_value)
                .strip()
            )

        return fields

    @staticmethod
    def _optional_value(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = " ".join(value.split())

        return normalized or None

    @classmethod
    def _parse_audience(
        cls,
        value: str | None,
    ) -> tuple[str, ...]:
        normalized = cls._optional_value(value)

        if normalized is None:
            return ()

        values: list[str] = []

        for part in re.split(
            r"[,،;|]+",
            normalized,
        ):
            item = " ".join(part.split())

            if item and item not in values:
                values.append(item)

        return tuple(values)

    @classmethod
    def _parse_date(
        cls,
        value: str | None,
    ) -> date | None:
        normalized = cls._optional_value(value)

        if normalized is None:
            return None

        for date_format in cls._DATE_FORMATS:
            try:
                return datetime.strptime(
                    normalized,
                    date_format,
                ).date()
            except ValueError:
                continue

        return None
