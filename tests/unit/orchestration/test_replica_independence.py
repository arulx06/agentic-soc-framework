from __future__ import annotations

from backend.app.services.orchestration_service import OrchestrationService
from orchestration.contracts import ORCHESTRATOR_IDS

from .conftest import TEST_KEYS


def test_exactly_three_distinct_orchestrator_instances_and_identities():
    service = OrchestrationService(keys=TEST_KEYS)
    assert tuple(replica.orchestrator_id for replica in service.replicas) == ORCHESTRATOR_IDS
    assert len({id(replica) for replica in service.replicas}) == 3
    assert set(ORCHESTRATOR_IDS).isdisjoint({"replica_a", "replica_b", "replica_c"})


def test_mutable_state_policy_hooks_and_history_are_not_aliased(request_factory):
    service = OrchestrationService(keys=TEST_KEYS)
    a, b, c = service.replicas
    assert len({id(replica.policy) for replica in service.replicas}) == 3
    assert len({id(replica.hooks) for replica in service.replicas}) == 3
    assert len({id(replica._recent_outcomes) for replica in service.replicas}) == 3
    a.propose(request_factory())
    assert a.status()["messages_proposed"] == 1
    assert b.status()["messages_proposed"] == 0
    assert c.status()["messages_proposed"] == 0


def test_replica_status_contains_operational_state_not_trust(request_factory):
    status = OrchestrationService(keys=TEST_KEYS).replica_statuses()[0].model_dump()
    forbidden = {"trust", "trust_score", "compromised", "malicious", "byzantine", "credential_state"}
    assert forbidden.isdisjoint(status)
