from __future__ import annotations

from app.services.wiki_parser import (
    WikiMetadataParser,
)


def test_parse_canonical_access_roles() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| קהל יעד = נציגים
| הרשאות גישה =
  branch_user,
  management,
  administrator
}}
"""
    )

    assert result.audience == ("נציגים",)
    assert result.access_roles == (
        "branch_user",
        "management",
        "administrator",
    )


def test_parse_hebrew_access_role_aliases() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| תפקידי גישה =
  סניף |
  הנהלה |
  מנהל מערכת
}}
"""
    )

    assert result.access_roles == (
        "branch_user",
        "management",
        "administrator",
    )


def test_parse_english_access_role_field() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| Access Roles =
  branch user;
  management;
  admin
}}
"""
    )

    assert result.access_roles == (
        "branch_user",
        "management",
        "administrator",
    )


def test_parse_access_roles_removes_duplicates() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| הרשאות גישה =
  סניף,
  branch_user,
  הנהלה,
  management,
  מנהל מערכת,
  administrator
}}
"""
    )

    assert result.access_roles == (
        "branch_user",
        "management",
        "administrator",
    )


def test_missing_access_roles_returns_empty_tuple() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| סוג מסמך = נוהל
| קהל יעד = נציגים
}}
"""
    )

    assert result.access_roles == ()


def test_unknown_access_roles_are_ignored() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| הרשאות גישה =
  unknown_role,
  תפקיד לא מוכר,
  management
}}
"""
    )

    assert result.access_roles == (
        "management",
    )


def test_audience_does_not_implicitly_set_access_roles() -> None:
    result = WikiMetadataParser().parse(
        """
{{Metadata
| קהל יעד =
  מנהלי סניפים,
  הנהלה
}}
"""
    )

    assert result.audience == (
        "מנהלי סניפים",
        "הנהלה",
    )
    assert result.access_roles == ()
