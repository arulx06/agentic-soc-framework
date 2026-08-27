from __future__ import annotations

from backend.app.services.orchestration_service import OrchestrationService
from orchestration.coordinator import BoundedReplayCache
from orchestration.instrumentation import OrchestrationInstrumentation
from orchestration.authentication import MessageVerifier
from orchestration.coordinator import DecisionRound
from orchestration.replica import OrchestratorReplica

from .conftest import TEST_KEYS


def test_replay_cache_is_bounded_and_detects_conflicting_identity():
    cache = BoundedReplayCache(2)
    assert cache.observe("orchestrator_a", "one", "a") == "NEW"
    assert cache.observe("orchestrator_a", "one", "a") == "DUPLICATE"
    assert cache.observe("orchestrator_a", "one", "b") == "CONFLICT"
    cache.observe("orchestrator_b", "two", "b")
    cache.observe("orchestrator_c", "three", "c")
    assert len(cache) == 2


def test_instrumentation_latency_and_rejection_histories_are_bounded():
    metrics = OrchestrationInstrumentation(latency_limit=2, rejection_limit=1)
    for value in (1, 2, 3):
        metrics.latency("decision_ms", value)
        metrics.rejection({"value": value})
    snapshot = metrics.snapshot()
    assert snapshot["latencies"]["decision_ms"]["count"] == 2
    assert snapshot["recent_rejections"] == [{"value": 3}]


def test_decision_replica_and_round_histories_are_bounded(request_factory):
    service = OrchestrationService(
        keys=TEST_KEYS,
        decision_history_limit=2,
        round_history_limit=2,
        recent_outcomes_limit=2,
    )
    for index in range(4):
        service.adjudicate(
            request_factory(request_id=f"request-{index}", round_id=f"round-{index}"),
            principal="test-principal",
        )
    assert len(service._decisions) == 2
    assert len(service.coordinator._rounds) == 2
    assert all(len(replica._recent_outcomes) == 2 for replica in service.replicas)


def test_per_round_rejection_evidence_is_bounded(request_factory):
    request = request_factory()
    state = DecisionRound(
        request,
        MessageVerifier(TEST_KEYS),
        BoundedReplayCache(4),
        OrchestrationInstrumentation(),
    )
    proposal = OrchestratorReplica("orchestrator_a", TEST_KEYS["orchestrator_a"]).propose(request)
    state.close()
    for _ in range(100):
        state.accept_proposal(proposal)
    assert len(state.rejections) == 64
