from pathlib import Path


def test_auth_session_migration_contains_required_fields() -> None:
    path = Path(
        "alembic/versions/"
        "20260730_0006_auth_sessions.py"
    )
    text = path.read_text(encoding="utf-8")

    assert 'revision: str = "20260730_0006"' in text
    assert (
        'down_revision: str | None = '
        '"20260730_0005"'
    ) in text
    assert '"auth_sessions"' in text
    assert '"token_hash"' in text
    assert '"expires_at"' in text
    assert '"revoked_at"' in text
    assert '"account_id"' in text
