from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.auth_dependencies import (
    require_workspace_access,
)
from app.db.models import (
    AccountRole,
    AccountType,
)
from app.main import app


@pytest.fixture
def workspace_access_override():
    """Authorize API tests that are not testing authentication."""

    account = SimpleNamespace(
        id=uuid4(),
        email="test@bitcoinchange.co.il",
        display_name="Test Account",
        account_type=AccountType.individual,
        role=AccountRole.administrator,
        branch_id=None,
        must_change_password=False,
        is_active=True,
    )

    app.dependency_overrides[
        require_workspace_access
    ] = lambda: account

    try:
        yield account
    finally:
        app.dependency_overrides.pop(
            require_workspace_access,
            None,
        )
