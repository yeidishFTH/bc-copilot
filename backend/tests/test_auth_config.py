from app.core.config import Settings


def test_authentication_defaults() -> None:
    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.auth_cookie_name
        == "bc_workspace_session"
    )
    assert settings.auth_session_hours == 12
    assert not settings.auth_cookie_secure
    assert settings.auth_cookie_samesite == "lax"
    assert settings.auth_max_failed_attempts == 5
    assert settings.auth_lock_minutes == 15
