"""Fixed typed route registry for Stage-8A.

Maps opaque route IDs to exactly five specialist identities.
No dynamic imports, eval, or arbitrary callable registration.
"""

from __future__ import annotations

from agentic_workflow.contracts import AGENT_IDS, AgentId

# Fixed deterministic capability registry
ROUTE_TO_AGENT: dict[str, AgentId] = {
    "agent.network_anomaly_detector": AgentId.network_anomaly_detector,
    "agent.iot_behavioral_profiler": AgentId.iot_behavioral_profiler,
    "agent.threat_intelligence_correlator": AgentId.threat_intelligence_correlator,
    "agent.risk_propagation_analyst": AgentId.risk_propagation_analyst,
    "agent.trust_access_controller": AgentId.trust_access_controller,
}

AGENT_TO_ROUTE: dict[AgentId, str] = {v: k for k, v in ROUTE_TO_AGENT.items()}

# Expose ordered tuple for tests/determinism
REGISTERED_ROUTES: tuple[str, ...] = tuple(sorted(ROUTE_TO_AGENT.keys()))


def resolve_route(route_id: str) -> AgentId:
    """Return specialist for route or raise ValueError for unknown."""
    try:
        return ROUTE_TO_AGENT[route_id]
    except KeyError:
        raise ValueError(f"unknown route {route_id!r}")


def is_registered_route(route_id: str) -> bool:
    return route_id in ROUTE_TO_AGENT
