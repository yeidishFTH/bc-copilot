from app.db.models import (
    AccountRole,
    AccountType,
    Branch,
    UserAccount,
)


def test_branch_model_table_name() -> None:
    assert Branch.__tablename__ == "branches"


def test_user_account_model_table_name() -> None:
    assert (
        UserAccount.__tablename__
        == "user_accounts"
    )


def test_account_type_values_are_stable() -> None:
    assert {
        item.value
        for item in AccountType
    } == {
        "branch",
        "individual",
    }


def test_account_role_values_are_stable() -> None:
    assert {
        item.value
        for item in AccountRole
    } == {
        "branch_user",
        "management",
        "administrator",
    }
