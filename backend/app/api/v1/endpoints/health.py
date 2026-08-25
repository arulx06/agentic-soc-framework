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
        active_run = (
            controller._runs.get(controller._active_id)
            if controller._active_id
            else None
        )
        active = (
            controller._active_id
            if active_run
            and active_run.state.value
            in ("CREATED", "RUNNING", "PAUSED")
            else None
        )
        active_starting = bool(
            active
            and active_run
            and active_run.state.value == "CREATED"
            and active_run.thread is not None
            and active_run.thread.is_alive()
        )
    readiness = artifacts_ready()
    scientific_ready = all(readiness.values())
    return {
        "service": "ok",
        "api_version": API_VERSION,
        "contract_versions": CONTRACT_VERSIONS,
        "active_replay": active,
        "active_replay_starting": active_starting,
        "artifact_readiness": readiness,
        "scientific_ready": scientific_ready,
    }
