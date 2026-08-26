"""Shared Stage-4B test helpers (plain module; fixtures live in conftest)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.app.api.v1.router import api_v1_router
from backend.app.contracts.common import ApiErrorV1
from backend.app.services.blackboard_service import BlackboardService
from backend.app.services.replay_controller import ControllerError, ReplayController


def make_api_app(controller: ReplayController, service: BlackboardService | None) -> FastAPI:
    """Isolated FastAPI app mirroring backend.app.main wiring (including the
    ControllerError -> ApiErrorV1 handler)."""
    app = FastAPI()
    app.include_router(api_v1_router, prefix="/api/v1")

    @app.exception_handler(ControllerError)
    async def _handler(_request, exc: ControllerError):
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiErrorV1(error_code=exc.code, message=exc.message).model_dump(),
        )

    app.state.controller = controller
    app.state.blackboard = service
    return app


@dataclass
class ApiEnv:
    client: TestClient
    controller: ReplayController
    service: BlackboardService
    root: Path
    published: list = field(default_factory=list)

    def drain_ring(self):
        return list(self.controller.broker._ring)
