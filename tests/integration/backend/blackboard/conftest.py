"""Stage-4B Blackboard API fixtures."""

from __future__ import annotations

import pytest

from tests.integration.backend.blackboard.api_fixtures import ApiEnv


@pytest.fixture
def api_env(tmp_path) -> ApiEnv:
    from fastapi.testclient import TestClient

    from backend.app.services.blackboard_service import BlackboardService
    from backend.app.services.replay_controller import ReplayController
    from tests.integration.backend.blackboard.api_fixtures import make_api_app

    root = tmp_path / "bb"
    service = BlackboardService(root=root)
    controller = ReplayController(blackboard=service)
    app = make_api_app(controller, service)
    env = ApiEnv(
        client=TestClient(app),
        controller=controller,
        service=service,
        root=root,
    )
    try:
        yield env
    finally:
        controller.shutdown()
        service.close()
