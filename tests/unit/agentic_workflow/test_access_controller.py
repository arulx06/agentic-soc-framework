from __future__ import annotations

import pytest

from agentic_workflow.access_controller import AccessController
from agentic_workflow.action_policy import POLICY_CONFIG
from agentic_workflow.contracts import ActionType, ControllerMode
from agentic_workflow.risk_analyst import RiskAnalyst
from simulation.abm import DeviceState


def make_risk_recommendation(systemic=0.2, evidence_complete=True, behavior_supported=True, network_risk=0.2, behavior_risk=0.2):
    state = DeviceState(
        node_id="sensor-1",
        role="sensor",
        device_type="sensor",
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        is_protected_asset=True,
        is_attacker=False,
        behavior_supported=behavior_supported,
        behavior_profile_type="continuous" if behavior_supported else None,
        network_risk=network_risk,
        behavior_risk=behavior_risk if behavior_supported else None,
        network_observed=True,
        behavior_observed=evidence_complete if behavior_supported else False,
        propagated_risk=0.05,
        systemic_risk=systemic,
    )
    analyst = RiskAnalyst()
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    # Override evidence_complete if needed (analyst computes it)
    if rec.evidence_complete != evidence_complete:
        rec = rec.model_copy(update={"evidence_complete": evidence_complete})
    return rec


def test_clear_low_risk_complete_evidence_allow():
    rec = make_risk_recommendation(systemic=0.1, evidence_complete=True)
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.action == ActionType.ALLOW
    assert access.policy_id == POLICY_CONFIG.policy_id
    assert access.controller_mode == ControllerMode.PRE_LZTAF_DEVICE_EVIDENCE


def test_intermediate_escalated_monitor():
    rec = make_risk_recommendation(systemic=0.5)
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.action == ActionType.MONITOR


def test_high_risk_block():
    rec = make_risk_recommendation(systemic=0.8)
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.action == ActionType.BLOCK


def test_exact_monitor_threshold_boundary():
    rec = make_risk_recommendation(systemic=POLICY_CONFIG.monitor_threshold)
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.action == ActionType.MONITOR


def test_exact_block_threshold_boundary():
    rec = make_risk_recommendation(systemic=POLICY_CONFIG.block_threshold)
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.action == ActionType.BLOCK


def test_behavior_supported_false_not_automatic_allow():
    rec = make_risk_recommendation(systemic=0.1, evidence_complete=False, behavior_supported=False)
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.action == ActionType.MONITOR
    assert access.behavior_supported is False
    assert rec.behavior_risk is None


def test_missing_evidence_conservative_but_strong_evidence_may_block():
    # Incomplete evidence normally MONITOR
    rec_low = make_risk_recommendation(systemic=0.3, evidence_complete=False)
    assert AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec_low).action == ActionType.MONITOR
    # Strong evidence independently triggers BLOCK even if incomplete
    rec_high = make_risk_recommendation(systemic=0.9, evidence_complete=False)
    assert AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec_high).action == ActionType.BLOCK


def test_trust_vector_false():
    rec = make_risk_recommendation()
    access = AccessController().decide(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", risk_recommendation=rec)
    assert access.trust_vector_supported is False
    assert access.credential_controls_supported is False
    assert access.agent_trust_supported is False


def test_thresholds_centralized_documented():
    from agentic_workflow import action_policy
    src = open(action_policy.__file__).read()
    assert "SIMULATION" in src or "ENGINEERING" in src
    assert "monitor_threshold" in src
    assert "block_threshold" in src


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("workflow_id", "other-workflow", "workflow_id mismatch"),
        ("entity_id", "other-entity", "entity_id mismatch"),
        ("window_id", 8, "window_id mismatch"),
        (
            "logical_timestamp",
            "2026-01-01T00:00:01Z",
            "logical_timestamp mismatch",
        ),
    ),
)
def test_risk_recommendation_binding_mismatch_rejected(field, value, message):
    recommendation = make_risk_recommendation().model_copy(update={field: value})
    with pytest.raises(ValueError, match=message):
        AccessController().decide(
            workflow_id="w1",
            entity_id="sensor-1",
            window_id=7,
            logical_timestamp="2026-01-01T00:00:00Z",
            risk_recommendation=recommendation,
        )
