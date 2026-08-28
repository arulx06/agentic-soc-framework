from __future__ import annotations

import pytest

from pipeline.findings import BehaviorFinding, NetworkFinding
from agentic_workflow.contracts import MappingStatus
from agentic_workflow.threat_correlator import ThreatCorrelator, CATALOG_VERSION


def make_network_finding(attack_prob=0.9, pred="attack", conf=0.9):
    return NetworkFinding(
        entity_id="sensor-1",
        window_id=7,
        timestamp_utc="2026-01-01T00:00:00Z",
        attack_probability=attack_prob,
        predicted_class=pred,
        confidence=conf,
        source_model="network_detector_v1@test",
        provenance={"source_mode": "feature_store"},
    )


def make_behavior_finding(deviation=0.9):
    return BehaviorFinding(
        entity_id="sensor-1",
        window_id=7,
        timestamp_utc="2026-01-01T00:00:00Z",
        deviation_score=deviation,
        profile_type="continuous",
        confidence=0.8,
        explanation="cadence deviation",
        source_model="behavior_profiler_v1@test",
        provenance={"source_mode": "feature_store"},
    )


def test_matched_valid_safe_runtime_rule():
    corr = ThreatCorrelator().correlate(
        workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
        findings=[make_network_finding()],
    )
    assert corr.mapping_status == MappingStatus.MATCHED
    assert corr.threat_behavior_id is not None
    assert corr.mapping_catalog_version == CATALOG_VERSION
    assert corr.mapping_rule_id is not None


def test_unmapped_when_insufficient_for_family():
    # predicted attack but low confidence -> UNMAPPED, not fabricated
    corr = ThreatCorrelator().correlate(
        workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
        findings=[make_network_finding(conf=0.5)],
    )
    assert corr.mapping_status == MappingStatus.UNMAPPED
    assert corr.threat_behavior_id is None
    # Also benign finding -> UNMAPPED
    corr2 = ThreatCorrelator().correlate(
        workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
        findings=[make_network_finding(pred="benign", attack_prob=0.1, conf=0.9)],
    )
    assert corr2.mapping_status == MappingStatus.UNMAPPED


def test_unsupported_modality():
    class FakeFinding:
        finding_type = "UNKNOWN_TYPE"
        entity_id = "sensor-1"
        window_id = 7

    corr = ThreatCorrelator().correlate(
        workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
        findings=[FakeFinding()],
    )
    assert corr.mapping_status == MappingStatus.UNSUPPORTED


def test_nested_ground_truth_rejected():
    # Try to pass a finding with tainted provenance? But Finding itself would have rejected at construction.
    # Instead test that correlator rejects tainted provenance dict
    with pytest.raises((ValueError, pytest.fail.Exception)):
        ThreatCorrelator().correlate(
            workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
            findings=[make_network_finding()],
            provenance={"attack_category": "secret"},
        )


def test_scenario_name_filename_target_rejected():
    for bad in [{"scenario_name": "secret"}, {"filename": "secret.pcap"}, {"targets": ["sensor"]}]:
        with pytest.raises((ValueError, Exception)):
            ThreatCorrelator().correlate(
                workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
                findings=[make_network_finding()],
                provenance=bad,
            )


def test_session_trace_never_decoded():
    # Provide session_trace opaque; correlator should not decode it and still work
    finding = make_network_finding()
    # Ensure finding provenance has session_trace and correlation still deterministic
    corr1 = ThreatCorrelator().correlate(
        workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
        findings=[finding],
        provenance={"session_trace": "abc123opaque"},
    )
    corr2 = ThreatCorrelator().correlate(
        workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z",
        findings=[finding],
        provenance={"session_trace": "differentOpaqueButSameFinding"},
    )
    # Deterministic mapping for same finding should be same status regardless of session_trace value?
    # Our correlator doesn't decode session_trace; both should be MATCHED (since finding same)
    assert corr1.mapping_status == corr2.mapping_status == MappingStatus.MATCHED


def test_same_finding_deterministic():
    f = make_behavior_finding(deviation=0.95)
    c1 = ThreatCorrelator().correlate(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", findings=[f])
    c2 = ThreatCorrelator().correlate(workflow_id="w1", entity_id="sensor-1", window_id=7, logical_timestamp="2026-01-01T00:00:00Z", findings=[f])
    assert c1.mapping_status == c2.mapping_status
    assert c1.threat_behavior_id == c2.threat_behavior_id
    assert c1.mapping_rule_id == c2.mapping_rule_id


def test_cross_entity_or_window_finding_rejected():
    correlator = ThreatCorrelator()
    with pytest.raises(ValueError, match="entity_id mismatch"):
        correlator.correlate(
            workflow_id="w1",
            entity_id="other-entity",
            window_id=7,
            logical_timestamp="2026-01-01T00:00:00Z",
            findings=[make_network_finding()],
        )
    with pytest.raises(ValueError, match="window_id mismatch"):
        correlator.correlate(
            workflow_id="w1",
            entity_id="sensor-1",
            window_id=8,
            logical_timestamp="2026-01-01T00:00:00Z",
            findings=[make_network_finding()],
        )
