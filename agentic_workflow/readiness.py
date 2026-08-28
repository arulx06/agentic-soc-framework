"""Workflow dependency / readiness model.

DAG:
  network_anomaly_detector \
                              -> threat_intelligence_correlator -> risk_propagation_analyst -> trust_access_controller
  iot_behavioral_profiler  /
But network and behavior are independently ready at start; threat needs
either/completed evidence stage terminal; risk needs authoritative device-risk
state; trust needs RiskRecommendation.

Pure readiness logic: no orchestrator calls.
"""

from __future__ import annotations

from agentic_workflow.contracts import AgentId

# Define dependencies
DEPENDENCIES: dict[AgentId, set[AgentId]] = {
    AgentId.network_anomaly_detector: set(),
    AgentId.iot_behavioral_profiler: set(),
    AgentId.threat_intelligence_correlator: {
        AgentId.network_anomaly_detector,
        AgentId.iot_behavioral_profiler,
    },
    AgentId.risk_propagation_analyst: {
        AgentId.threat_intelligence_correlator,
    },
    AgentId.trust_access_controller: {
        AgentId.risk_propagation_analyst,
    },
}

# For more granular: evidence stage terminal vs device-risk available flags
# We expose a readiness function that takes completed agents and additional
# flags for the later dependencies that require external state.


def is_ready(
    agent_id: AgentId,
    completed: set[AgentId],
    *,
    device_risk_available: bool = False,
    risk_recommendation_available: bool = False,
) -> bool:
    """Return True if agent's dependencies are satisfied."""
    # Base DAG check
    deps = DEPENDENCIES.get(agent_id, set())
    # For threat correlator we allow either network or behavior completed?
    # Spec says: validated finding evidence complete -> threat. So we require
    # at least one of the two detectors completed? But simplest: require both
    # dispatched? To keep exhaustive tests simple we treat as either is okay
    # BUT original spec says Network and Behaviour roles may be independently
    # ready at start, Threat Intelligence must not be ready until detector evidence
    # stage is terminal. That suggests threat needs BOTH? Actually spec shows:
    # network + behavior -> validated finding evidence complete -> threat
    # So we interpret as: threat requires that evidence stage is terminal, which
    # in our pure model means both detectors completed OR at least evidence stage
    # marked complete. For now we require that at least one of network/behavior
    # is completed AND the "evidence terminal" flag is passed via completed set
    # containing both? Let's implement: threat is ready when both detectors are
    # in completed set.
    # However to allow testing "one detector only" we keep strict both-required
    # and tests will reflect that.
    if agent_id == AgentId.risk_propagation_analyst:
        # Needs threat completed AND device_risk_available
        if AgentId.threat_intelligence_correlator not in completed:
            return False
        return bool(device_risk_available)
    if agent_id == AgentId.trust_access_controller:
        if AgentId.risk_propagation_analyst not in completed:
            return False
        return bool(risk_recommendation_available)
    # For other agents, check normal deps
    return deps.issubset(completed)


def ready_agents(
    completed: set[AgentId],
    *,
    device_risk_available: bool = False,
    risk_recommendation_available: bool = False,
) -> set[AgentId]:
    """Return set of agents ready to run next."""
    ready = set()
    for aid in AgentId:
        if aid in completed:
            continue
        if is_ready(
            aid,
            completed,
            device_risk_available=device_risk_available,
            risk_recommendation_available=risk_recommendation_available,
        ):
            ready.add(aid)
    return ready
