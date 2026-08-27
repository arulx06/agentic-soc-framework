from __future__ import annotations

import time

import pytest

from orchestration.contracts import CandidateRouteV1, ORCHESTRATOR_IDS, OrchestrationRequestV1
from orchestration.hooks import (
    OrchestratorHookPoint,
    OrchestratorHooks,
    OrchestratorOmissionError,
)


TEST_KEYS = {
    "orchestrator_a": b"a" * 32,
    "orchestrator_b": b"b" * 32,
    "orchestrator_c": b"c" * 32,
}


class FixedPolicy:
    policy_id = "fixed_test_policy"
    policy_version = "1"

    def __init__(self, route_id: str):
        self.route_id = route_id

    def propose(self, request):
        return self.route_id, "TEST_FIXED_ROUTE"


class DelayHooks(OrchestratorHooks):
    def __init__(self, seconds: float):
        self.seconds = seconds

    def observe(self, context):
        time.sleep(self.seconds)


class OmitHooks(OrchestratorHooks):
    def observe(self, context):
        raise OrchestratorOmissionError("test omission")


class VoteDelayHooks(OrchestratorHooks):
    def __init__(self, seconds: float):
        self.seconds = seconds

    def observe(self, context):
        if context.hook_point is OrchestratorHookPoint.ORCHESTRATOR_VOTE:
            time.sleep(self.seconds)


@pytest.fixture
def request_factory():
    def make(
        request_id: str = "request-1",
        round_id: str = "round-1",
        candidates=(
            CandidateRouteV1(route_id="route_alpha", priority=1),
            CandidateRouteV1(route_id="route_beta", priority=2),
            CandidateRouteV1(route_id="route_gamma", priority=3),
        ),
        provenance=None,
    ):
        return OrchestrationRequestV1(
            request_id=request_id,
            request_version=1,
            round_id=round_id,
            decision_kind="OPAQUE_ROUTE",
            candidate_routes=candidates,
            logical_timestamp="2026-08-28T00:00:00Z",
            window_id=7,
            source_component="tests.unit.orchestration",
            provenance=provenance or {"runtime_trace": "opaque-1"},
        )

    return make
