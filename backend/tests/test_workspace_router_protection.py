from app.api.auth_dependencies import (
    require_workspace_access,
)
from app.api.routes.copilot import (
    router as copilot_router,
)
from app.api.routes.knowledge import (
    router as knowledge_router,
)


def dependency_calls(router) -> set[object]:
    return {
        dependency.dependency
        for dependency in router.dependencies
    }


def test_knowledge_router_requires_workspace_access() -> None:
    assert (
        require_workspace_access
        in dependency_calls(knowledge_router)
    )


def test_copilot_router_requires_workspace_access() -> None:
    assert (
        require_workspace_access
        in dependency_calls(copilot_router)
    )
