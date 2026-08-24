"""Health endpoint: inexpensive service + readiness summary."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.config import API_VERSION, CONTRACT_VERSIONS

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    from backend.app.services.session_catalog import artifacts_ready

    controller = request.app.state.controller
    with controller._lock:
        active = (
            controller._active_id
            if controller._active_id
            and controller._runs.get(controller._active_id)
            and controller._runs[controller._active_id].state.value == "RUNNING"
            else None
        )
    readiness = artifacts_ready()
    scientific_ready = all(readiness.values())
    return {
        "service": "ok",
        "api_version": API_VERSION,
        "contract_versions": CONTRACT_VERSIONS,
        "active_replay": active,
        "artifact_readiness": readiness,
        "scientific_ready": scientific_ready,
    }
