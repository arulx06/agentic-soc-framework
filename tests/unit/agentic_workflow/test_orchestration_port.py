from __future__ import annotations

from dataclasses import dataclass

from agentic_workflow.contracts import AgentId
from agentic_workflow.orchestration_port import should_execute


@dataclass
class FakeDecision:
    outcome: str
    selected_route_id: str | None


def test_decided_valid_registered_route_executes_one_specialist():
    d = FakeDecision(outcome="DECIDED", selected_route_id="agent.network_anomaly_detector")
    assert should_execute(d) == AgentId.network_anomaly_detector
    assert should_execute(FakeDecision(outcome="DECIDED", selected_route_id="agent.trust_access_controller")) == AgentId.trust_access_controller


def test_no_quorum_no_execution():
    assert should_execute(FakeDecision(outcome="NO_QUORUM", selected_route_id="agent.network_anomaly_detector")) is None


def test_timed_out_no_execution():
    assert should_execute(FakeDecision(outcome="TIMED_OUT", selected_route_id="agent.network_anomaly_detector")) is None


def test_insufficient_responses_no_execution():
    assert should_execute(FakeDecision(outcome="INSUFFICIENT_RESPONSES", selected_route_id="agent.network_anomaly_detector")) is None


def test_rejected_request_no_execution():
    assert should_execute(FakeDecision(outcome="REJECTED_REQUEST", selected_route_id="agent.network_anomaly_detector")) is None


def test_unknown_route_no_execution():
    assert should_execute(FakeDecision(outcome="DECIDED", selected_route_id="agent.unknown_agent")) is None
    assert should_execute(FakeDecision(outcome="DECIDED", selected_route_id="")) is None
    assert should_execute(FakeDecision(outcome="DECIDED", selected_route_id=None)) is None


def test_no_scheduler_fallback():
    # Ensure that non-DECIDED does not fallback to any agent
    for outcome in ["NO_QUORUM", "TIMED_OUT", "INSUFFICIENT_RESPONSES", "REJECTED_REQUEST"]:
        assert should_execute(FakeDecision(outcome=outcome, selected_route_id="agent.network_anomaly_detector")) is None
