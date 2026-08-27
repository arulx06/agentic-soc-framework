from __future__ import annotations

from backend.app.services.orchestration_service import OrchestrationService
from orchestration.contracts import OrchestrationOutcome

from .conftest import DelayHooks, FixedPolicy, OmitHooks, TEST_KEYS, VoteDelayHooks


def service_for(routes=("route_alpha", "route_alpha", "route_alpha"), hooks=None, timeout=0.2):
    ids = ("orchestrator_a", "orchestrator_b", "orchestrator_c")
    return OrchestrationService(
        keys=TEST_KEYS,
        policies={key: FixedPolicy(route) for key, route in zip(ids, routes)},
        hooks=hooks,
        timeout_seconds=timeout,
    )


def test_healthy_three_zero_agreement_decides(request_factory):
    decision = service_for().adjudicate(request_factory(), principal="test-principal")
    assert decision.outcome is OrchestrationOutcome.DECIDED
    assert decision.selected_route_id == "route_alpha"
    assert set(decision.supporting_orchestrators) == {"orchestrator_a", "orchestrator_b", "orchestrator_c"}


def test_two_vs_one_decides_and_exposes_disagreement(request_factory):
    decision = service_for(("route_alpha", "route_alpha", "route_beta")).adjudicate(
        request_factory(), principal="test-principal"
    )
    assert decision.outcome is OrchestrationOutcome.DECIDED
    assert decision.selected_route_id == "route_alpha"
    assert decision.disagreeing_orchestrators == ("orchestrator_c",)


def test_one_unavailable_still_allows_two_of_three(request_factory):
    service = service_for()
    service.replicas[2].set_available(False)
    decision = service.adjudicate(request_factory(), principal="test-principal")
    assert decision.outcome is OrchestrationOutcome.DECIDED
    assert decision.unavailable_orchestrators == ("orchestrator_c",)
    assert decision.selected_route_id == "route_alpha"


def test_three_way_split_has_no_fallback_route(request_factory):
    decision = service_for(("route_alpha", "route_beta", "route_gamma")).adjudicate(
        request_factory(), principal="test-principal"
    )
    assert decision.outcome is OrchestrationOutcome.NO_QUORUM
    assert decision.selected_route_id is None
    assert decision.selected_proposal_digest is None


def test_one_response_and_two_timeouts_has_no_decision(request_factory):
    service = service_for(
        hooks={"orchestrator_b": DelayHooks(0.08), "orchestrator_c": DelayHooks(0.08)},
        timeout=0.015,
    )
    decision = service.adjudicate(request_factory(), principal="test-principal")
    assert decision.outcome is OrchestrationOutcome.TIMED_OUT
    assert decision.selected_route_id is None
    assert set(decision.timed_out_orchestrators) == {"orchestrator_b", "orchestrator_c"}


def test_two_fast_replicas_form_quorum_without_waiting_for_slow_third(request_factory):
    service = service_for(hooks={"orchestrator_c": DelayHooks(0.15)}, timeout=0.5)
    decision = service.adjudicate(request_factory(), principal="test-principal")
    assert decision.outcome is OrchestrationOutcome.DECIDED
    assert decision.decision_latency_ms < 140
    assert decision.timed_out_orchestrators == ()
    assert decision.delayed_orchestrators == ("orchestrator_c",)


def test_omission_is_distinct_from_timeout_and_unavailable(request_factory):
    service = service_for(hooks={"orchestrator_c": OmitHooks()})
    decision = service.adjudicate(request_factory(), principal="test-principal")
    assert decision.outcome is OrchestrationOutcome.DECIDED
    assert decision.omitted_orchestrators == ("orchestrator_c",)
    assert decision.timed_out_orchestrators == ()
    assert decision.unavailable_orchestrators == ()


def test_vote_phase_timeout_preserves_valid_proposal_evidence(request_factory):
    service = service_for(
        hooks={
            "orchestrator_b": VoteDelayHooks(0.08),
            "orchestrator_c": VoteDelayHooks(0.08),
        },
        timeout=0.015,
    )
    decision = service.adjudicate(request_factory(), principal="test-principal")
    assert decision.outcome is OrchestrationOutcome.TIMED_OUT
    assert len(decision.proposal_summaries) == 3
    assert len(decision.vote_summaries) == 1
    assert set(decision.timed_out_orchestrators) == {"orchestrator_b", "orchestrator_c"}


def test_replica_lane_delayed_from_prior_round_is_retried_before_new_deadline(request_factory):
    class RequestPolicy:
        policy_id = "request_test_policy"
        policy_version = "1"

        def __init__(self, first_route, second_route):
            self.first_route = first_route
            self.second_route = second_route

        def propose(self, request):
            route = self.first_route if request.request_id == "first" else self.second_route
            return route, "TEST_REQUEST_ROUTE"

    service = OrchestrationService(
        keys=TEST_KEYS,
        policies={
            "orchestrator_a": RequestPolicy("route_alpha", "route_alpha"),
            "orchestrator_b": RequestPolicy("route_alpha", "route_beta"),
            "orchestrator_c": RequestPolicy("route_alpha", "route_beta"),
        },
        hooks={"orchestrator_c": DelayHooks(0.04)},
        timeout_seconds=0.3,
    )
    first = service.adjudicate(
        request_factory(request_id="first", round_id="round-first"),
        principal="test-principal",
    )
    assert first.delayed_orchestrators == ("orchestrator_c",)
    second = service.adjudicate(
        request_factory(request_id="second", round_id="round-second"),
        principal="test-principal",
    )
    assert second.outcome is OrchestrationOutcome.DECIDED
    assert second.selected_route_id == "route_beta"
    assert set(second.supporting_orchestrators) == {"orchestrator_b", "orchestrator_c"}
