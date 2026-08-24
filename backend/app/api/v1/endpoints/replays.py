"""Replay creation, status and control endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.contracts.replay_v1 import PacingSpeed

router = APIRouter()


@router.post("/replays", status_code=201)
def create_replay(request: Request, body: dict):
    controller = request.app.state.controller
    replay_id = controller.create_replay(
        session_id=str(body.get("session_id", "")),
        source_mode=str(body.get("source_mode", "feature_store")),
        pacing=PacingSpeed(body.get("pacing", "max")),
    )
    return {"replay_id": replay_id, "status": controller.status(replay_id)}


@router.get("/replays/{replay_id}")
def get_status(replay_id: str, request: Request):
    controller = request.app.state.controller
    return controller.status(replay_id)


@router.post("/replays/{replay_id}/play")
def play(replay_id: str, request: Request):
    request.app.state.controller.play(replay_id)
    return {"replay_id": replay_id, "state": "RUNNING"}


@router.post("/replays/{replay_id}/pause")
def pause(replay_id: str, request: Request):
    request.app.state.controller.pause(replay_id)
    return {"replay_id": replay_id, "state": "PAUSED"}


@router.post("/replays/{replay_id}/resume")
def resume(replay_id: str, request: Request):
    request.app.state.controller.resume(replay_id)
    return {"replay_id": replay_id, "state": "RUNNING"}


@router.post("/replays/{replay_id}/step")
def step(replay_id: str, request: Request):
    request.app.state.controller.step(replay_id)
    return {"replay_id": replay_id, "state": "PAUSED", "stepped": True}


@router.post("/replays/{replay_id}/restart", status_code=201)
def restart(replay_id: str, request: Request):
    new_id = request.app.state.controller.restart(replay_id)
    return {"previous_replay_id": replay_id, "new_replay_id": new_id}


@router.patch("/replays/{replay_id}/speed")
def set_speed(replay_id: str, request: Request, body: dict):
    speed = PacingSpeed(body.get("pacing", "max"))
    request.app.state.controller.set_pacing(replay_id, speed)
    return {"replay_id": replay_id, "pacing": speed.value}
