"""DEVICE_ONLY SREP endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/replays/{replay_id}/srep")
def srep(replay_id: str, request: Request):
    controller = request.app.state.controller
    snap, report = controller.srep_snapshot(replay_id)
    data = snap.model_dump()
    # Factual smoke labeling from artifact metadata only.
    data["artifact_flags"] = ["SMOKE_MODEL_ARTIFACTS", "NOT_RESEARCH_RESULTS"]
    return data
