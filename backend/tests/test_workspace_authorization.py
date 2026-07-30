from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.auth_dependencies import (
    current_account,
)
from app.api.dependencies import (
    get_copilot_answer_service,
    get_knowledge_retrieval_service,
)
from app.db.models import (
    AccountRole,
    AccountType,
)
from app.main import app


class FakeKnowledgeService:
    async def search(
        self,
        *_: object,
        **__: object,
    ) -> tuple[()]:
        return ()


class FakeCopilotService:
    async def answer(
        self,
        *_: object,
        **__: object,
    ) -> None:
        raise AssertionError(
            "Copilot service must not run "
            "when authorization fails"
        )


def make_account(
    *,
    must_change_password: bool,
):
    return SimpleNamespace(
        id=uuid4(),
        email="test@bitcoinchange.co.il",
        display_name="Test Account",
        account_type=AccountType.individual,
        role=AccountRole.administrator,
        branch_id=None,
        must_change_password=(
            must_change_password
        ),
        is_active=True,
    )


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_knowledge_requires_authentication() -> None:
    app.dependency_overrides[
        get_knowledge_retrieval_service
    ] = lambda: FakeKnowledgeService()

    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/search",
            json={
                "query": "פתיחת סניף",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required"
    }


def test_copilot_requires_authentication() -> None:
    app.dependency_overrides[
        get_copilot_answer_service
    ] = lambda: FakeCopilotService()

    with TestClient(app) as client:
        response = client.post(
            "/api/copilot/ask",
            json={
                "question": "איך פותחים סניף?",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required"
    }


def test_knowledge_rejects_forced_password_change() -> None:
    account = make_account(
        must_change_password=True
    )

    app.dependency_overrides[
        current_account
    ] = lambda: account

    app.dependency_overrides[
        get_knowledge_retrieval_service
    ] = lambda: FakeKnowledgeService()

    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/search",
            json={
                "query": "פתיחת סניף",
            },
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Password change required"
    }


def test_copilot_rejects_forced_password_change() -> None:
    account = make_account(
        must_change_password=True
    )

    app.dependency_overrides[
        current_account
    ] = lambda: account

    app.dependency_overrides[
        get_copilot_answer_service
    ] = lambda: FakeCopilotService()

    with TestClient(app) as client:
        response = client.post(
            "/api/copilot/ask",
            json={
                "question": "איך פותחים סניף?",
            },
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Password change required"
    }


def test_knowledge_allows_activated_account() -> None:
    account = make_account(
        must_change_password=False
    )

    app.dependency_overrides[
        current_account
    ] = lambda: account

    app.dependency_overrides[
        get_knowledge_retrieval_service
    ] = lambda: FakeKnowledgeService()

    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/search",
            json={
                "query": "פתיחת סניף",
            },
        )

    assert response.status_code == 200
    assert response.json()["count"] == 0
