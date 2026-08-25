"""Backend per-window communication delta semantics."""

import pytest

from datasets.datasense.devices import DeviceInventory
from simulation.communication_graph import build_comm_graph
from tests.support.paths import DEVICES_CSV


def _inventory():
    return DeviceInventory.load(DEVICES_CSV)


def _rec(src, dst, wid, packets, bytes_=0, protos=None):
    return {
        "src_entity_id": src,
        "dst_entity_id": dst,
        "window_id": wid,
        "window_start_utc": f"2020-01-01T00:00:{wid:02d}Z",
        "packet_count": packets,
        "captured_byte_count": bytes_,
        "protocols": protos or ["TCP"],
        "broadcast_indicator": False,
        "multicast_indicator": False,
    }


def test_per_window_deltas_and_totals():
    inv = _inventory()
    cg = build_comm_graph(inventory=inv)

    # Window 1: A->B 3, B->C 2
    cg.apply(_rec("laptop-01", "server-01", 1, 3, 3000, ["TCP"]))
    cg.apply(_rec("server-01", "printer-01", 1, 2, 1000, ["UDP"]))

    assert cg.current_window_id == 1
    assert cg.get_window_delta("laptop-01", "server-01")["packet_count_delta"] == 3
    assert cg.get_window_delta("server-01", "printer-01")["packet_count_delta"] == 2
    assert cg.g.edges["laptop-01", "server-01"]["packet_count_total"] == 3
    assert cg.g.edges["server-01", "printer-01"]["packet_count_total"] == 2

    # Window 2: A->B 0 (absent), B->C 5
    cg.apply(_rec("server-01", "printer-01", 2, 5, 5000, ["TCP", "UDP"]))

    assert cg.current_window_id == 2
    # A->B had no traffic in window 2 -> delta 0, but total remains 3
    assert cg.get_window_delta("laptop-01", "server-01")["packet_count_delta"] == 0
    assert cg.g.edges["laptop-01", "server-01"]["packet_count_total"] == 3
    # B->C delta 5, total 7
    assert cg.get_window_delta("server-01", "printer-01")["packet_count_delta"] == 5
    assert cg.g.edges["server-01", "printer-01"]["packet_count_total"] == 7
    assert cg.get_window_delta("server-01", "printer-01")["captured_byte_delta"] == 5000
    assert set(cg.get_window_delta("server-01", "printer-01")["protocols_in_window"]) == {"TCP", "UDP"}


def test_empty_window_clears_deltas():
    inv = _inventory()
    cg = build_comm_graph(inventory=inv)
    cg.apply(_rec("a", "b", 10, 10, 1000))
    assert cg.get_window_delta("a", "b")["packet_count_delta"] == 10
    # Advance to window 11 with no records via begin_window
    cg.begin_window(11)
    assert cg.current_window_id == 11
    assert cg.get_window_delta("a", "b")["packet_count_delta"] == 0
    # Total still preserved
    assert cg.g.edges["a", "b"]["packet_count_total"] == 10


def test_window_delta_bounded_and_protocols():
    inv = _inventory()
    cg = build_comm_graph(inventory=inv)
    # Multiple records for same pair in same window should aggregate
    cg.apply(_rec("x", "y", 5, 1, 100, ["TCP"]))
    cg.apply(_rec("x", "y", 5, 2, 200, ["UDP"]))
    cg.apply(_rec("x", "y", 5, 3, 300, ["TCP"]))  # duplicate protocol
    delta = cg.get_window_delta("x", "y")
    assert delta["packet_count_delta"] == 6
    assert delta["captured_byte_delta"] == 600
    assert set(delta["protocols_in_window"]) == {"TCP", "UDP"}
    assert cg.g.edges["x", "y"]["packet_count_total"] == 6


def test_communication_snapshot_exposes_deltas():
    """Via adapter, snapshot should contain both totals and deltas for current window."""
    from backend.app.adapters.stage2_replay_adapter import build_runtime, communication_graph_contract

    rt = build_runtime(
        replay_id="test-per-window",
        session_trace="trace",
        scenario_id="attack_recon_host-disc-udp-ping_soil-sensor",
        source_mode="feature_store",
        pacing_speed="max",
    )
    # Run to first window completion and inspect
    # Use runner directly to control window
    rt.runner.run()
    # After full run, current_window_id is last window
    cg = communication_graph_contract(rt, "test-per-window")
    # Snapshot window_id should match runner's current window
    assert cg.window_id == rt.comm_graph.current_window_id
    # Every edge should have delta fields
    for e in cg.edges:
        assert hasattr(e, "packet_count_delta")
        assert hasattr(e, "captured_byte_delta")
        assert hasattr(e, "protocols_in_window")
        # Totals must be >= deltas
        assert e.packet_count_total >= e.packet_count_delta
        assert e.captured_byte_total >= e.captured_byte_delta
    rt.close()
