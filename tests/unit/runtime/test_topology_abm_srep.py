"""Topology, communication graph, ABM, SREP tests (§32)."""

import pytest

from conftest import DEFAULT_DEVICES_ROWS

from agents.finding_gateway import FindingGateway
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from pipeline.findings import NetworkFinding, opaque_session_trace
from simulation.abm import DeviceABM
from simulation.communication_graph import build_comm_graph
from simulation.topology import attacker_nodes, build_topology, protected_nodes
from srep.device_srep import (
    MODE_DEVICE_ONLY,
    SREPEngine,
    TrustGraphUnsupportedError,
)


def _inventory():
    return DeviceInventory(
        [
            DeviceRecord(
                device_name=r["device_name"],
                mac=r["mac"].lower(),
                ip=r["ip"],
                role=r["role"],
                type=r["type"],
                main_topic=r["main_topic"],
            )
            for r in DEFAULT_DEVICES_ROWS
        ]
    )


@pytest.fixture
def env():
    inv = _inventory()
    topo = build_topology(inv)
    abm = DeviceABM(inv, topo)
    gw = FindingGateway(abm)
    comm = build_comm_graph(inventory=inv)
    return inv, topo, abm, gw, comm


def _finding(entity, proba, window=0):
    return NetworkFinding(
        entity_id=entity,
        window_id=window,
        timestamp_utc="2025-01-15T21:25:13.307Z",
        attack_probability=proba,
        predicted_class="attack" if proba >= 0.5 else "benign",
        confidence=abs(proba - 0.5) * 2,
        source_model="network_detector_v1@network_feature_schema_v1",
        provenance={
            "session_trace": opaque_session_trace("s"),
            "source_mode": "feature_store",
        },
    )


def _comm_record(src, dst, window=0, packets=3):
    return {
        "scenario_id": "s",
        "window_id": window,
        "window_start_utc": "2025-01-15T21:25:13.307Z",
        "window_end_utc": "2025-01-15T21:25:18.307Z",
        "src_entity_id": src,
        "dst_entity_id": dst,
        "src_resolution_status": "resolved_mac",
        "dst_resolution_status": "resolved_mac",
        "packet_count": packets,
        "captured_byte_count": packets * 60,
        "wire_byte_count": packets * 60,
        "protocols": ["tcp"],
        "protocol_packet_counts": [packets],
        "src_ports": [],
        "dst_ports": [],
        "broadcast_indicator": False,
        "multicast_indicator": False,
        "raw_source": "pcap",
        "extractor_version": "datasense_raw_extractor_v2",
        "schema_version": "communication_feature_schema_v1",
    }


def test_topology_metadata_grounded(env):
    _, topo, *_ = env
    broker = topo.nodes["mqtt-broker"]
    assert broker["is_protected_asset"] is True
    soil = topo.nodes["soil-sensor"]
    assert soil["behavior_supported"] is True
    e = topo.edges["soil-sensor", "mqtt-broker"]
    assert e["provenance"] == "STRONGLY_INFERRED"
    e2 = topo.edges["soil-sensor", "ap"]
    assert e2["provenance"] == "DOCUMENTED"
    for u, v, d in topo.edges(data=True):
        assert d["provenance"] in ("DOCUMENTED", "STRONGLY_INFERRED")
    import networkx as nx

    assert nx.is_frozen(topo), "runtime topology must be frozen"


def test_attackers_distinguishable_and_not_protected(env):
    _, topo, *_ = env
    assert "attacker0" in attacker_nodes(topo)
    assert "attacker0" not in protected_nodes(topo)
    assert topo.nodes["attacker0"]["is_attacker"] is True
    assert topo.nodes["attacker0"]["is_protected_asset"] is False


def test_communication_updates_gcomm_not_topology(env):
    inv, topo, _, _, comm = env
    before = set(topo.edges)
    comm.apply(_comm_record("soil-sensor", "attacker0"))
    assert comm.g.has_edge("soil-sensor", "attacker0")
    edge_data = comm.g.edges["soil-sensor", "attacker0"]
    assert edge_data["packet_count_total"] == 3
    assert set(topo.edges) == before, "structural topology must not mutate"
    assert comm.g.nodes["attacker0"]["is_attacker"] is True

    comm.apply(_comm_record("soil-sensor", "attacker0", packets=2))
    assert comm.g.edges["soil-sensor", "attacker0"]["packet_count_total"] == 5


