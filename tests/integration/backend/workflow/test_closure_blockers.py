"""Stage-8 corrective-closure integration tests."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from agentic_workflow.contracts import AgentId


def _wait_completed(client, rid, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = client.get(f"/api/v1/replays/{rid}").json()
        if st.get("state") in ("COMPLETED", "FAILED"):
            return st
        time.sleep(0.2)
    raise TimeoutError("replay not completed")


def test_multi_entity_isolation(workflow_app):
    """Blocker A: two entities in same window must have isolated chains."""
    _client, _controller, workflow, _blackboard, _orchestration = workflow_app

    from agents.finding_gateway import FindingGateway
    from datasets.datasense.devices import DeviceInventory
    from backend.app.config import DEVICES_CSV
    from pipeline.findings import NetworkFinding
    from simulation.abm import DeviceABM
    from simulation.topology import build_topology

    inv = DeviceInventory.load(DEVICES_CSV)
    eligible = sorted(
        entity_id
        for entity_id, state in DeviceABM(inv, build_topology(inv)).states.items()
        if state.is_protected_asset and not state.behavior_supported
    )
    assert len(eligible) >= 2
    low_entity, high_entity = eligible[:2]
    risks = {low_entity: 0.1, high_entity: 0.9}

    class Detector:
        def findings_from_records(self, records, **_kwargs):
            return [
                NetworkFinding(
                    entity_id=row["device_id"],
                    window_id=0,
                    timestamp_utc="2026-01-01T00:00:00Z",
                    attack_probability=risks[row["device_id"]],
                    predicted_class=(
                        "attack" if risks[row["device_id"]] >= 0.5 else "benign"
                    ),
                    confidence=0.9,
                    source_model="closure-detector-v1",
                    provenance={"source_mode": "feature_store"},
                )
                for row in records
            ]

    class Profiler:
        def predict_record(self, *_args, **_kwargs):
            return None

    def run(
        replay_id,
        rows,
        *,
        reverse_state_order=False,
        logical_timestamp="2026-01-01T00:00:00Z",
    ):
        abm = DeviceABM(inv, build_topology(inv))
        if reverse_state_order:
            abm.states = dict(reversed(tuple(abm.states.items())))

        def deterministic_propagate():
            for entity_id, risk in risks.items():
                state = abm.states[entity_id]
                state.network_observed = True
                state.network_risk = risk
                state.behavior_risk = None
                state.propagated_risk = 0.0
                state.systemic_risk = risk

        abm.propagate = deterministic_propagate
        result = workflow.execute_window(
            replay_id=replay_id,
            window_id=0,
            logical_timestamp=logical_timestamp,
            net_rows=rows,
            beh_rows=[],
            abm=abm,
            gateway=FindingGateway(abm),
            detector=Detector(),
            profiler=Profiler(),
            inventory=inv,
        )
        assert result["status"] == "COMPLETED"
        return workflow._get_state(replay_id)

    rows = [
        {"device_id": low_entity, "network_observed": True},
        {"device_id": high_entity, "network_observed": True},
    ]
    state = run("multi-entity-test", rows)
    reordered = run(
        "multi-entity-reordered",
        list(reversed(rows)),
        reverse_state_order=True,
    )
    generated_timestamp = run("multi-entity-generated-timestamp", rows, logical_timestamp=None)

    def chain_semantics(replay_state):
        correlations = {item.entity_id: item for item in replay_state.recent_correlations}
        risk_recommendations = {item.entity_id: item for item in replay_state.recent_risks}
        access_recommendations = {item.entity_id: item for item in replay_state.recent_access}
        actions = {item.entity_id: item for item in replay_state.recent_actions}
        assert set(correlations) == set(risks)
        assert set(risk_recommendations) == set(risks)
        assert set(access_recommendations) == set(risks)
        assert set(actions) == set(risks)

        semantics = []
        for entity_id, expected_risk in sorted(risks.items()):
            correlation = correlations[entity_id]
            risk = risk_recommendations[entity_id]
            access = access_recommendations[entity_id]
            action = actions[entity_id]
            assert correlation.source_finding_ids == (f"{entity_id}:0",)
            assert correlation.evidence_refs == (f"finding:{entity_id}",)
            assert risk.threat_correlation_refs == (correlation.correlation_id,)
            assert risk.systemic_risk == expected_risk
            assert access.evidence_refs == (
                risk.recommendation_id,
                correlation.correlation_id,
            )
            assert action.controller_recommendation_id == access.recommendation_id
            assert action.evidence_refs == access.evidence_refs
            semantics.append((entity_id, expected_risk, action.action.value))
        return semantics

    expected = [
        (high_entity, 0.9, "BLOCK"),
        (low_entity, 0.1, "ALLOW"),
    ]
    assert sorted(chain_semantics(state)) == sorted(expected)
    assert chain_semantics(reordered) == chain_semantics(state)
    timestamps = {
        item.logical_timestamp
        for collection in (
            generated_timestamp.recent_correlations,
            generated_timestamp.recent_risks,
            generated_timestamp.recent_access,
            generated_timestamp.recent_actions,
        )
        for item in collection
    }
    assert len(timestamps) == 1


def test_empty_evidence_has_no_arbitrary_entity_chain(workflow_app):
    """An empty window may complete, but cannot invent an entity-scoped chain."""
    _client, _controller, workflow, blackboard, _orchestration = workflow_app

    from agents.finding_gateway import FindingGateway
    from backend.app.config import DEVICES_CSV
    from datasets.datasense.devices import DeviceInventory
    from simulation.abm import DeviceABM
    from simulation.topology import build_topology

    inventory = DeviceInventory.load(DEVICES_CSV)
    abm = DeviceABM(inventory, build_topology(inventory))
    result = workflow.execute_window(
        replay_id="empty-evidence-test",
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        net_rows=[],
        beh_rows=[],
        abm=abm,
        gateway=FindingGateway(abm),
        detector=object(),
        profiler=object(),
        inventory=inventory,
    )

    assert result["status"] == "COMPLETED"
    assert result["entity_id"] == "window-scope"
    state = workflow._get_state("empty-evidence-test")
    assert list(state.recent_correlations) == []
    assert list(state.recent_risks) == []
    assert list(state.recent_access) == []
    assert list(state.recent_actions) == []
    assert state.window_states[0].entity_ids == []
    assert blackboard.list_records(key_prefix="workflow/", limit=10)["total"] == 0


def test_feature_store_and_direct_raw_workflow_semantics_match(workflow_app):
    """Equivalent input modes must produce equivalent workflow semantics."""
    client, _controller, workflow, _blackboard, _orchestration = workflow_app

    states = {}
    for source_mode in ("feature_store", "direct_raw"):
        response = client.post(
            "/api/v1/replays",
            json={
                "session_id": "attack_recon_host-disc-udp-ping_soil-sensor",
                "source_mode": source_mode,
                "pacing": "max",
            },
        )
        assert response.status_code == 201
        replay_id = response.json()["replay_id"]
        assert client.post(f"/api/v1/replays/{replay_id}/play").status_code == 200
        status = _wait_completed(client, replay_id, timeout=120)
        assert status["state"] == "COMPLETED"
        states[source_mode] = workflow._get_state(replay_id)

    def semantics(state):
        correlations = sorted(
            (
                item.window_id,
                item.entity_id,
                item.mapping_status.value,
                item.threat_behavior_id,
                item.source_finding_ids,
            )
            for item in state.recent_correlations
        )
        risks = sorted(
            (
                item.window_id,
                item.entity_id,
                item.network_risk,
                item.behavior_risk,
                item.propagated_risk,
                item.systemic_risk,
                item.evidence_complete,
                item.recommended_escalation,
            )
            for item in state.recent_risks
        )
        actions = sorted(
            (
                item.window_id,
                item.entity_id,
                item.action.value,
                item.evidence_complete,
                item.behavior_supported,
                item.physical_enforcement_claimed,
                item.counterfactual_effect_applied,
            )
            for item in state.recent_actions
        )
        return correlations, risks, actions

    store_semantics = semantics(states["feature_store"])
    direct_semantics = semantics(states["direct_raw"])
    assert store_semantics[0]
    assert store_semantics[1]
    assert store_semantics[2]
    assert direct_semantics == store_semantics


def test_live_action_idempotency_and_conflict(workflow_app):
    """Blocker B: identical retry idempotent, conflicting retry rejected, PARTIAL not success."""
    _client, _controller, _workflow, blackboard, _orchestration = workflow_app

    # Use the workflow's committer directly via Blackboard
    from agentic_workflow.contracts import AccessRecommendationV1, ActionType, ControllerMode
    from agentic_workflow.action_commit import ActionCommitter
    from agentic_workflow.blackboard_ledger import BlackboardActionLedger
    # Create a valid AccessRecommendation
    rec = AccessRecommendationV1(
        recommendation_id="rec-idempotent-123",
        workflow_id="wf-test",
        entity_id="sensor-1",
        window_id=5,
        logical_timestamp="2026-01-01T00:00:00Z",
        action=ActionType.ALLOW,
        policy_id="stage8_access_policy_v1",
        policy_version="1",
        controller_mode=ControllerMode.PRE_LZTAF_DEVICE_EVIDENCE,
        evidence_complete=True,
        behavior_supported=True,
        source_component="agentic_workflow.access_controller",
        provenance={},
    )

    ledger = BlackboardActionLedger(blackboard, cache_limit=10)
    committer = ActionCommitter(ledger=ledger)

    # First commit
    dec1 = committer.commit(
        rec,
        workflow_id="wf-test",
        replay_id="replay-test",
        window_id=5,
        logical_timestamp="2026-01-01T00:00:00Z",
        entity_id="sensor-1",
    )
    assert dec1.action == ActionType.ALLOW

    # Identical retry should be idempotent (same decision_id)
    dec2 = committer.commit(
        rec,
        workflow_id="wf-test",
        replay_id="replay-test",
        window_id=5,
        logical_timestamp="2026-01-01T00:00:00Z",
        entity_id="sensor-1",
    )
    assert dec1.decision_id == dec2.decision_id

    # A cold ledger/committer must return the persisted decision, not a new UUID.
    restarted_committer = ActionCommitter(
        ledger=BlackboardActionLedger(blackboard, cache_limit=10)
    )
    dec3 = restarted_committer.commit(
        rec,
        workflow_id="wf-test",
        replay_id="replay-test",
        window_id=5,
        logical_timestamp="2026-01-01T00:00:00Z",
        entity_id="sensor-1",
    )
    assert dec3.decision_id == dec1.decision_id
    # No extra version should have been created (Blackboard should still have 1 record for that key)
    listing = blackboard.list_records(record_type="ENFORCEMENT_DECISION_RECORD", key_prefix="workflow/action/replay-test/5/sensor-1", limit=10)
    # Should have exactly 1 committed record (not 2)
    assert listing["total"] == 1

    # Conflicting retry (different action) should be rejected
    rec_conflict = rec.model_copy(update={"action": ActionType.BLOCK, "recommendation_id": "rec-conflict-999"})
    with pytest.raises(ValueError, match="conflicting"):
        restarted_committer.commit(
            rec_conflict,
            workflow_id="wf-test",
            replay_id="replay-test",
            window_id=5,
            logical_timestamp="2026-01-01T00:00:00Z",
            entity_id="sensor-1",
        )

    wrong_workflow = rec.model_copy(update={"workflow_id": "wf-other"})
    with pytest.raises(RuntimeError, match="workflow mismatch"):
        restarted_committer.commit(
            wrong_workflow,
            workflow_id="wf-other",
            replay_id="replay-test",
            window_id=5,
            logical_timestamp="2026-01-01T00:00:00Z",
            entity_id="sensor-1",
        )
    # Original should remain unchanged
    listing2 = blackboard.list_records(record_type="ENFORCEMENT_DECISION_RECORD", key_prefix="workflow/action/replay-test/5/sensor-1", limit=10)
    assert listing2["total"] == 1
    item = listing2["items"][0]
    assert item["record_version"] == 1
    stored = blackboard.read_latest(item["record_key"], principal="closure-test")
    assert stored.outcome.value in ("CONSISTENT", "DEGRADED_CONSISTENT")
    assert stored.record.payload["decision_id"] == dec1.decision_id
    assert stored.record.payload["action"] == "ALLOW"
    assert stored.record.payload["controller_recommendation_id"] == rec.recommendation_id

    class PartialBlackboard:
        enabled = True

        def read_latest(self, *_args, **_kwargs):
            return SimpleNamespace(
                outcome=SimpleNamespace(value="NOT_FOUND"),
                record=None,
            )

        def record_workflow_output(self, **_kwargs):
            return SimpleNamespace(
                outcome=SimpleNamespace(value="PARTIAL_COMMIT"),
                reason="one durable acknowledgement",
            )

    partial_ledger = BlackboardActionLedger(PartialBlackboard(), cache_limit=2)
    partial_committer = ActionCommitter(ledger=partial_ledger)
    with pytest.raises(RuntimeError, match="not COMMITTED: PARTIAL_COMMIT"):
        partial_committer.commit(
            rec.model_copy(update={"recommendation_id": "rec-partial-123"}),
            workflow_id="wf-test",
            replay_id="partial-replay",
            window_id=5,
            logical_timestamp="2026-01-01T00:00:00Z",
            entity_id="sensor-1",
        )
    assert partial_ledger.get(("wf-test", "partial-replay", 5, "sensor-1")) is None

    class NonAuthoritativeBlackboard:
        enabled = True
        write_attempted = False

        def read_latest(self, *_args, **_kwargs):
            return SimpleNamespace(
                outcome=SimpleNamespace(value="INSUFFICIENT_QUORUM"),
                record=None,
            )

        def record_workflow_output(self, **_kwargs):
            self.write_attempted = True
            raise AssertionError("write must not follow a non-authoritative read")

    unavailable = NonAuthoritativeBlackboard()
    unavailable_committer = ActionCommitter(
        ledger=BlackboardActionLedger(unavailable, cache_limit=2)
    )
    with pytest.raises(RuntimeError, match="non-authoritative action read"):
        unavailable_committer.commit(
            rec,
            workflow_id="wf-test",
            replay_id="unavailable-replay",
            window_id=5,
            logical_timestamp="2026-01-01T00:00:00Z",
            entity_id="sensor-1",
        )
    assert unavailable.write_attempted is False


def test_scientific_orchestration_events_projection(workflow_app):
    """Blocker C: real Stage-6 facts projected into scientific replay."""
    client, controller, workflow, blackboard, orchestration = workflow_app

    rid = client.post("/api/v1/replays", json={"session_id":"attack_recon_host-disc-udp-ping_soil-sensor","source_mode":"feature_store","pacing":"max"}).json()["replay_id"]
    client.post(f"/api/v1/replays/{rid}/play")
    deadline = __import__("time").monotonic() + 60
    while __import__("time").monotonic() < deadline:
        st = client.get(f"/api/v1/replays/{rid}").json()
        if st.get("state") == "COMPLETED":
            break
        time.sleep(0.2)
    assert st["state"] == "COMPLETED"

    # Get scientific events
    evs = [e for e in controller.broker._ring if e.replay_id == rid]
    types = [e.event_type.value for e in evs]

    # Check required scientific orchestration events
    assert "ORCHESTRATION_REQUEST_RECEIVED" in types
    assert "ORCHESTRATOR_PROPOSAL" in types
    assert "ORCHESTRATOR_VOTE" in types
    assert "ORCHESTRATION_DECISION" in types
    # At least one of quorum/no-quorum
    assert "ORCHESTRATION_QUORUM_REACHED" in types or "ORCHESTRATION_NO_QUORUM" in types

    # All have scientific replay_id and monotonic sequence
    for e in evs:
        if e.event_type.value.startswith("ORCHESTRATION") or e.event_type.value.startswith("ORCHESTRATOR"):
            assert e.replay_id == rid
    seqs = [e.sequence_number for e in evs]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))

    decisions = {
        event.payload["decision_id"]: (index, event)
        for index, event in enumerate(evs)
        if event.event_type.value == "ORCHESTRATION_DECISION"
    }
    dispatches = [
        (index, event)
        for index, event in enumerate(evs)
        if event.event_type.value == "AGENT_DISPATCHED"
    ]
    assert decisions
    assert dispatches
    for dispatch_index, dispatch in dispatches:
        decision_index, decision = decisions[dispatch.payload["decision_id"]]
        assert decision_index < dispatch_index
        assert dispatch.payload["request_id"] == decision.payload["request_id"]
        assert dispatch.payload["round_id"] == decision.payload["round_id"]
        assert dispatch.payload["selected_route_id"] == decision.payload["selected_route_id"]

    proposals = [e for e in evs if e.event_type.value == "ORCHESTRATOR_PROPOSAL"]
    votes = [e for e in evs if e.event_type.value == "ORCHESTRATOR_VOTE"]
    assert proposals
    assert votes
    proposal_digests = {e.payload["proposal_digest"] for e in proposals}
    assert all(e.payload["request_id"] for e in proposals)
    assert all(e.payload["round_id"] for e in proposals)
    assert all(e.payload["decision_id"] in decisions for e in proposals)
    assert all(e.payload["message_hash"] for e in proposals)
    assert all(e.payload["authentication_verified"] is True for e in proposals)
    assert all(e.payload["selected_proposal_digest"] in proposal_digests for e in votes)
    assert all(e.payload["request_id"] for e in votes)
    assert all(e.payload["round_id"] for e in votes)
    assert all(e.payload["decision_id"] in decisions for e in votes)
    assert all(e.payload["vote"] in ("APPROVE", "REJECT") for e in votes)
    assert all(e.payload["message_hash"] for e in votes)
    assert all(e.payload["authentication_verified"] is True for e in votes)

    # Ensure orchestration-ops is not contaminated with scientific dispatches.
    ops_evs = [
        e
        for e in controller.broker._ring
        if e.replay_id == "orchestration-ops"
        and e.event_type.value.startswith(("ORCHESTRATION", "ORCHESTRATOR"))
    ]
    scientific_request_ids = {
        e.payload["request_id"]
        for e in evs
        if e.event_type.value == "ORCHESTRATION_REQUEST_RECEIVED"
    }
    assert not any(e.payload.get("request_id") in scientific_request_ids for e in ops_evs)


def test_window_states_bounded(workflow_app):
    """Blocker D: window_states bounded, eviction, Blackboard survives."""
    client, controller, workflow, blackboard, orchestration = workflow_app
    # Use tiny bound
    workflow.window_states_limit = 3
    # Also set the per-replay state's limit
    # Create a replay and run 5 windows (exceed limit 3)
    # We will directly use workflow.execute_window 5 times with same replay_id but different window_ids
    from datasets.datasense.devices import DeviceInventory
    from backend.app.config import DEVICES_CSV, NETWORK_MODEL_PATH, BEHAVIOR_MODEL_PATH
    from simulation.abm import DeviceABM
    from simulation.topology import build_topology
    from agents.finding_gateway import FindingGateway
    from pipeline.network_detector import NetworkDetector
    from pipeline.behavior_profiler import BehaviorProfiler

    inv = DeviceInventory.load(DEVICES_CSV)
    det = NetworkDetector.load(NETWORK_MODEL_PATH)
    prof = BehaviorProfiler.load(BEHAVIOR_MODEL_PATH)
    abm = DeviceABM(inv, build_topology(inv))
    gateway = FindingGateway(abm)

    from datasets.datasense.feature_store import FeatureStoreReader
    from backend.app.config import FEATURE_STORE_ROOT
    reader = FeatureStoreReader(FEATURE_STORE_ROOT)
    net_rows = list(reader.iter_network_records("attack_recon_host-disc-udp-ping_soil-sensor"))[:2]
    beh_rows = list(reader.iter_behavior_records("attack_recon_host-disc-udp-ping_soil-sensor"))[:2]

    replay_id = "bound-test-replay"
    for wid in range(5):
        window_net_rows = [{**row, "window_id": wid} for row in net_rows]
        window_beh_rows = [{**row, "window_id": wid} for row in beh_rows]
        res = workflow.execute_window(
            replay_id=replay_id,
            window_id=wid,
            logical_timestamp="2026-01-01T00:00:00Z",
            net_rows=window_net_rows,
            beh_rows=window_beh_rows,
            abm=abm,
            gateway=gateway,
            detector=det,
            profiler=prof,
            inventory=inv,
        )
        assert res["status"] == "COMPLETED"

    state = workflow._get_state(replay_id)
    assert list(state.window_states) == [2, 3, 4]
    assert all(item.status == "COMPLETED" for item in state.window_states.values())
    assert len(state.recent_windows) <= 64
    assert state.recent_windows[-1].window_id == 4
    snapshot = workflow.snapshot(replay_id)
    assert snapshot["bounds"]["window_states"] == 3
    assert snapshot["bounds"]["window_states_current"] == 3

    listing = blackboard.list_records(record_type="THREAT_CORRELATION_RECORD", key_prefix=f"workflow/threat/{replay_id}/0/", limit=10)
    assert listing["total"] >= 1, "Blackboard evidence should survive window_states eviction"

    from backend.app.services.workflow_service import WorkflowService, WorkflowWindowState

    active_service = WorkflowService(window_states_limit=1)
    active_state = active_service._get_state("active-bound-test")
    first = WorkflowWindowState(
        window_id=0,
        workflow_id=active_state.workflow_id,
        replay_id=active_state.replay_id,
        entity_id="window-scope",
        logical_timestamp="2026-01-01T00:00:00Z",
    )
    second = WorkflowWindowState(
        window_id=1,
        workflow_id=active_state.workflow_id,
        replay_id=active_state.replay_id,
        entity_id="window-scope",
        logical_timestamp="2026-01-01T00:00:05Z",
    )
    active_service._remember_window_state(active_state, first)
    with pytest.raises(RuntimeError, match="duplicate workflow window 0"):
        active_service._remember_window_state(active_state, first)
    with pytest.raises(RuntimeError, match="capacity exhausted by active windows"):
        active_service._remember_window_state(active_state, second)
    assert list(active_state.window_states) == [0]
    assert active_state.window_states[0] is first

    with pytest.raises(ValueError, match="window_states_limit must be positive"):
        WorkflowService(window_states_limit=0)


def test_no_fallback_real_no_quorum(workflow_app):
    """Blocker: NO_QUORUM/TIMED_OUT/INSUFFICIENT must cause zero execution."""
    from backend.app.services.workflow_service import WorkflowService
    from unittest.mock import Mock

    assert (
        WorkflowService(orchestration=None)._dispatch_via_orchestration(
            "missing-orchestration",
            0,
            "2026-01-01T00:00:00Z",
            {AgentId.network_anomaly_detector},
        )
        is None
    )

    # Create fake orchestration that returns NO_QUORUM, TIMED_OUT, INSUFFICIENT
    for outcome_val in ["NO_QUORUM", "TIMED_OUT", "INSUFFICIENT_RESPONSES"]:
        fake_dec = Mock()
        fake_dec.outcome.value = outcome_val
        fake_dec.outcome = type("O", (), {"value": outcome_val})()
        fake_dec.selected_route_id = None
        fake_orch = Mock()
        fake_orch.coordinator.adjudicate.return_value = fake_dec

        # Need a fresh workflow with this fake orchestration but real Blackboard
        from backend.app.services.blackboard_service import BlackboardService
        import tempfile
        from pathlib import Path
        tmpdir = tempfile.mkdtemp()
        bb = BlackboardService(root=Path(tmpdir), enabled=True)
        ws = WorkflowService(blackboard=bb, orchestration=fake_orch, controller=None)

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
            replay_id=f"no-fallback-{outcome_val}",
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
        assert result["status"] == "FAILED", f"should fail for {outcome_val}"
        assert len(result["executions"]) == 0, f"should have zero executions for {outcome_val}"
        # No Blackboard workflow records should have been created
        listing = bb.list_records(key_prefix="workflow/", limit=10)
        # For NO_QUORUM etc., no threat/risk/access/action should be committed
        # Check that no workflow records exist for that replay
        assert listing["total"] == 0, f"should have no workflow records for {outcome_val}, got {listing['total']}"
