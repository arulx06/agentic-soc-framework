from __future__ import annotations

from pipeline.findings import NetworkFinding, BehaviorFinding
from agentic_workflow.contracts import AgentDispatchV1, AgentId
from agentic_workflow.network_agent import NetworkAgent
from agentic_workflow.behavior_agent import BehaviorAgent


class SpyDetector:
    def __init__(self):
        self.calls = 0
        self.last_record = None

    def finding_from_record(self, record, *, source_mode="feature_store", session_trace=None, artifact_path=""):
        self.calls += 1
        self.last_record = record
        return NetworkFinding(
            entity_id=record["device_id"],
            window_id=int(record["window_id"]),
            timestamp_utc=record["window_start_utc"],
            attack_probability=0.9,
            predicted_class="attack",
            confidence=0.9,
            source_model="network_detector_v1@test",
            provenance={"source_mode": source_mode},
        )


class SpyProfiler:
    def __init__(self, finding_to_return=None):
        self.calls = 0
        self.finding_to_return = finding_to_return

    def predict_record(self, record, *, source_mode="feature_store", telemetry_context_active=False, current_window_id=None, session_trace=None):
        self.calls += 1
        if self.finding_to_return is not None:
            return self.finding_to_return
        # Return None for unsupported
        return None


def make_dispatch(agent_id: AgentId):
    return AgentDispatchV1(
        dispatch_id="d1",
        workflow_id="w1",
        agent_id=agent_id,
        window_id=7,
        logical_timestamp="2026-01-01T00:00:00Z",
        source_component="test",
        input_refs=("input:net:1",),
    )


def test_network_agent_reuses_detector_and_preserves_output():
    spy = SpyDetector()
    agent = NetworkAgent(spy)
    dispatch = make_dispatch(AgentId.network_anomaly_detector)
    record = {
        "device_id": "sensor-1",
        "window_id": 7,
        "window_start_utc": "2026-01-01T00:00:00Z",
        "network_observed": True,
        "source_mode": "feature_store",
    }
    result, finding = agent.execute(dispatch, record)
    assert spy.calls == 1
    assert finding.attack_probability == 0.9
    assert finding.predicted_class == "attack"
    assert result.agent_id == AgentId.network_anomaly_detector
    assert result.entity_id == "sensor-1"
    # second call should be second inference, not duplicate caching
    agent.execute(dispatch, record)
    assert spy.calls == 2


def test_network_agent_one_window_one_inference():
    spy = SpyDetector()
    agent = NetworkAgent(spy)
    dispatch = make_dispatch(AgentId.network_anomaly_detector)
    record = {
        "device_id": "sensor-1",
        "window_id": 7,
        "window_start_utc": "2026-01-01T00:00:00Z",
        "network_observed": True,
    }
    # Simulate old direct inference vs new wrapper: we ensure wrapper calls exactly once
    # Spy proves no double inference architecture
    agent.execute(dispatch, record)
    assert spy.calls == 1


def test_behavior_agent_preserves_missingness():
    # supported + zero deviation case, supported + nonzero, unsupported, missing
    finding_supported = BehaviorFinding(
        entity_id="sensor-1",
        window_id=7,
        timestamp_utc="2026-01-01T00:00:00Z",
        deviation_score=0.0,
        profile_type="continuous",
        confidence=0.6,
        explanation="within normal",
        source_model="behavior_profiler_v1@test",
        provenance={"source_mode": "feature_store"},
    )
    spy = SpyProfiler(finding_to_return=finding_supported)
    agent = BehaviorAgent(spy)
    dispatch = make_dispatch(AgentId.iot_behavioral_profiler)
    record = {"device_id": "sensor-1", "window_id": 7, "window_start_utc": "2026-01-01T00:00:00Z", "behavior_observed": True}
    result, finding = agent.execute(dispatch, record, telemetry_context_active=True)
    assert spy.calls == 1
    assert finding.deviation_score == 0.0
    assert result.output_refs == (f"finding:sensor-1:7",)

    # supported + nonzero deviation
    finding_nonzero = BehaviorFinding(
        entity_id="sensor-1",
        window_id=7,
        timestamp_utc="2026-01-01T00:00:00Z",
        deviation_score=0.9,
        profile_type="sparse",
        confidence=0.9,
        explanation="unexpected_burst",
        source_model="behavior_profiler_v1@test",
        provenance={"source_mode": "feature_store"},
    )
    spy2 = SpyProfiler(finding_to_return=finding_nonzero)
    agent2 = BehaviorAgent(spy2)
    result2, finding2 = agent2.execute(dispatch, record, telemetry_context_active=True)
    assert finding2.deviation_score == 0.9

    # unsupported telemetry -> None, but agent still returns execution with empty output_refs and preserves behavior_supported False
    spy_none = SpyProfiler(finding_to_return=None)
    agent3 = BehaviorAgent(spy_none)
    result3, finding3 = agent3.execute(dispatch, record, telemetry_context_active=False)
    assert finding3 is None
    assert result3.output_refs == ()
    # Missing telemetry case: profiler returns None
    assert spy_none.calls == 1


def test_behavior_missing_does_not_become_zero_risk():
    # This test ensures behavior unsupported doesn't fabricate 0 risk; the risk analyst will handle
    # Here we just check that BehaviorFinding missingness is preserved as None
    spy = SpyProfiler(finding_to_return=None)
    agent = BehaviorAgent(spy)
    dispatch = make_dispatch(AgentId.iot_behavioral_profiler)
    record = {"device_id": "unknown-sensor", "window_id": 7, "window_start_utc": "2026-01-01T00:00:00Z"}
    _, finding = agent.execute(dispatch, record, telemetry_context_active=False)
    assert finding is None


def test_no_double_inference_architecture():
    # Prove that one window -> one detector inference, one profiler inference when supported
    spy_det = SpyDetector()
    spy_prof = SpyProfiler(
        finding_to_return=BehaviorFinding(
            entity_id="sensor-1",
            window_id=7,
            timestamp_utc="2026-01-01T00:00:00Z",
            deviation_score=0.1,
            profile_type="continuous",
            confidence=0.5,
            explanation="within normal",
            source_model="behavior_profiler_v1@test",
            provenance={"source_mode": "feature_store"},
        )
    )
    net_agent = NetworkAgent(spy_det)
    beh_agent = BehaviorAgent(spy_prof)
    dispatch_net = make_dispatch(AgentId.network_anomaly_detector)
    dispatch_beh = make_dispatch(AgentId.iot_behavioral_profiler)
    record = {
        "device_id": "sensor-1",
        "window_id": 7,
        "window_start_utc": "2026-01-01T00:00:00Z",
        "network_observed": True,
        "behavior_observed": True,
    }
    net_agent.execute(dispatch_net, record)
    beh_agent.execute(dispatch_beh, record, telemetry_context_active=True)
    assert spy_det.calls == 1
    assert spy_prof.calls == 1
