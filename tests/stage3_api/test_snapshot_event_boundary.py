"""Snapshot-event boundary tests (Stage-3A corrective pass).

Proves:
  * replay completion emits 45 DEVICE_STATE + one Device Risk Graph +
    one Communication Graph + one SREP event, all BEFORE REPLAY_COMPLETED;
  * POST /api/v1/snapshots after completion persists the snapshot and
    appends ZERO new events;
  * REPLAY_COMPLETED remains the final event in the namespace.
"""

import time

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts.events_v1 import ReplayEventType
from backend.app.main import app

SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _wait_terminal(client, rid, timeout=60.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        st = client.get(f"/api/v1/replays/{rid}").json()
        last = st
        if st.get("state") in ("COMPLETED", "FAILED"):
            return st
        time.sleep(0.2)
    raise TimeoutError(f"replay did not terminate; last={last}")


@pytest.fixture
def completed_replay(client):
    rid = client.post(
        "/api/v1/replays",
        json={"session_id": SESSION, "source_mode": "feature_store", "pacing": "max"},
    ).json()["replay_id"]
    assert client.post(f"/api/v1/replays/{rid}/play").status_code == 200
    st = _wait_terminal(client, rid)

    # status flips to COMPLETED slightly before the worker publishes the
    # final snapshot events + terminal envelope; wait for the terminal
    # event to appear in the ring before asserting.
    controller = app.state.controller
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        ring = [e for e in controller.broker._ring if e.replay_id == rid]
        if any(
            e.event_type
            in (ReplayEventType.REPLAY_COMPLETED, ReplayEventType.REPLAY_FAILED)
            for e in ring
        ):
            break
        time.sleep(0.1)

    assert st["state"] == "COMPLETED", st.get("error")
    return rid


def _events_for(controller, rid):
    return [e for e in controller.broker._ring if e.replay_id == rid]


def test_completion_emits_final_scientific_events_before_terminal(client, completed_replay):
    controller = app.state.controller
    events = _events_for(controller, completed_replay)
    order = [e.event_type for e in events]

    assert sum(1 for t in order if t == ReplayEventType.DEVICE_STATE) == 45
    assert order.count(ReplayEventType.DEVICE_RISK_GRAPH_SNAPSHOT) == 1
    assert order.count(ReplayEventType.COMMUNICATION_GRAPH_SNAPSHOT) == 1
    assert order.count(ReplayEventType.SREP_SNAPSHOT) == 1

    terminal_idx = order.index(ReplayEventType.REPLAY_COMPLETED)
    last_window_completed_idx = len(order) - 1 - order[::-1].index(
        ReplayEventType.WINDOW_COMPLETED
    )
    snap_idxs = [
        i
        for i, t in enumerate(order)
        if t
        in (
            ReplayEventType.DEVICE_STATE,
            ReplayEventType.DEVICE_RISK_GRAPH_SNAPSHOT,
            ReplayEventType.COMMUNICATION_GRAPH_SNAPSHOT,
            ReplayEventType.SREP_SNAPSHOT,
        )
    ]
    assert snap_idxs, "final scientific snapshot events must be present"
    assert all(last_window_completed_idx < i < terminal_idx for i in snap_idxs)

    # SREP payload is genuinely DEVICE_ONLY backend state
    srep_env = next(
        e for e in events if e.event_type == ReplayEventType.SREP_SNAPSHOT
    )
    assert srep_env.payload["mode"] == "DEVICE_ONLY"
    assert srep_env.payload["steps_replayed"] == 13


def test_post_snapshots_appends_no_events_and_terminal_stays_last(
    client, completed_replay
):
    controller = app.state.controller

    before = list(_events_for(controller, completed_replay))
    before_count = len(before)
    assert before[-1].event_type == ReplayEventType.REPLAY_COMPLETED

    resp = client.post("/api/v1/snapshots")
    assert resp.status_code == 201, resp.text

    after = list(_events_for(controller, completed_replay))
    assert len(after) == before_count, (
        "snapshot saving must not append any replay events"
    )
    assert [e.sequence_number for e in after] == [
        e.sequence_number for e in before
    ]
    assert after[-1].event_type == ReplayEventType.REPLAY_COMPLETED