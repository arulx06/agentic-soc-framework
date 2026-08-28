from __future__ import annotations

from agentic_workflow.contracts import AgentId
from agentic_workflow.readiness import DEPENDENCIES, is_ready, ready_agents


def test_network_and_behavior_independently_ready_at_start():
    assert is_ready(AgentId.network_anomaly_detector, set())
    assert is_ready(AgentId.iot_behavioral_profiler, set())
    ready = ready_agents(set())
    assert AgentId.network_anomaly_detector in ready
    assert AgentId.iot_behavioral_profiler in ready


def test_threat_not_ready_until_detectors_terminal():
    assert not is_ready(AgentId.threat_intelligence_correlator, set())
    assert not is_ready(AgentId.threat_intelligence_correlator, {AgentId.network_anomaly_detector})
    assert not is_ready(
        AgentId.threat_intelligence_correlator, {AgentId.iot_behavioral_profiler}
    )
    assert is_ready(
        AgentId.threat_intelligence_correlator,
        {AgentId.network_anomaly_detector, AgentId.iot_behavioral_profiler},
    )


def test_risk_not_ready_before_device_risk_available():
    completed = {AgentId.network_anomaly_detector, AgentId.iot_behavioral_profiler, AgentId.threat_intelligence_correlator}
    assert not is_ready(AgentId.risk_propagation_analyst, completed, device_risk_available=False)
    assert is_ready(AgentId.risk_propagation_analyst, completed, device_risk_available=True)
    # also not ready if threat missing
    assert not is_ready(
        AgentId.risk_propagation_analyst,
        {AgentId.network_anomaly_detector},
        device_risk_available=True,
    )


def test_trust_not_ready_before_risk_recommendation():
    completed = {
        AgentId.network_anomaly_detector,
        AgentId.iot_behavioral_profiler,
        AgentId.threat_intelligence_correlator,
        AgentId.risk_propagation_analyst,
    }
    assert not is_ready(
        AgentId.trust_access_controller, completed, risk_recommendation_available=False
    )
    assert is_ready(
        AgentId.trust_access_controller, completed, risk_recommendation_available=True
    )


def test_dependency_dag_exhaustive():
    # Every agent listed has entry
    assert set(DEPENDENCIES.keys()) == set(AgentId)
    # No cycles: trust depends on risk which depends on threat etc; check ordering via incremental ready
    completed = set()
    order = []
    while len(completed) < 5:
        ready = ready_agents(
            completed, device_risk_available=True, risk_recommendation_available=True
        )
        assert ready, "dag is stuck"
        nxt = sorted(ready, key=lambda x: x.value)[0]
        order.append(nxt)
        completed.add(nxt)
    assert order[0] in (AgentId.network_anomaly_detector, AgentId.iot_behavioral_profiler)
    assert order.index(AgentId.threat_intelligence_correlator) > max(
        order.index(AgentId.network_anomaly_detector),
        order.index(AgentId.iot_behavioral_profiler),
    )
    assert order.index(AgentId.risk_propagation_analyst) > order.index(
        AgentId.threat_intelligence_correlator
    )
    assert order.index(AgentId.trust_access_controller) > order.index(
        AgentId.risk_propagation_analyst
    )
