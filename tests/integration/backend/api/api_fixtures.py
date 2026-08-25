"""Shared Stage-3A test helpers (plain module; avoids conftest name-shadowing with the legacy suite)."""

from __future__ import annotations

import time

import pytest

SESSION_ID = "attack_recon_host-disc-udp-ping_soil-sensor"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as c:
        yield c


def wait_for_state(controller, replay_id: str, states, timeout: float = 60.0):
    wanted = {s.value if hasattr(s, "value") else str(s) for s in states}
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        st = controller.status(replay_id)
        last = st
        if st.state.value in wanted:
            return st
        time.sleep(0.2)
    raise TimeoutError(f"replay {replay_id} did not reach {wanted}; last={last}")


def run_to_completion(controller, session_id=SESSION_ID, mode="feature_store"):
    rid = controller.create_replay(
        session_id=session_id, source_mode=mode, pacing="max"
    )
    controller.play(rid)
    st = wait_for_state(controller, rid, ("COMPLETED", "FAILED"))
    if st.state.value == "FAILED":
        raise RuntimeError(st.error)

    # Status flips to COMPLETED before the worker publishes the final
    # scientific snapshot events + terminal envelope. Wait for the terminal
    # event so consumers of broker.ring see a complete namespace.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        ring = [
            e for e in controller.broker._ring
            if e.replay_id == rid
            and e.event_type.value in ("REPLAY_COMPLETED", "REPLAY_FAILED")
        ]
        if ring:
            break
        time.sleep(0.05)
    return rid, st


@pytest.fixture(scope="session")
def completed_feature_store_run():
    from backend.app.services.replay_controller import ReplayController

    controller = ReplayController()
    rid, status = run_to_completion(controller)
    return controller, rid, status
