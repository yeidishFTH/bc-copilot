from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Iterable, Mapping


BRANCH_USER: Final = "branch_user"
MANAGEMENT: Final = "management"
ADMINISTRATOR: Final = "administrator"

VALID_ACCESS_ROLES: Final[frozenset[str]] = frozenset(
    {
        BRANCH_USER,
        MANAGEMENT,
        ADMINISTRATOR,
    }
)

OPEN_ACCESS: Final[tuple[str, ...]] = ()

ALL_WORKSPACE_ROLES: Final[tuple[str, ...]] = (
    BRANCH_USER,
    MANAGEMENT,
    ADMINISTRATOR,
)

MANAGEMENT_AND_ADMIN: Final[tuple[str, ...]] = (
    MANAGEMENT,
    ADMINISTRATOR,
)

ADMIN_ONLY: Final[tuple[str, ...]] = (
    ADMINISTRATOR,
)


@dataclass(frozen=True, slots=True)
class AccessPolicyRecommendation:
    portal: str | None
    access_roles: tuple[str, ...] | None
    requires_manual_review: bool
    reason: str


_PORTAL_DEFAULTS: Final[
    dict[str, tuple[str, ...] | None]
] = {
    "תפעול סניף": ALL_WORKSPACE_ROLES,
    "לקוחות": ALL_WORKSPACE_ROLES,
    "עובדים והדרכה": ALL_WORKSPACE_ROLES,
    "סניפים": ALL_WORKSPACE_ROLES,
    "מלאי וציוד": ALL_WORKSPACE_ROLES,
    "טפסים": ALL_WORKSPACE_ROLES,
    "ידע ארגוני": ALL_WORKSPACE_ROLES,

    "הנהלה": MANAGEMENT_AND_ADMIN,

    "ציות ורגולציה": None,
    "מערכות מידע": None,
    "Back Office": None,
    "משאבי אנוש": None,
    "שיווק": None,
    "פורטלים": None,
    "Sandbox": None,
}

PORTAL_DEFAULT_ACCESS_ROLES: Final[
    Mapping[str, tuple[str, ...] | None]
] = MappingProxyType(_PORTAL_DEFAULTS)


def normalize_access_role(role: str) -> str:
    if not isinstance(role, str):
        raise ValueError(
            "access role must be a string"
        )

    normalized = role.strip().casefold()

    if normalized not in VALID_ACCESS_ROLES:
        raise ValueError(
            f"unknown access role: {role!r}"
        )

    return normalized


def normalize_access_roles(
    roles: Iterable[str],
) -> tuple[str, ...]:
    normalized: list[str] = []

    for role in roles:
        canonical = normalize_access_role(role)

        if canonical not in normalized:
            normalized.append(canonical)

    return tuple(normalized)


def is_role_allowed(
    access_roles: Iterable[str],
    role: str | None,
) -> bool:
    normalized_roles = normalize_access_roles(
        access_roles
    )

    if not normalized_roles:
        return True

    if role is None:
        return False

    return (
        normalize_access_role(role)
        in normalized_roles
    )


def recommend_access_for_portal(
    portal: str | None,
) -> AccessPolicyRecommendation:
    normalized_portal = (
        portal.strip()
        if isinstance(portal, str)
        else ""
    )

    if not normalized_portal:
        return AccessPolicyRecommendation(
            portal=None,
            access_roles=None,
            requires_manual_review=True,
            reason=(
                "The document has no recognized portal "
                "and must be reviewed manually."
            ),
        )

    if normalized_portal not in PORTAL_DEFAULT_ACCESS_ROLES:
        return AccessPolicyRecommendation(
            portal=normalized_portal,
            access_roles=None,
            requires_manual_review=True,
            reason=(
                "The portal is not present in "
                "Knowledge Access Policy v1."
            ),
        )

    roles = PORTAL_DEFAULT_ACCESS_ROLES[
        normalized_portal
    ]

    if roles is None:
        return AccessPolicyRecommendation(
            portal=normalized_portal,
            access_roles=None,
            requires_manual_review=True,
            reason=(
                "This portal may contain mixed or "
                "sensitive knowledge and requires "
                "document-level review."
            ),
        )

    return AccessPolicyRecommendation(
        portal=normalized_portal,
        access_roles=roles,
        requires_manual_review=False,
        reason=(
            "Recommendation derived from the "
            "approved portal policy."
        ),
    )
