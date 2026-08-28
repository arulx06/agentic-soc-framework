from __future__ import annotations

import pytest

from agentic_workflow.contracts import AGENT_IDS, AgentId
from agentic_workflow.registry import ROUTE_TO_AGENT, resolve_route, is_registered_route


def test_exact_five_specialist_identities():
    assert len(AGENT_IDS) == 5
    assert set(AGENT_IDS) == {
        "network_anomaly_detector",
        "iot_behavioral_profiler",
        "threat_intelligence_correlator",
        "risk_propagation_analyst",
        "trust_access_controller",
    }


def test_identities_distinct_from_orchestrators_and_replicas():
    orchestrators = {"orchestrator_a", "orchestrator_b", "orchestrator_c"}
    replicas = {"replica_a", "replica_b", "replica_c"}
    assert set(AGENT_IDS).isdisjoint(orchestrators)
    assert set(AGENT_IDS).isdisjoint(replicas)


def test_registry_has_exactly_five_routes():
    assert len(ROUTE_TO_AGENT) == 5
    assert set(ROUTE_TO_AGENT.values()) == set(AgentId)
    for route, agent in ROUTE_TO_AGENT.items():
        assert route.startswith("agent.")


def test_unknown_route_rejected():
    with pytest.raises(ValueError, match="unknown route"):
        resolve_route("agent.unknown_agent")
    with pytest.raises(ValueError, match="unknown route"):
        resolve_route("eval('malicious')")
    with pytest.raises(ValueError, match="unknown route"):
        resolve_route("")


def test_no_dynamic_import_eval():
    # Ensure registry does not use eval/dynamic import from arbitrary strings
    import agentic_workflow.registry as reg

    src = open(reg.__file__).read()
    assert "eval(" not in src
    assert "__import__" not in src
    assert "importlib" not in src


def test_is_registered_route():
    assert is_registered_route("agent.network_anomaly_detector")
    assert not is_registered_route("agent.fake")
