from pathlib import Path


def test_account_migration_defines_required_tables() -> None:
    path = Path(
        "alembic/versions/"
        "20260730_0005_accounts.py"
    )
    text = path.read_text(encoding="utf-8")

    assert 'revision: str = "20260730_0005"' in text
    assert (
        'down_revision: str | None = '
        '"20260729_0004"'
    ) in text
    assert '"branches"' in text
    assert '"user_accounts"' in text
    assert "must_change_password" in text
    assert "password_hash" in text
    assert "account_branch_consistency" in text
