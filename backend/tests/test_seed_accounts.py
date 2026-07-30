from app.cli.seed_accounts import (
    BRANCHES,
    INDIVIDUAL_ACCOUNTS,
    INITIAL_PASSWORD,
)
from app.db.models import AccountRole


def test_seed_contains_eleven_unique_branches() -> None:
    assert len(BRANCHES) == 11
    assert len(
        {
            branch.code
            for branch in BRANCHES
        }
    ) == 11
    assert len(
        {
            branch.email.lower()
            for branch in BRANCHES
        }
    ) == 11


def test_seed_contains_six_unique_individuals() -> None:
    assert len(INDIVIDUAL_ACCOUNTS) == 6

    emails = {
        email.lower()
        for email, _, _ in (
            INDIVIDUAL_ACCOUNTS
        )
    }

    assert emails == {
        "ohad@bitcoinchange.co.il",
        "miki@bitcoinchange.co.il",
        "lihi@bitcoinchange.co.il",
        "idan@bitcoinchange.co.il",
        "avi@bitcoinchange.co.il",
        "oren@bitcoinchange.co.il",
    }


def test_idan_is_initial_administrator() -> None:
    roles = {
        email: role
        for email, _, role in (
            INDIVIDUAL_ACCOUNTS
        )
    }

    assert (
        roles["idan@bitcoinchange.co.il"]
        is AccountRole.administrator
    )


def test_initial_password_matches_requested_value() -> None:
    assert INITIAL_PASSWORD == "12345678"
