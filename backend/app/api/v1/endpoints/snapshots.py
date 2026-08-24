"""Saved backend snapshots: list / read / save final replay snapshot."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.config import CONTRACT_VERSIONS
from backend.app.contracts.saved_snapshot_v1 import SavedReplaySnapshotV1
from backend.app.services.replay_controller import ControllerError
from backend.app.services.snapshot_store import now_utc

router = APIRouter()


@router.get("/snapshots")
def list_snapshots(request: Request):
    store: SnapshotStore = request.app.state.snapshot_store
    return {"snapshots": store.list_snapshots()}


@router.get("/snapshots/{snapshot_id}")
def read_snapshot(snapshot_id: str, request: Request):
    store = request.app.state.snapshot_store
    try:
        snap = store.load(snapshot_id)
    except ValueError as exc:
        raise ControllerError(
            "incompatible_schema", str(exc), 409
        )
    if snap is None:
        raise ControllerError("unknown_snapshot", f"unknown snapshot {snapshot_id!r}", 404)
    return snap.model_dump()


@router.post("/snapshots", status_code=201)
def save_final_snapshot(request: Request):
    controller = request.app.state.controller
    with controller._lock:
        active_id = controller._active_id
        run = controller._runs.get(active_id) if active_id else None
        if run is None or run.runtime is None:
            raise ControllerError(
                "no_scientific_state",
                "no completed/running replay runtime available to snapshot",
                409,
            )
        from backend.app.adapters.stage2_replay_adapter import (
            communication_graph_contract,
            device_risk_graph_contract,
            device_state_contracts,
            srep_contract,
        )

        device_states = [s.model_dump() for s in device_state_contracts(run.runtime, active_id)]
        risk_graph = device_risk_graph_contract(run.runtime, active_id).model_dump()
        comm_graph = communication_graph_contract(run.runtime, active_id).model_dump()
        srep_snap, _report = srep_contract(run.runtime, active_id)

        status = run.status().model_dump()
    snapshot_id = f"snap-{active_id}"
    snap = SavedReplaySnapshotV1(
        snapshot_id=snapshot_id,
        replay_id=active_id,
        session_trace=run.session_trace,
        created_at_utc=now_utc(),
        replay_status=status,
        device_states=device_states,
        device_risk_graph=risk_graph,
        communication_graph=comm_graph,
        srep=srep_snap.model_dump(),
        provenance={
            "contract_versions": dict(CONTRACT_VERSIONS),
            "source_component": "backend.app.api.v1.endpoints.snapshots",
        },
    )
    path = request.app.state.snapshot_store.save(snap)
    # Snapshot saving persists the already-produced final scientific state
    # and deliberately emits NO replay events: REPLAY_COMPLETED remains the
    # final event in the replay's namespace (see docs/stage3a §5).
    return {"snapshot_id": snapshot_id, "path": str(path)}
