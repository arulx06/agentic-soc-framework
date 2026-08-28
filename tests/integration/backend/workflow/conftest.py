import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_v1_router
from backend.app.contracts.common import ApiErrorV1
from backend.app.services.blackboard_service import BlackboardService
from backend.app.services.event_broker import EventBroker
from backend.app.services.orchestration_service import OrchestrationService
from backend.app.services.replay_controller import ControllerError, ReplayController
from backend.app.services.snapshot_store import SnapshotStore
from backend.app.services.workflow_service import WorkflowService


@pytest.fixture
def workflow_app(tmp_path):
    # Fresh isolated stack per test
    bb_root = tmp_path / "blackboard"
    bb_root.mkdir(parents=True, exist_ok=True)
    blackboard = BlackboardService(root=bb_root, enabled=True)
    broker = EventBroker(ring_size=4000, subscriber_queue_size=500)
    controller = ReplayController(broker=broker, blackboard=blackboard)
    orchestration = OrchestrationService()
    orchestration.publisher = controller._publish_orchestration_event
    workflow = WorkflowService(blackboard=blackboard, orchestration=orchestration, controller=controller)
    controller.workflow = workflow

    snapshot_store = SnapshotStore(tmp_path / "snapshots")
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.exception_handler(ControllerError)
    async def handler(_request, exc: ControllerError):
        return JSONResponse(status_code=exc.status_code, content=ApiErrorV1(error_code=exc.code, message=exc.message).model_dump())

    app.state.controller = controller
    app.state.blackboard = blackboard
    app.state.orchestration = orchestration
    app.state.workflow = workflow
    app.state.snapshot_store = snapshot_store

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client, controller, workflow, blackboard, orchestration

    # Cleanup
    try:
        workflow._states.clear()
    except Exception:
        pass
    try:
        orchestration.coordinator._rounds.clear()
        orchestration.coordinator._active_keys.clear()
    except Exception:
        pass
    try:
        blackboard.close()
    except Exception:
        pass
    try:
        controller.shutdown()
    except Exception:
        pass
