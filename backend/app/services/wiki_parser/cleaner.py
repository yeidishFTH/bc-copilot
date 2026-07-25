from __future__ import annotations

import html
import re


_HTML_COMMENT_PATTERN = re.compile(
    r"<!--.*?-->",
    flags=re.DOTALL,
)

_HTML_TAG_PATTERN = re.compile(
    r"</?[a-zA-Z][^>]*>",
)

_MAGIC_WORD_PATTERN = re.compile(
    r"__[A-Z][A-Z0-9_]*__",
)

_WIKI_LINK_PATTERN = re.compile(
    r"\[\[(?:[^\[\]|]+\|)?([^\[\]|]+)\]\]"
)

_EXTERNAL_LINK_PATTERN = re.compile(
    r"\[(?:https?://\S+)(?:\s+([^\]]+))?\]"
)

_BOLD_ITALIC_PATTERN = re.compile(
    r"'{2,5}"
)

_MULTIPLE_SPACES_PATTERN = re.compile(
    r"[ \t]{2,}"
)

_MULTIPLE_BLANK_LINES_PATTERN = re.compile(
    r"\n{3,}"
)

_STRUCTURAL_TEMPLATE_NAMES = frozenset(
    {
        "metadata",
        "breadcrumb",
    }
)


def clean_wikitext_block(value: str) -> str:
    """
    Convert one MediaWiki content block into retrieval-friendly plain text.

    The cleaner deliberately removes only presentation and navigation noise.
    It preserves operational wording, lists, headings, table cell content and
    human-readable wiki-link labels.
    """

    if not isinstance(value, str):
        raise ValueError("value must be a string")

    cleaned = html.unescape(value)
    cleaned = _HTML_COMMENT_PATTERN.sub("", cleaned)
    cleaned = _remove_structural_templates(cleaned)
    cleaned = _MAGIC_WORD_PATTERN.sub("", cleaned)
    cleaned = _HTML_TAG_PATTERN.sub("", cleaned)
    cleaned = _WIKI_LINK_PATTERN.sub(r"\1", cleaned)
    cleaned = _EXTERNAL_LINK_PATTERN.sub(
        lambda match: match.group(1) or "",
        cleaned,
    )
    cleaned = _BOLD_ITALIC_PATTERN.sub("", cleaned)

    output_lines: list[str] = []

    for raw_line in cleaned.splitlines():
        line = _clean_line(raw_line)

        if line is None:
            continue

        output_lines.append(line)

    normalized = "\n".join(output_lines).strip()
    normalized = _MULTIPLE_BLANK_LINES_PATTERN.sub(
        "\n\n",
        normalized,
    )

    return normalized


def _remove_structural_templates(value: str) -> str:
    """
    Remove known structural templates while supporting nested braces.

    Other templates are intentionally preserved because their parameters may
    contain business knowledge that should not be discarded silently.
    """

    output: list[str] = []
    index = 0
    length = len(value)

    while index < length:
        if value.startswith("{{", index):
            template_end = _find_template_end(value, index)

            if template_end is not None:
                template = value[index + 2 : template_end - 2]
                template_name = (
                    template.split("|", 1)[0]
                    .strip()
                    .casefold()
                )

                if template_name in _STRUCTURAL_TEMPLATE_NAMES:
                    index = template_end
                    continue

        output.append(value[index])
        index += 1

    return "".join(output)


def _find_template_end(
    value: str,
    start: int,
) -> int | None:
    depth = 0
    index = start

    while index < len(value) - 1:
        pair = value[index : index + 2]

        if pair == "{{":
            depth += 1
            index += 2
            continue

        if pair == "}}":
            depth -= 1
            index += 2

            if depth == 0:
                return index

            continue

        index += 1

    return None


def _clean_line(raw_line: str) -> str | None:
    stripped = raw_line.strip()

    if not stripped:
        return ""

    if stripped in {
        "{|",
        "|}",
    }:
        return None

    if stripped.startswith("{|"):
        return None

    if stripped.startswith("|-"):
        return None

    if stripped.startswith("!"):
        cells = [
            cell.strip()
            for cell in stripped.lstrip("!").split("!!")
            if cell.strip()
        ]
        return " | ".join(cells) or None

    if stripped.startswith("|"):
        cells = [
            cell.strip()
            for cell in stripped.lstrip("|").split("||")
            if cell.strip()
        ]
        return " | ".join(cells) or None

    normalized = _MULTIPLE_SPACES_PATTERN.sub(
        " ",
        stripped,
    )

    return normalized
