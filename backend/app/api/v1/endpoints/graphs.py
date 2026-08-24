"""Device-state and graph snapshot endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/replays/{replay_id}/device-state")
def device_states(replay_id: str, request: Request):
    controller = request.app.state.controller
    states = controller.device_states(replay_id)
    return {
        "schema_version": "device_state_v1",
        "replay_id": replay_id,
        "devices": [s.model_dump() for s in states],
    }


@router.get("/replays/{replay_id}/graphs/device-risk")
def device_risk_graph(replay_id: str, request: Request):
    controller = request.app.state.controller
    snap = controller.device_risk_graph(replay_id)
    return snap.model_dump()


@router.get("/replays/{replay_id}/graphs/communication")
def communication_graph(replay_id: str, request: Request):
    controller = request.app.state.controller
    snap = controller.communication_graph(replay_id)
    return snap.model_dump()
