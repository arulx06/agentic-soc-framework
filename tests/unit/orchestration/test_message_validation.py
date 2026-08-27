from __future__ import annotations

from orchestration.authentication import MessageVerifier
from orchestration.coordinator import BoundedReplayCache, DecisionRound
from orchestration.instrumentation import OrchestrationInstrumentation
from orchestration.replica import OrchestratorReplica

from .conftest import FixedPolicy, TEST_KEYS


def make_round(request):
    return DecisionRound(
        request,
        MessageVerifier(TEST_KEYS),
        BoundedReplayCache(20),
        OrchestrationInstrumentation(),
    )


def test_duplicate_sender_vote_counts_once(request_factory):
    request = request_factory()
    state = make_round(request)
    a = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"])
    proposal = a.propose(request)
    vote = a.vote(request, proposal)
    assert state.accept_proposal(proposal) == "ACCEPTED"
    assert state.accept_vote(vote) == "ACCEPTED"
    assert state.accept_vote(vote) == "DUPLICATE"
    assert len(state.votes) == 1
    assert state.quorum_digest is None


def test_conflicting_double_vote_is_detected_and_not_counted(request_factory):
    request = request_factory()
    state = make_round(request)
    a = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"], policy=FixedPolicy("route_alpha"))
    b = OrchestratorReplica("orchestrator_b", TEST_KEYS["orchestrator_b"], policy=FixedPolicy("route_beta"))
    proposal_a = a.propose(request)
    proposal_b = b.propose(request)
    state.accept_proposal(proposal_a)
    state.accept_proposal(proposal_b)
    assert state.accept_vote(a.vote(request, proposal_a)) == "ACCEPTED"
    assert state.accept_vote(a.vote(request, proposal_b)) == "CONFLICTING_VOTE"
    assert len(state.votes) == 1
    assert any(item.reason_code == "CONFLICTING_VOTE" for item in state.rejections)


def test_forged_authentication_does_not_count(request_factory):
    request = request_factory()
    state = make_round(request)
    proposal = OrchestratorReplica("orchestrator_a", b"z" * 32).propose(request)
    assert state.accept_proposal(proposal) == "AUTHENTICATION_FAILED"
    assert state.proposals == {}


def test_forged_vote_authentication_does_not_count(request_factory):
    request = request_factory()
    state = make_round(request)
    honest = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"])
    proposal = honest.propose(request)
    assert state.accept_proposal(proposal) == "ACCEPTED"
    forged_vote = OrchestratorReplica("orchestrator_a", b"z" * 32).vote(request, proposal)
    assert state.accept_vote(forged_vote) == "AUTHENTICATION_FAILED"
    assert state.votes == {}


def test_valid_signed_wrong_round_message_does_not_count(request_factory):
    state = make_round(request_factory())
    wrong_request = request_factory(round_id="round-other")
    proposal = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"]).propose(wrong_request)
    assert state.accept_proposal(proposal) == "WRONG_ROUND"
    assert state.proposals == {}


def test_unknown_route_proposal_is_rejected(request_factory):
    request = request_factory()
    state = make_round(request)
    proposal = OrchestratorReplica(
        "orchestrator_a", TEST_KEYS["orchestrator_a"], policy=FixedPolicy("route_outside_set")
    ).propose(request)
    assert state.accept_proposal(proposal) == "UNKNOWN_ROUTE"
    assert state.proposals == {}


def test_late_message_cannot_modify_terminal_round(request_factory):
    request = request_factory()
    state = make_round(request)
    proposal = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"]).propose(request)
    state.close()
    assert state.accept_proposal(proposal) == "LATE_MESSAGE"
    assert state.proposals == {}
