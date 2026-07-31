from __future__ import annotations

import pytest

from app.services.knowledge.access_policy import (
    ADMINISTRATOR,
    ADMIN_ONLY,
    ALL_WORKSPACE_ROLES,
    BRANCH_USER,
    MANAGEMENT,
    MANAGEMENT_AND_ADMIN,
    OPEN_ACCESS,
    PORTAL_DEFAULT_ACCESS_ROLES,
    VALID_ACCESS_ROLES,
    is_role_allowed,
    normalize_access_role,
    normalize_access_roles,
    recommend_access_for_portal,
)


def test_policy_uses_current_account_roles() -> None:
    assert VALID_ACCESS_ROLES == {
        BRANCH_USER,
        MANAGEMENT,
        ADMINISTRATOR,
    }


def test_open_access_allows_all_roles() -> None:
    assert OPEN_ACCESS == ()

    for role in VALID_ACCESS_ROLES:
        assert is_role_allowed(
            OPEN_ACCESS,
            role,
        )


def test_open_access_allows_missing_role() -> None:
    assert is_role_allowed(
        OPEN_ACCESS,
        None,
    )


def test_restricted_access_requires_matching_role() -> None:
    roles = (
        MANAGEMENT,
        ADMINISTRATOR,
    )

    assert not is_role_allowed(
        roles,
        None,
    )
    assert not is_role_allowed(
        roles,
        BRANCH_USER,
    )
    assert is_role_allowed(
        roles,
        MANAGEMENT,
    )
    assert is_role_allowed(
        roles,
        ADMINISTRATOR,
    )


def test_roles_are_not_implicitly_hierarchical() -> None:
    assert not is_role_allowed(
        (MANAGEMENT,),
        ADMINISTRATOR,
    )

    assert is_role_allowed(
        (
            MANAGEMENT,
            ADMINISTRATOR,
        ),
        ADMINISTRATOR,
    )


def test_normalize_access_role() -> None:
    assert (
        normalize_access_role(
            " MANAGEMENT "
        )
        == MANAGEMENT
    )


def test_normalize_access_roles_removes_duplicates() -> None:
    assert normalize_access_roles(
        (
            " management ",
            "MANAGEMENT",
            "administrator",
        )
    ) == (
        MANAGEMENT,
        ADMINISTRATOR,
    )


@pytest.mark.parametrize(
    "role",
    [
        "",
        "unknown",
        "compliance",
        "human_resources",
        "back_office",
    ],
)
def test_unknown_role_is_rejected(
    role: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="unknown access role",
    ):
        normalize_access_role(role)


@pytest.mark.parametrize(
    "portal",
    [
        "תפעול סניף",
        "לקוחות",
        "עובדים והדרכה",
        "סניפים",
        "מלאי וציוד",
        "טפסים",
        "ידע ארגוני",
    ],
)
def test_operational_portals_recommend_all_roles(
    portal: str,
) -> None:
    recommendation = (
        recommend_access_for_portal(
            portal
        )
    )

    assert recommendation.portal == portal
    assert (
        recommendation.access_roles
        == ALL_WORKSPACE_ROLES
    )
    assert (
        recommendation.requires_manual_review
        is False
    )


def test_management_portal_recommends_management_and_admin() -> None:
    recommendation = (
        recommend_access_for_portal(
            "הנהלה"
        )
    )

    assert (
        recommendation.access_roles
        == MANAGEMENT_AND_ADMIN
    )
    assert (
        recommendation.requires_manual_review
        is False
    )


@pytest.mark.parametrize(
    "portal",
    [
        "ציות ורגולציה",
        "מערכות מידע",
        "Back Office",
        "משאבי אנוש",
        "שיווק",
        "פורטלים",
        "Sandbox",
    ],
)
def test_sensitive_portals_require_manual_review(
    portal: str,
) -> None:
    recommendation = (
        recommend_access_for_portal(
            portal
        )
    )

    assert recommendation.access_roles is None
    assert (
        recommendation.requires_manual_review
        is True
    )


@pytest.mark.parametrize(
    "portal",
    [
        None,
        "",
        "   ",
        "פורטל לא מוכר",
    ],
)
def test_missing_or_unknown_portal_requires_review(
    portal: str | None,
) -> None:
    recommendation = (
        recommend_access_for_portal(
            portal
        )
    )

    assert recommendation.access_roles is None
    assert (
        recommendation.requires_manual_review
        is True
    )


def test_policy_profiles_are_consistent() -> None:
    assert ALL_WORKSPACE_ROLES == (
        BRANCH_USER,
        MANAGEMENT,
        ADMINISTRATOR,
    )

    assert MANAGEMENT_AND_ADMIN == (
        MANAGEMENT,
        ADMINISTRATOR,
    )

    assert ADMIN_ONLY == (
        ADMINISTRATOR,
    )


def test_portal_mapping_is_read_only() -> None:
    with pytest.raises(TypeError):
        PORTAL_DEFAULT_ACCESS_ROLES[
            "הנהלה"
        ] = OPEN_ACCESS  # type: ignore[index]
