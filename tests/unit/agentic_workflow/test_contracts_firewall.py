from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_workflow.contracts import (
    AccessRecommendationV1,
    AgentDispatchV1,
    AgentId,
    ControllerMode,
    EnforcementDecisionV1,
    RiskRecommendationV1,
    ThreatCorrelationV1,
    MappingStatus,
    ActionType,
)
from agentic_workflow.firewall import AGENTIC_EXTRA_FORBIDDEN_KEYS


def test_agent_dispatch_requires_exact_schema_version():
    with pytest.raises(ValidationError):
        AgentDispatchV1.model_validate(
            {
                "schema_version": "agent_dispatch_v2",
                "dispatch_id": "d1",
                "workflow_id": "w1",
                "agent_id": "network_anomaly_detector",
                "window_id": 0,
                "logical_timestamp": "2026-01-01T00:00:00Z",
                "source_component": "test",
            }
        )


def test_nested_ground_truth_rejected():
    # nested dict with forbidden key must raise
    with pytest.raises((ValidationError, ValueError)):
        AgentDispatchV1(
            dispatch_id="d1",
            workflow_id="w1",
            agent_id=AgentId.network_anomaly_detector,
            window_id=0,
            logical_timestamp="2026-01-01T00:00:00Z",
            source_component="test",
            provenance={"nested": {"label": "attack"}},
        )


def test_extra_forbidden_scenario_id_rejected():
    with pytest.raises((ValidationError, ValueError)):
        AgentDispatchV1(
            dispatch_id="d1",
            workflow_id="w1",
            agent_id=AgentId.network_anomaly_detector,
            window_id=0,
            logical_timestamp="2026-01-01T00:00:00Z",
            source_component="test",
            provenance={"scenario_id": "hidden"},
        )


@pytest.mark.parametrize("key", sorted(AGENTIC_EXTRA_FORBIDDEN_KEYS))
def test_each_extra_forbidden_key_rejected(key):
    with pytest.raises((ValidationError, ValueError)):
        ThreatCorrelationV1(
            correlation_id="c1",
            workflow_id="w1",
            entity_id="e1",
            window_id=0,
            logical_timestamp="2026-01-01T00:00:00Z",
            mapping_status=MappingStatus.UNMAPPED,
            mapping_catalog_version="threat_catalog_v1",
            provenance={key: "secret"},
        )


def test_session_trace_allowed_not_decoded():
    # session_trace is allowed opaque key
    d = AgentDispatchV1(
        dispatch_id="d1",
        workflow_id="w1",
        agent_id=AgentId.network_anomaly_detector,
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        source_component="test",
        provenance={"session_trace": "abc123opaque"},
    )
    assert d.provenance["session_trace"] == "abc123opaque"


def test_attack_probability_allowed_as_output():
    # legitimate model output field allowed inside provenance? But our firewall checks keys not values
    # attack_probability key is not forbidden (forbidden is bare 'attack' etc but we allow compound)
    # Ensure that output_summary with attack_probability not rejected (tested via ThreatCorrelation allowed provenance)
    corr = ThreatCorrelationV1(
        correlation_id="c1",
        workflow_id="w1",
        entity_id="e1",
        window_id=0,
        logical_timestamp="2026-01-01T00:00:00Z",
        mapping_status=MappingStatus.UNMAPPED,
        mapping_catalog_version="threat_catalog_v1",
        provenance={"attack_probability": 0.9},
    )
    assert corr.provenance["attack_probability"] == 0.9


def test_enforcement_decision_requires_false_physical_claims():
    with pytest.raises(ValidationError):
        EnforcementDecisionV1.model_validate(
            {
                "schema_version": "enforcement_decision_v1",
                "decision_id": "d1",
                "workflow_id": "w1",
                "replay_id": "r1",
                "window_id": 0,
                "logical_timestamp": "2026-01-01T00:00:00Z",
                "entity_id": "e1",
                "action": "BLOCK",
                "controller_recommendation_id": "cr1",
                "policy_id": "stage8_access_policy_v1",
                "policy_version": "1",
                "evidence_complete": True,
                "behavior_supported": True,
                "source_component": "test",
                "physical_enforcement_claimed": True,  # must be False
                "counterfactual_effect_applied": False,
            }
        )
