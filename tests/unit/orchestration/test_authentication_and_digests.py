from __future__ import annotations

from orchestration.authentication import MessageVerifier
from orchestration.hashing import proposal_digest
from orchestration.replica import OrchestratorReplica
from orchestration.coordinator import OrchestrationCoordinator

from .conftest import FixedPolicy, TEST_KEYS


def test_same_semantic_route_has_same_digest_but_distinct_message_hash(request_factory):
    request = request_factory()
    a = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"], policy=FixedPolicy("route_alpha"))
    b = OrchestratorReplica("orchestrator_b", TEST_KEYS["orchestrator_b"], policy=FixedPolicy("route_alpha"))
    proposal_a = a.propose(request)
    proposal_b = b.propose(request)
    assert proposal_a.proposal_digest == proposal_b.proposal_digest
    assert proposal_a.message_hash != proposal_b.message_hash


def test_different_route_changes_semantic_proposal_digest(request_factory):
    request = request_factory()
    alpha = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"], policy=FixedPolicy("route_alpha")).propose(request)
    beta = OrchestratorReplica("orchestrator_b", TEST_KEYS["orchestrator_b"], policy=FixedPolicy("route_beta")).propose(request)
    assert alpha.proposal_digest != beta.proposal_digest


def test_valid_sender_and_key_authenticates(request_factory):
    message = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"]).propose(request_factory())
    assert MessageVerifier(TEST_KEYS).verify(message) == (True, "AUTHENTICATED")


def test_correct_sender_with_wrong_verification_key_is_rejected(request_factory):
    message = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"]).propose(request_factory())
    wrong = {**TEST_KEYS, "orchestrator_a": b"z" * 32}
    assert MessageVerifier(wrong).verify(message)[0] is False


def test_sender_route_digest_and_round_mutations_fail_authentication(request_factory):
    message = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"]).propose(request_factory())
    mutations = (
        {"orchestrator_id": "orchestrator_b"},
        {"proposed_route_id": "route_beta"},
        {"proposal_digest": "0" * 64},
        {"round_id": "round-other"},
    )
    verifier = MessageVerifier(TEST_KEYS)
    for mutation in mutations:
        assert verifier.verify(message.model_copy(update=mutation))[0] is False


def test_authenticator_reprs_never_expose_key_material(request_factory):
    replica = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"])
    text = repr(replica._authenticator)
    assert TEST_KEYS["orchestrator_a"].hex() not in text
    assert "aaaaaaaaaaaaaaaa" not in text


def test_replica_operational_status_counts_observed_authentication_failure(request_factory):
    replicas = [
        OrchestratorReplica("orchestrator_a", b"z" * 32),
        OrchestratorReplica("orchestrator_b", TEST_KEYS["orchestrator_b"]),
        OrchestratorReplica("orchestrator_c", TEST_KEYS["orchestrator_c"]),
    ]
    decision = OrchestrationCoordinator(replicas, TEST_KEYS).adjudicate(request_factory())
    assert decision.selected_route_id == "route_alpha"
    assert replicas[0].status()["authentication_failures_observed"] == 1


def test_generated_message_fields_are_bounded(request_factory):
    replica = OrchestratorReplica(
        "orchestrator_a",
        TEST_KEYS["orchestrator_a"],
        policy=FixedPolicy("r" * 129),
    )
    try:
        replica.propose(request_factory())
    except Exception as exc:
        assert "128 characters" in str(exc)
    else:
        raise AssertionError("oversized proposal route was accepted")
