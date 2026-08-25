"""Direct raw communication graph regression (Issue B).

Verifies that direct_raw no longer starves the communication stream
and that feature_store/direct_raw remain scientifically equivalent.
"""

import time

import pytest

from backend.app.services.replay_controller import ReplayController
from api_fixtures import SESSION_ID, wait_for_state


@pytest.fixture
def controller():
    return ReplayController(sleeper=lambda _s: 0)


def test_direct_raw_communication_graph_populated(controller):
    """direct_raw must produce non-empty communication graph where fixture has traffic."""
    rid = controller.create_replay(
        session_id=SESSION_ID, source_mode="direct_raw", pacing="max"
    )
    controller.play(rid)
    wait_for_state(controller, rid, ("COMPLETED",))
    # Poll until communication graph has data (final snapshots may still be emitting)
    deadline = time.monotonic() + 10
    comm = None
    while time.monotonic() < deadline:
        comm = controller.communication_graph(rid)
        if len(comm.edges) > 0:
            break
        time.sleep(0.2)
    assert comm is not None
    assert len(comm.nodes) > 0, "communication graph nodes should be populated in direct_raw"
    assert len(comm.edges) > 0, "communication graph edges should be populated in direct_raw"
    # Sanity: windows processed >0
    st = controller.status(rid)
    assert st.windows_processed > 0


def test_feature_store_vs_direct_raw_communication_equivalence():
    """Communication graph from both modes should be equivalent for same fixture."""
    from backend.app.adapters.stage2_replay_adapter import (
        build_runtime,
        communication_graph_contract,
    )

    def run_and_snapshot(source_mode: str):
        rt = build_runtime(
            replay_id=f"test-{source_mode}",
            session_trace="trace",
            scenario_id=SESSION_ID,
            source_mode=source_mode,
            pacing_speed="max",
        )
        rt.runner.run()
        cg = communication_graph_contract(rt, f"test-{source_mode}")
        rt.close()
        return cg

    cg_store = run_and_snapshot("feature_store")
    cg_raw = run_and_snapshot("direct_raw")

    # Nodes: set equality
    assert set(cg_store.nodes) == set(cg_raw.nodes), "node identities must match"

    # Edges: compare directed endpoints and stable fields
    def key(e):
        return (e.src_entity_id, e.dst_entity_id)

    store_by_key = {key(e): e for e in cg_store.edges}
    raw_by_key = {key(e): e for e in cg_raw.edges}
    assert set(store_by_key) == set(raw_by_key), "edge endpoint sets must be equivalent"

    for k in store_by_key:
        s = store_by_key[k]
        r = raw_by_key[k]
        assert s.packet_count_total == r.packet_count_total, f"packet_count mismatch for {k}"
        assert s.captured_byte_total == r.captured_byte_total, f"byte total mismatch for {k}"
        assert set(s.protocols_ever) == set(r.protocols_ever), f"protocols mismatch for {k}"
        # window/timestamp fields should be equivalent where present
        assert s.first_window_id == r.first_window_id
        assert s.last_window_id == r.last_window_id


def test_direct_raw_no_regression_to_network_and_device_graph(controller):
    """Direct raw fix must not break network findings / device risk graph."""
    rid = controller.create_replay(
        session_id=SESSION_ID, source_mode="direct_raw", pacing="max"
    )
    controller.play(rid)
    wait_for_state(controller, rid, ("COMPLETED",))
    st = controller.status(rid)
    assert st.windows_processed == 13
    # Device risk graph should have topology nodes (inventory size ~48)
    risk = controller.device_risk_graph(rid)
    assert len(risk.nodes) > 0
    assert len(risk.edges) > 0
    # Device states
    states = controller.device_states(rid)
    assert len(states) > 0
    # Communication graph also populated (re-check)
    comm = controller.communication_graph(rid)
    assert len(comm.edges) > 0
    # SREP should be DEVICE_ONLY and have blast radius
    srep, _ = controller.srep_snapshot(rid)
    assert srep.mode == "DEVICE_ONLY"
    assert srep.defended_blast_radius is not None
