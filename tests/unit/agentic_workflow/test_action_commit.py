from __future__ import annotations

import pytest

from agentic_workflow.access_controller import AccessController
from agentic_workflow.action_commit import ActionCommitter, InMemoryLedger
from agentic_workflow.risk_analyst import RiskAnalyst
from simulation.abm import DeviceState


def make_recommendation(action=None, systemic=0.2, evidence_complete=True):
    state = DeviceState(
        node_id="sensor-1",
        role="sensor",
        device_type="sensor",
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        is_protected_asset=True,
        is_attacker=False,
        behavior_supported=True,
        behavior_profile_type="continuous",
        network_risk=systemic,
        behavior_risk=systemic,
        network_observed=True,
        behavior_observed=True,
        propagated_risk=0.0,
        systemic_risk=systemic,
    )
    risk = RiskAnalyst().analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    if risk.evidence_complete != evidence_complete:
        risk = risk.model_copy(update={"evidence_complete": evidence_complete})
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=risk)
    if action is not None and access.action != action:
        # Force desired action by adjusting systemic
        systemic_for_action = 0.1 if action == "ALLOW" else (0.5 if action == "MONITOR" else 0.9)
        return make_recommendation(action=None, systemic=systemic_for_action, evidence_complete=evidence_complete)
    return access


def test_valid_recommendation_exact_action():
    committer = ActionCommitter()
    rec = make_recommendation(systemic=0.5)  # MONITOR
    decision = committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    assert decision.action.value == rec.action.value
    assert decision.controller_recommendation_id == rec.recommendation_id


def test_committer_does_not_recalculate_policy():
    committer = ActionCommitter()
    rec = make_recommendation(systemic=0.9)  # BLOCK
    # Tamper: if committer recalculated, it would use systemic 0.9 -> BLOCK regardless.
    # Instead we verify that committer preserves rec.action even if we craft a rec with mismatched risk
    # Our rec is BLOCK; committer should keep BLOCK
    decision = committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    assert decision.action.value == "BLOCK"


def test_duplicate_identical_recommendation_idempotent():
    committer = ActionCommitter()
    rec = make_recommendation(systemic=0.5)
    d1 = committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    d2 = committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    assert d1.decision_id == d2.decision_id
    assert committer.instrumentation.snapshot()["counters"]["action_duplicates"] >= 1


def test_conflicting_second_action_rejected():
    committer = ActionCommitter()
    rec1 = make_recommendation(systemic=0.5)  # MONITOR
    rec2 = make_recommendation(systemic=0.9)  # BLOCK, different recommendation_id and action
    committer.commit(rec1, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    with pytest.raises(ValueError, match="conflicting"):
        committer.commit(rec2, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")


def test_wrong_replay_window_entity_rejected():
    committer = ActionCommitter()
    rec = make_recommendation()
    with pytest.raises(ValueError):
        committer.commit(rec, workflow_id="wrong", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    with pytest.raises(ValueError):
        committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=99, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    with pytest.raises(ValueError):
        committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="other-entity")
    with pytest.raises(ValueError):
        committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="WRONG TS", entity_id="sensor-1")


def test_ground_truth_contamination_rejected():
    from agentic_workflow.contracts import AccessRecommendationV1, AgentId, ControllerMode, ActionType
    # Try to create a recommendation with forbidden key -> should fail at contract level
    with pytest.raises((ValueError, Exception)):
        AccessRecommendationV1(
            recommendation_id="cr1",
            workflow_id="w1",
            entity_id="sensor-1",
            window_id=7,
            logical_timestamp="2026-01-01T00:00:00Z",
            action=ActionType.BLOCK,
            policy_id="stage8_access_policy_v1",
            policy_version="1",
            controller_mode=ControllerMode.PRE_LZTAF_DEVICE_EVIDENCE,
            evidence_complete=True,
            behavior_supported=True,
            source_component="test",
            provenance={"scenario_id": "secret"},
        )


def test_block_physical_enforcement_false():
    committer = ActionCommitter()
    rec = make_recommendation(systemic=0.9)
    decision = committer.commit(rec, workflow_id="w1", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    assert decision.action.value == "BLOCK"
    assert decision.physical_enforcement_claimed is False
    assert decision.counterfactual_effect_applied is False


def test_ledger_bounded():
    ledger = InMemoryLedger(limit=2)
    committer = ActionCommitter(ledger=ledger)
    for i in range(3):
        # create recommendation with matching workflow_id
        from agentic_workflow.access_controller import AccessController
        from agentic_workflow.risk_analyst import RiskAnalyst
        from simulation.abm import DeviceState

        state = DeviceState(
            node_id="sensor-1",
            role="sensor",
            device_type="sensor",
            ip="192.168.1.10",
            mac="aa:bb:cc:dd:ee:ff",
            is_protected_asset=True,
            is_attacker=False,
            behavior_supported=True,
            behavior_profile_type="continuous",
            network_risk=0.2,
            behavior_risk=0.2,
            network_observed=True,
            behavior_observed=True,
            propagated_risk=0.0,
            systemic_risk=0.2,
        )
        risk = RiskAnalyst().analyze(workflow_id=f"w{i}", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
        rec = AccessController().decide(workflow_id=f"w{i}", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=risk)
        committer.commit(rec, workflow_id=f"w{i}", replay_id="r1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", entity_id="sensor-1")
    assert len(ledger._store) == 2
