from __future__ import annotations

from backend.app.contracts.events_v1 import ReplayEventType
from backend.app.services.orchestration_service import OrchestrationService

from .conftest import DelayHooks, FixedPolicy, TEST_KEYS


def test_event_summaries_preserve_observed_completion_order_not_identity_sort(request_factory):
    routes = {
        "orchestrator_a": FixedPolicy("route_alpha"),
        "orchestrator_b": FixedPolicy("route_beta"),
        "orchestrator_c": FixedPolicy("route_gamma"),
    }
    service = OrchestrationService(
        keys=TEST_KEYS,
        policies=routes,
        hooks={
            "orchestrator_a": DelayHooks(0.03),
            "orchestrator_b": DelayHooks(0.01),
        },
        timeout_seconds=0.2,
    )
    published = []
    service.publisher = lambda event_type, payload, **context: published.append(
        (event_type, payload)
    )
    service.adjudicate(request_factory(), principal="test-principal")
    proposal_senders = [
        payload["orchestrator_id"]
        for event_type, payload in published
        if event_type is ReplayEventType.ORCHESTRATOR_PROPOSAL
    ]
    assert proposal_senders == ["orchestrator_c", "orchestrator_b", "orchestrator_a"]