def test_direct_vs_propagated_separate_and_decaying(env):
    _, topo, abm, gw, _ = env
    gw.submit(_finding("soil-sensor", 1.0))
    abm.propagate()
    soil = abm.states["soil-sensor"]
    broker = abm.states["mqtt-broker"]
    edge = abm.states["edge1"]
    assert soil.propagated_risk == 0.0
    assert 0 < broker.propagated_risk <= 0.5
    if edge.propagated_risk > 0:
        assert edge.propagated_risk < broker.propagated_risk
    assert soil.systemic_risk == 1.0


def test_cycles_cannot_amplify_without_bound(env):
    _, topo, abm, gw, _ = env
    import networkx as nx

    mutable = nx.DiGraph(topo)
    mutable.add_edge("soil-sensor", "motion-sensor", provenance="DOCUMENTED", relation="test")
    mutable.add_edge("motion-sensor", "water-sensor", provenance="DOCUMENTED", relation="test")
    mutable.add_edge("water-sensor", "soil-sensor", provenance="DOCUMENTED", relation="test")
    abm.topology = mutable
    gw.submit(_finding("soil-sensor", 1.0))
    abm.params["max_hops"] = 6
    for _ in range(4):
        abm.propagate()
    for st in abm.states.values():
        assert st.propagated_risk <= 1.0 + 1e-9
        assert st.systemic_risk <= 1.0 + 1e-9


def test_missing_behaviour_explicit_in_srep(env):
    _, _, abm, gw, _ = env
    gw.submit(_finding("router", 0.7))
    abm.propagate()
    router = abm.states["router"]
    assert router.behavior_risk is None
    assert router.behavior_supported is False
    srep = SREPEngine(abm).run()
    node = next(n for n in srep["device_risk_nodes"] if n["node_id"] == "router")
    assert node["behavior_risk"] is None
    assert node["network_risk"] == pytest.approx(0.7)


def test_attacker_excluded_from_defended_blast_radius(env):
    _, _, abm, _, _ = env
    base_radius = abm.defended_blast_radius()
    atk_state = None

    class FakeAttackerFinding:
        entity_id = "attacker0"
        window_id = 0
        timestamp_utc = "2025-01-15T21:25:13.307Z"
        attack_probability = 1.0
        predicted_class = "attack"
        confidence = 1.0
        source_model = "test"
        provenance = {"scenario_id": "s"}

        def evidence_kind(self):
            return "network"

    abm.apply_network_evidence(FakeAttackerFinding())
    abm.propagate()
    after_radius = abm.defended_blast_radius()
    assert abm.states["attacker0"].is_attacker is True
    assert after_radius >= base_radius - 1e-9
    contribution = any(
        n["node_id"] == "attacker0" and n["defended_contribution"] > 0
        for n in SREPEngine(abm).run()["device_risk_nodes"]
    )
    assert contribution is False
    assert atk_state is None


def test_history_bounded(env):
    _, _, abm, gw, _ = env
    small_abm = DeviceABM(_inventory(), build_topology(_inventory()), history_limit=8)
    gws = FindingGateway(small_abm)
    for w in range(50):
        gws.submit(_finding("soil-sensor", 0.9, window=w))
        small_abm.propagate()
        small_abm.record_step()
    assert len(small_abm.history) == 8
    assert small_abm.history[-1]["step"] == 50


def test_srep_reports_device_only(env):
    _, _, abm, gw, comm = env
    gw.submit(_finding("soil-sensor", 0.95))
    abm.propagate()
    report = SREPEngine(abm, comm.g).run()
    assert report["mode"] == MODE_DEVICE_ONLY
    assert "must not be interpreted as full dual-graph" in report["mode_note"]
    assert report["parameter_disclaimer"].startswith("SIMULATION-DEFINED")


def test_srep_rejects_unsupported_trust_graph(env):
    _, _, abm, _, _ = env
    import networkx as nx

    fake_trust = nx.DiGraph()
    fake_trust.add_edge("agentA", "agentB", trust=0.9)
    with pytest.raises(TrustGraphUnsupportedError):
        SREPEngine(abm).run(agent_trust_graph=fake_trust)
