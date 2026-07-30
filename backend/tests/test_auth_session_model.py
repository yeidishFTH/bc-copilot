from app.db.models import (
    AuthSession,
    UserAccount,
)


def test_auth_session_table_name() -> None:
    assert (
        AuthSession.__tablename__
        == "auth_sessions"
    )


def test_user_account_has_session_relationship() -> None:
    relationship = (
        UserAccount.__mapper__.relationships[
            "sessions"
        ]
    )

    assert (
        relationship.mapper.class_
        is AuthSession
    )
