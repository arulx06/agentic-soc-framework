from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.app.api.v1.router import api_v1_router
from backend.app.contracts.common import ApiErrorV1
from backend.app.services.event_broker import EventBroker
from backend.app.services.orchestration_service import OrchestrationService
from backend.app.services.replay_controller import ControllerError, ReplayController

TEST_KEYS = {
    "orchestrator_a": b"a" * 32,
    "orchestrator_b": b"b" * 32,
    "orchestrator_c": b"c" * 32,
}


def request_body(request_id="api-request-1", round_id="api-round-1"):
    return {
        "schema_version": "orchestration_request_v1",
        "request_id": request_id,
        "request_version": 1,
        "round_id": round_id,
        "decision_kind": "OPAQUE_ROUTE",
        "candidate_routes": [
            {
                "schema_version": "orchestration_candidate_route_v1",
                "route_id": "route_alpha",
                "priority": 1,
            },
            {
                "schema_version": "orchestration_candidate_route_v1",
                "route_id": "route_beta",
                "priority": 2,
            },
        ],
        "logical_timestamp": "2026-08-28T00:00:00Z",
        "window_id": 4,
        "source_component": "integration.test",
        "provenance": {"runtime_trace": "opaque-api"},
    }


@pytest.fixture
def api_env():
    broker = EventBroker(ring_size=100, subscriber_queue_size=100)
    controller = ReplayController(broker=broker)
    service = OrchestrationService(keys=TEST_KEYS, timeout_seconds=0.2)
    service.publisher = controller._publish_orchestration_event
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.exception_handler(ControllerError)
    async def handler(_request, exc: ControllerError):
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiErrorV1(error_code=exc.code, message=exc.message).model_dump(),
        )

    app.state.controller = controller
    app.state.orchestration = service
    app.state.blackboard = None
    with TestClient(app) as client:
        yield client, controller, service
    service.shutdown()
    controller.shutdown()
