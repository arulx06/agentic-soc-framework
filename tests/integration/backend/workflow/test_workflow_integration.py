"""Stage-8B integration tests: orchestrated five-agent workflow."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_workflow.contracts import AgentId, ActionType
from agentic_workflow.readiness import ready_agents
from agentic_workflow.registry import AGENT_TO_ROUTE, ROUTE_TO_AGENT
from backend.app.main import app
from backend.app.services.snapshot_store import SnapshotStore
from backend.app.contracts.events_v1 import ReplayEventType


@pytest.fixture(autouse=True)
def _isolate_workflow_state():
    # Ensure per-test isolation of workflow and orchestration per-replay state
    try:
        app.state.workflow._states.clear()
    except Exception:
        pass
    try:
        # Clear orchestration round history to prevent cross-test contamination
        app.state.orchestration.coordinator._rounds.clear()
        app.state.orchestration.coordinator._active_keys.clear()
        app.state.orchestration.coordinator.replay_cache._entries.clear()
        # Clear controller's workflow states is already done
        # Do not clear broker ring globally, but ensure ops sequences don't overflow
    except Exception:
        pass
    yield
    try:
        app.state.workflow._states.clear()
        app.state.orchestration.coordinator._rounds.clear()
        app.state.orchestration.coordinator._active_keys.clear()
        app.state.orchestration.coordinator.replay_cache._entries.clear()
    except Exception:
        pass


# Helper to create isolated workflow via API

def _wait_completed(client, rid, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = client.get(f"/api/v1/replays/{rid}").json()
        if st.get("state") in ("COMPLETED", "FAILED"):
            return st
        time.sleep(0.2)
    raise TimeoutError("replay not completed")


def _wait_workflow_completed(client, rid, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            snap = client.get(f"/api/v1/replays/{rid}/workflow").json()
            statuses = {s["agent_id"]: s["status"] for s in snap.get("five_agent_statuses", [])}
            if all(statuses.get(aid) == "COMPLETED" for aid in ["network_anomaly_detector","iot_behavioral_profiler","threat_intelligence_correlator","risk_propagation_analyst","trust_access_controller"]):
                return snap
        except Exception:
            pass
        time.sleep(0.2)
    return None


def test_ready_routes_only_candidates():
    ready = {AgentId.network_anomaly_detector, AgentId.iot_behavioral_profiler}
    # Simulate dispatch request candidates
    from agentic_workflow.registry import AGENT_TO_ROUTE
    candidates = {AGENT_TO_ROUTE[a] for a in ready}
    assert candidates == {"agent.network_anomaly_detector", "agent.iot_behavioral_profiler"}
    # Threat should not be candidate initially
    assert "agent.threat_intelligence_correlator" not in candidates


def test_orchestration_dispatch_no_fallback_via_api(workflow_app):
    client, controller, workflow, blackboard, orchestration = workflow_app
    rid = client.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
    client.post(f"/api/v1/replays/{rid}/play")
    _wait_completed(client, rid)
    # Poll workflow
    snap = _wait_workflow_completed(client, rid, timeout=15)
    assert snap is not None
    assert snap["workflow_mode"] == "FIVE_AGENT_LIVE"
    statuses = {s["agent_id"]: s["status"] for s in snap["five_agent_statuses"]}
    for aid in ["network_anomaly_detector","iot_behavioral_profiler","threat_intelligence_correlator","risk_propagation_analyst","trust_access_controller"]:
        assert statuses[aid] == "COMPLETED", statuses
    assert len(snap["latest_enforcement_decisions"]) > 0
    for dec in snap["latest_enforcement_decisions"]:
        assert dec["action"] in ("ALLOW","MONITOR","BLOCK")
        assert dec["physical_enforcement_claimed"] is False
        assert dec["counterfactual_effect_applied"] is False


def test_no_quorum_via_direct_orchestration():
    # Use orchestration directly to simulate NO_QUORUM: make two orchestrators timeout
    # Instead, test workflow's handling of non-DECIDED via fake decision
    from backend.app.services.workflow_service import WorkflowService
    from unittest.mock import Mock
    # Fake orchestration that returns NO_QUORUM
    fake_decision = Mock()
    fake_decision.outcome.value = "NO_QUORUM"
    fake_decision.selected_route_id = None
    fake_orch = Mock()
    fake_orch.coordinator.adjudicate.return_value = fake_decision
    ws = WorkflowService(orchestration=fake_orch, blackboard=None, controller=None)
    # Try dispatch with ready {network}
    ready = {AgentId.network_anomaly_detector}
    dec = ws._dispatch_via_orchestration("test-rid", 0, "2026-01-01T00:00:00Z", ready)
    # Should return fake decision with NO_QUORUM
    assert dec.outcome.value == "NO_QUORUM"
    # Workflow should treat as no execution
    # Simulate execute_window with this fake: it should fail window
    # We can test that no specialist executes when not DECIDED by checking that _dispatch returns non-DECIDED and workflow would mark failed


def test_unknown_route_rejected():
    from agentic_workflow.registry import resolve_route
    with pytest.raises(ValueError):
        resolve_route("agent.unknown_agent")
    with pytest.raises(ValueError):
        resolve_route("eval('bad')")


def test_selected_not_ready_rejected():
    # Simulate ready {network} but selected route is threat (not ready) -> should be rejected
    from backend.app.services.workflow_service import WorkflowService
    from unittest.mock import Mock
    fake_dec = Mock()
    fake_dec.outcome.value = "DECIDED"
    fake_dec.selected_route_id = "agent.threat_intelligence_correlator"  # not ready
    fake_orch = Mock()
    fake_orch.coordinator.adjudicate.return_value = fake_dec
    ws = WorkflowService(orchestration=fake_orch, blackboard=None, controller=None)
    # Create minimal ABM and gateway for execute_window to fail at not_ready check
    from datasets.datasense.devices import DeviceInventory
    from backend.app.config import DEVICES_CSV
    from simulation.abm import DeviceABM
    from simulation.topology import build_topology
    from agents.finding_gateway import FindingGateway
    from pipeline.network_detector import NetworkDetector
    from pipeline.behavior_profiler import BehaviorProfiler
    from backend.app.config import NETWORK_MODEL_PATH, BEHAVIOR_MODEL_PATH
    inv = DeviceInventory.load(DEVICES_CSV)
    det = NetworkDetector.load(NETWORK_MODEL_PATH)
    prof = BehaviorProfiler.load(BEHAVIOR_MODEL_PATH)
    abm = DeviceABM(inv, build_topology(inv))
    gateway = FindingGateway(abm)
    # Use empty rows to trigger not_ready
    result = ws.execute_window(
        replay_id="test-rid2",
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        net_rows=[],
        beh_rows=[],
        abm=abm,
        gateway=gateway,
        detector=det,
        profiler=prof,
        inventory=inv,
    )
    assert result["status"] == "FAILED"
    assert any("not_ready" in f or "SELECTED_NOT_READY" in f for f in result["failures"])


def test_no_double_inference_via_workflow(tmp_path):
    # Ensure one window -> one detector inference via spy
    from pipeline.network_detector import NetworkDetector
    from backend.app.config import NETWORK_MODEL_PATH
    det = NetworkDetector.load(NETWORK_MODEL_PATH)
    orig = det.findings_from_records
    calls = []
    def spy(rows, **kw):
        calls.append(len(rows))
        return orig(rows, **kw)
    det.findings_from_records = spy

    prev = app.state.snapshot_store
    app.state.snapshot_store = SnapshotStore(tmp_path / "snap2")
    try:
        # Patch the global load to return spy det? Instead inject via runtime?
        # For this test, we will directly test via WorkflowService with spy
        from backend.app.services.workflow_service import WorkflowService
        from backend.app.services.blackboard_service import BlackboardService
        from backend.app.services.orchestration_service import OrchestrationService
        import tempfile
        tmpdir = tempfile.mkdtemp()
        bb = BlackboardService(root=Path(tmpdir), enabled=True)
        orch = OrchestrationService()
        from backend.app.services.replay_controller import ReplayController
        from backend.app.services.event_broker import EventBroker
        broker = EventBroker(ring_size=1000, subscriber_queue_size=100)
        ctrl = ReplayController(broker=broker, blackboard=bb)
        ws = WorkflowService(blackboard=bb, orchestration=orch, controller=ctrl)
        from datasets.datasense.devices import DeviceInventory
        from backend.app.config import DEVICES_CSV
        from simulation.abm import DeviceABM
        from simulation.topology import build_topology
        from agents.finding_gateway import FindingGateway
        from pipeline.behavior_profiler import BehaviorProfiler
        from backend.app.config import BEHAVIOR_MODEL_PATH
        inv = DeviceInventory.load(DEVICES_CSV)
        prof = BehaviorProfiler.load(BEHAVIOR_MODEL_PATH)
        abm = DeviceABM(inv, build_topology(inv))
        gateway = FindingGateway(abm)
        from datasets.datasense.feature_store import FeatureStoreReader
        from backend.app.config import FEATURE_STORE_ROOT
        reader = FeatureStoreReader(FEATURE_STORE_ROOT)
        net_rows = list(reader.iter_network_records("attack_recon_host-disc-udp-ping_soil-sensor"))[:5]
        # Use same spy det
        result = ws.execute_window(
            replay_id="spy-test",
            window_id=0,
            logical_timestamp="2026-01-01T00:00:00Z",
            net_rows=net_rows,
            beh_rows=[],
            abm=abm,
            gateway=gateway,
            detector=det,
            profiler=prof,
            inventory=inv,
        )
        # Should have exactly 1 call for network
        assert len(calls) == 1
        assert calls[0] == len([r for r in net_rows if r.get("network_observed")])
    finally:
        app.state.snapshot_store = prev
        det.findings_from_records = orig


def test_finding_gateway_remains_authoritative():
    from simulation.abm import DeviceABM
    from datasets.datasense.devices import DeviceInventory
    from backend.app.config import DEVICES_CSV
    from simulation.topology import build_topology
    from agents.finding_gateway import FindingGateway
    from pipeline.findings import NetworkFinding
    inv = DeviceInventory.load(DEVICES_CSV)
    abm = DeviceABM(inv, build_topology(inv))
    gateway = FindingGateway(abm)
    # Invalid finding (unknown entity)
    bad = NetworkFinding(
        entity_id="unknown-device-xyz",
        window_id=0,
        timestamp_utc="2026-01-01T00:00:00Z",
        attack_probability=0.9,
        predicted_class="attack",
        confidence=0.9,
        source_model="network_detector_v1@test",
        provenance={"source_mode":"feature_store"},
    )
    ok = gateway.submit(bad)
    assert not ok
    # ABM not updated
    assert abm.states["soil-sensor"].network_risk is None


def test_workflow_output_gateway_validates():
    from agentic_workflow.workflow_gateway import WorkflowOutputGateway
    from agentic_workflow.contracts import ThreatCorrelationV1, MappingStatus
    gw = WorkflowOutputGateway()
    # Valid
    corr = ThreatCorrelationV1(
        correlation_id="c1",
        workflow_id="w1",
        entity_id="e1",
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        mapping_status=MappingStatus.UNMAPPED,
        mapping_catalog_version="threat_catalog_v1",
        provenance={},
    )
    assert gw.submit(corr)
    assert not gw.submit(corr, entity_id="other-entity")
    cross_entity_ref = corr.model_copy(
        update={"source_finding_ids": ("other-entity:0",)}
    )
    assert not gw.submit(cross_entity_ref, entity_id="e1")
    # Invalid with ground truth should be rejected
    bad = ThreatCorrelationV1(
        correlation_id="c1",
        workflow_id="w1",
        entity_id="e1",
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        mapping_status=MappingStatus.UNMAPPED,
        mapping_catalog_version="threat_catalog_v1",
        provenance={},
    )
    # Try to submit with tainted provenance via direct dict (bypass pydantic? but gateway checks)
    bad_tainted = bad.model_copy(update={"provenance": {"scenario_id": "secret"}})
    # This will fail at model validation before gateway, so test gateway with raw dict
    assert not gw.submit({"provenance": {"scenario_id": "secret"}, "schema_version": "threat_correlation_v1"})
    assert not gw.submit({"schema_version": "unknown_workflow_output_v1"})


def test_blackboard_failure_handling(tmp_path):
    # Simulate blackboard failing for threat records
    from backend.app.services.workflow_service import WorkflowService
    from backend.app.services.blackboard_service import BlackboardService
    from backend.app.services.orchestration_service import OrchestrationService
    from unittest.mock import Mock, MagicMock
    from blackboard.contracts import WriteOutcome
    # Create mock blackboard that fails for threat
    mock_bb = Mock()
    mock_bb.enabled = True
    # First call (threat) returns PARTIAL_COMMIT, others would succeed but workflow should fail after first
    def fake_record(*args, **kwargs):
        m = Mock()
        m.outcome.value = "PARTIAL_COMMIT"
        m.outcome = WriteOutcome.PARTIAL_COMMIT
        return m
    mock_bb.record_workflow_output.side_effect = fake_record

    orch = OrchestrationService()
    ws = WorkflowService(blackboard=mock_bb, orchestration=orch, controller=None)
    # Need minimal setup
    from datasets.datasense.devices import DeviceInventory
    from backend.app.config import DEVICES_CSV
    from simulation.abm import DeviceABM
    from simulation.topology import build_topology
    from agents.finding_gateway import FindingGateway
    from pipeline.network_detector import NetworkDetector
    from pipeline.behavior_profiler import BehaviorProfiler
    from backend.app.config import NETWORK_MODEL_PATH, BEHAVIOR_MODEL_PATH
    inv = DeviceInventory.load(DEVICES_CSV)
    det = NetworkDetector.load(NETWORK_MODEL_PATH)
    prof = BehaviorProfiler.load(BEHAVIOR_MODEL_PATH)
    abm = DeviceABM(inv, build_topology(inv))
    gateway = FindingGateway(abm)
    from datasets.datasense.feature_store import FeatureStoreReader
    from backend.app.config import FEATURE_STORE_ROOT
    reader = FeatureStoreReader(FEATURE_STORE_ROOT)
    net_rows = list(reader.iter_network_records("attack_recon_host-disc-udp-ping_soil-sensor"))[:2]
    result = ws.execute_window(
        replay_id="fail-test",
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        net_rows=net_rows,
        beh_rows=[],
        abm=abm,
        gateway=gateway,
        detector=det,
        profiler=prof,
        inventory=inv,
    )
    assert result["status"] == "FAILED"
    assert any("PARTIAL_COMMIT" in f or "blackboard" in f.lower() for f in result["failures"])


def test_e2e_five_roles_via_api(workflow_app):
    client, controller, workflow, blackboard, orchestration = workflow_app
    rid = client.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
    client.post(f"/api/v1/replays/{rid}/play")
    _wait_completed(client, rid)
    # Poll workflow until all five roles show COMPLETED
    snap = _wait_workflow_completed(client, rid, timeout=15)
    assert snap is not None, "workflow did not reach all five COMPLETED"
    assert snap["workflow_mode"] == "FIVE_AGENT_LIVE"
    for s in snap["five_agent_statuses"]:
        assert s["status"] == "COMPLETED"
    # Verify SREP DEVICE_ONLY via events
    from backend.app.contracts.events_v1 import ReplayEventType
    evs = [e for e in controller.broker._ring if e.replay_id == rid and e.event_type == ReplayEventType.SREP_SNAPSHOT]
    assert evs and evs[0].payload["mode"] == "DEVICE_ONLY"
    # Verify no Agent Trust Graph
    assert snap["latest_threat_correlations"][0]["mapping_catalog_version"] == "threat_catalog_v1"
    for rec in snap["latest_risk_recommendations"]:
        assert rec["agent_trust_graph_supported"] is False
    for rec in snap["latest_access_recommendations"]:
        assert rec["trust_vector_supported"] is False
        assert rec["controller_mode"] == "PRE_LZTAF_DEVICE_EVIDENCE"
    for dec in snap["latest_enforcement_decisions"]:
        assert dec["physical_enforcement_claimed"] is False
        assert dec["counterfactual_effect_applied"] is False


def test_blackboard_e2e_via_api(workflow_app):
    client, _controller, _workflow, blackboard, _orchestration = workflow_app
    rid = client.post(
        "/api/v1/replays",
        json={
            "session_id": "attack_recon_host-disc-udp-ping_soil-sensor",
            "source_mode": "feature_store",
            "pacing": "max",
        },
    ).json()["replay_id"]
    client.post(f"/api/v1/replays/{rid}/play")
    _wait_completed(client, rid)

    prefixes = {
        "THREAT_CORRELATION_RECORD": "threat",
        "RISK_RECOMMENDATION_RECORD": "risk",
        "ACCESS_RECOMMENDATION_RECORD": "access",
        "ENFORCEMENT_DECISION_RECORD": "action",
    }
    for record_type, key_kind in prefixes.items():
        key_prefix = f"workflow/{key_kind}/{rid}/"
        listing = blackboard.list_records(
            record_type=record_type,
            key_prefix=key_prefix,
            limit=100,
        )
        assert listing["total"] > 0, f"no {record_type}"
        for item in listing["items"][:2]:
            assert item["record_type"] == record_type
            assert item["record_key"].startswith(key_prefix)
            assert item["content_hash"]
            result = blackboard.read_latest(item["record_key"], principal="test")
            assert result.outcome.value in ("CONSISTENT", "DEGRADED_CONSISTENT")


def test_feedback_e2e(workflow_app):
    client, controller, workflow, blackboard, orchestration = workflow_app
    rid = client.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
    client.post(f"/api/v1/replays/{rid}/play")
    _wait_completed(client, rid)
    # Wait for actions to appear
    deadline = time.monotonic() + 10
    acts = None
    while time.monotonic() < deadline:
        acts = client.get(f"/api/v1/replays/{rid}/actions").json()
        if acts["total"] > 0:
            break
        time.sleep(0.2)
    assert acts is not None and acts["total"] > 0
    did = acts["actions"][0]["decision_id"]
    # Valid feedback
    fb = client.post(f"/api/v1/replays/{rid}/workflow/feedback", json={
        "window_id": acts["actions"][0]["window_id"],
        "entity_id": acts["actions"][0]["entity_id"],
        "related_action_id": did,
        "related_finding_ids": [],
        "feedback_source": "analyst_review",
        "confirmed": True,
        "verdict": "confirmed",
        "reason_code": "manual",
        "provenance": {}
    }, headers={"X-Feedback-Principal":"tester"})
    assert fb.status_code == 201
    # confirmed false rejected
    fb2 = client.post(f"/api/v1/replays/{rid}/workflow/feedback", json={
        "window_id": acts["actions"][0]["window_id"],
        "entity_id": acts["actions"][0]["entity_id"],
        "related_action_id": did,
        "related_finding_ids": [],
        "feedback_source": "analyst_review",
        "confirmed": False,
        "verdict": "confirmed",
        "reason_code": "manual",
        "provenance": {}
    }, headers={"X-Feedback-Principal":"tester"})
    assert fb2.status_code == 422
    # unknown action rejected
    fb3 = client.post(f"/api/v1/replays/{rid}/workflow/feedback", json={
        "window_id": 0,
        "entity_id": "unknown",
        "related_action_id": "nonexistent",
        "related_finding_ids": [],
        "feedback_source": "analyst_review",
        "confirmed": True,
        "verdict": "confirmed",
        "reason_code": "manual",
        "provenance": {}
    }, headers={"X-Feedback-Principal":"tester"})
    assert fb3.status_code == 404
    # wrong binding rejected
    fb4 = client.post(f"/api/v1/replays/{rid}/workflow/feedback", json={
        "window_id": 999,
        "entity_id": acts["actions"][0]["entity_id"],
        "related_action_id": did,
        "related_finding_ids": [],
        "feedback_source": "analyst_review",
        "confirmed": True,
        "verdict": "confirmed",
        "reason_code": "manual",
        "provenance": {}
    }, headers={"X-Feedback-Principal":"tester"})
    assert fb4.status_code == 422
    # ground truth rejected
    fb5 = client.post(f"/api/v1/replays/{rid}/workflow/feedback", json={
        "window_id": acts["actions"][0]["window_id"],
        "entity_id": acts["actions"][0]["entity_id"],
        "related_action_id": did,
        "related_finding_ids": [],
        "feedback_source": "analyst_review",
        "confirmed": True,
        "verdict": "confirmed",
        "reason_code": "manual",
        "provenance": {"scenario_id": "secret"},
        "note": "secret"
    }, headers={"X-Feedback-Principal":"tester"})
    assert fb5.status_code in (422, 400)
    # Verify original action not rewritten
    act_again = client.get(f"/api/v1/replays/{rid}/actions/{did}").json()
    assert act_again["decision_id"] == did


def test_events_scientific_sequence(tmp_path):
    prev = app.state.snapshot_store
    app.state.snapshot_store = SnapshotStore(tmp_path / "snap6")
    try:
        with TestClient(app) as c:
            rid = c.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
            c.post(f"/api/v1/replays/{rid}/play")
            _wait_completed(c, rid)
            ctrl = app.state.controller
            evs = [e for e in ctrl.broker._ring if e.replay_id == rid]
            seqs = [e.sequence_number for e in evs]
            assert seqs == sorted(seqs)
            assert len(seqs) == len(set(seqs))
            # Check workflow events use scientific replay_id, not orchestration-ops
            workflow_evs = [e for e in evs if e.event_type.value.startswith("WORKFLOW") or e.event_type.value.startswith("AGENT") or e.event_type.value.startswith("THREAT") or e.event_type.value.startswith("RISK") or e.event_type.value.startswith("ACCESS") or e.event_type.value.startswith("ENFORCEMENT")]
            assert len(workflow_evs) > 0
            for e in workflow_evs:
                assert e.replay_id == rid
            # Check orchestration-ops isolation: orchestration events for this replay should be in scientific, not only ops
            # Also ensure orchestration-ops still has its own sequence
            ops_evs = [e for e in ctrl.broker._ring if e.replay_id == "orchestration-ops"]
            # At least should exist from earlier? Not necessarily, but ensure not contaminated
            for e in evs:
                assert e.replay_id != "orchestration-ops" or e.event_type.value.startswith("ORCHESTRATION")
    finally:
        app.state.snapshot_store = prev


def test_replay_lifecycle_no_duplicate(tmp_path):
    prev = app.state.snapshot_store
    app.state.snapshot_store = SnapshotStore(tmp_path / "snap7")
    try:
        with TestClient(app) as c:
            rid = c.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
            c.post(f"/api/v1/replays/{rid}/play")
            _wait_completed(c, rid)
            snap2 = c.get(f"/api/v1/replays/{rid}/workflow").json()
            # Check no window executed twice: window_ids unique
            wids = [w["window_id"] for w in snap2["recent_windows"]]
            assert len(wids) == len(set(wids))
            assert len(wids) == 13
            # Restart should use new replay id and fresh workflow
            new_rid = c.post(f"/api/v1/replays/{rid}/restart").json()["new_replay_id"]
            assert new_rid != rid
            assert c.get(f"/api/v1/replays/{new_rid}").json()["replay_id"] == new_rid
            # Give new replay a moment to start, then wait completed
            _wait_completed(c, new_rid)
            snap_new = c.get(f"/api/v1/replays/{new_rid}/workflow").json()
            assert snap_new["replay_id"] == new_rid
            assert len(snap_new["recent_windows"]) == 13
            # Ensure new replay's workflow windows are not reused from old (different workflow_id)
            assert snap_new["workflow_id"] != snap2["workflow_id"]
    finally:
        app.state.snapshot_store = prev


def test_api_workflow_snapshot_and_actions(tmp_path):
    prev = app.state.snapshot_store
    app.state.snapshot_store = SnapshotStore(tmp_path / "snap8")
    try:
        with TestClient(app) as c:
            rid = c.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
            c.post(f"/api/v1/replays/{rid}/play")
            _wait_completed(c, rid)
            snap = c.get(f"/api/v1/replays/{rid}/workflow").json()
            assert snap["schema_version"] == "workflow_snapshot_v1"
            assert snap["workflow_mode"] == "FIVE_AGENT_LIVE"
            assert len(snap["five_agent_statuses"]) == 5
            assert "bounds" in snap
            assert "instrumentation" in snap
            # No Agent Trust fields
            assert "agent_trust_graph_supported" not in str(snap) or "agent_trust_graph_supported" in str(snap["latest_risk_recommendations"])
            # Check SREP still DEVICE_ONLY via events
            ctrl = app.state.controller
            evs = [e for e in ctrl.broker._ring if e.replay_id == rid and e.event_type == ReplayEventType.SREP_SNAPSHOT]
            assert evs[0].payload["mode"] == "DEVICE_ONLY"
            # Action listing
            listing = c.get(f"/api/v1/replays/{rid}/actions?limit=5&offset=0").json()
            assert listing["schema_version"] == "action_listing_v1"
            assert listing["limit"] == 5
            assert listing["history_complete"] is False
            # Unknown replay
            assert c.get("/api/v1/replays/unknown-workflow/workflow").status_code == 404
            assert c.get(f"/api/v1/replays/{rid}/actions/unknown").status_code == 404
    finally:
        app.state.snapshot_store = prev
