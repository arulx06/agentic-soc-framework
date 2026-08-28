from __future__ import annotations

import pytest

from agentic_workflow.contracts import MappingStatus, ThreatCorrelationV1
from agentic_workflow.risk_analyst import RiskAnalyst
from simulation.abm import DeviceState


def make_state(**overrides):
    base = dict(
        node_id="sensor-1",
        role="sensor",
        device_type="sensor",
        ip="192.168.1.10",
        mac="aa:bb:cc:dd:ee:ff",
        is_protected_asset=True,
        is_attacker=False,
        behavior_supported=True,
        behavior_profile_type="continuous",
        network_risk=0.6,
        behavior_risk=0.2,
        network_observed=True,
        behavior_observed=True,
        propagated_risk=0.1,
        systemic_risk=0.6,
    )
    base.update(overrides)
    return DeviceState(**{k: v for k, v in base.items() if k in DeviceState.__dataclass_fields__})


def test_uses_supplied_authoritative_state():
    analyst = RiskAnalyst()
    state = make_state(network_risk=0.8, behavior_risk=0.4, propagated_risk=0.2, systemic_risk=0.8)
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    assert rec.network_risk == 0.8
    assert rec.behavior_risk == 0.4
    assert rec.propagated_risk == 0.2
    assert rec.systemic_risk == 0.8
    assert rec.device_risk_supported is True


def test_does_not_recompute_competing_graph():
    # Ensure no new graph algorithm invoked: we check that systemic is passed through not recalculated via different formula
    # Use a state where systemic is not max(direct, propagated) to see if analyst preserves
    analyst = RiskAnalyst()
    state = make_state(systemic_risk=0.99, propagated_risk=0.01, network_risk=0.2, behavior_risk=0.2)
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    assert rec.systemic_risk == 0.99


def test_preserves_network_behavior_propagated_systemic_distinctions():
    analyst = RiskAnalyst()
    state = make_state(network_risk=0.3, behavior_risk=0.9, propagated_risk=0.05, systemic_risk=0.9)
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    assert rec.network_risk == 0.3
    assert rec.behavior_risk == 0.9
    assert rec.direct_risk == max(0.3, 0.9)
    assert rec.propagated_risk == 0.05


def test_behavior_risk_none_stays_none():
    analyst = RiskAnalyst()
    state = make_state(behavior_supported=False, behavior_risk=None, behavior_observed=False, network_risk=0.5, systemic_risk=0.5)
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    assert rec.behavior_risk is None
    assert rec.behavior_supported is False


def test_behavior_supported_false_with_risk_raises():
    analyst = RiskAnalyst()
    state = make_state(behavior_supported=False, behavior_risk=0.2)
    with pytest.raises(ValueError):
        analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)


def test_agent_trust_supported_false():
    analyst = RiskAnalyst()
    state = make_state()
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    assert rec.agent_trust_graph_supported is False
    assert rec.agent_workflow_risk_supported is False
    assert "agent_trust_graph_supported" in rec.model_dump()


def test_no_invented_trust_score():
    analyst = RiskAnalyst()
    state = make_state()
    rec = analyst.analyze(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", device_state=state)
    dump = rec.model_dump()
    assert "trust_score" not in dump
    assert "trust_vector" not in dump


def test_cross_entity_threat_correlation_rejected():
    correlation = ThreatCorrelationV1(
        correlation_id="correlation-1",
        workflow_id="w1",
        entity_id="other-entity",
        window_id=7,
        logical_timestamp="2026-01-01T00:00:00Z",
        mapping_status=MappingStatus.UNMAPPED,
        mapping_catalog_version="threat_catalog_v1",
    )
    with pytest.raises(ValueError, match="entity_id mismatch"):
        RiskAnalyst().analyze(
            workflow_id="w1",
            entity_id="sensor-1",
            window_id=7,
            logical_timestamp="2026-01-01T00:00:00Z",
            device_state=make_state(),
            threat_correlations=(correlation,),
        )
    with pytest.raises(ValueError, match="device_state entity_id mismatch"):
        RiskAnalyst().analyze(
            workflow_id="w1",
            entity_id="sensor-1",
            window_id=7,
            logical_timestamp="2026-01-01T00:00:00Z",
            device_state=make_state(node_id="other-entity"),
        )
