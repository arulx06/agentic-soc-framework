from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from backend.app.services.orchestration_service import (
    OrchestrationService,
    OrchestrationServiceError,
)

from .conftest import TEST_KEYS


def test_concurrent_duplicate_round_produces_only_one_final_decision(request_factory):
    service = OrchestrationService(keys=TEST_KEYS)
    request = request_factory()

    def invoke():
        try:
            return service.adjudicate(request, principal="test-principal")
        except OrchestrationServiceError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: invoke(), range(2)))
    decisions = [result for result in results if result is not None]
    assert len(decisions) == 1
    assert len(service._decisions) == 1


def test_same_round_identity_with_different_content_is_rejected(request_factory):
    service = OrchestrationService(keys=TEST_KEYS)
    first = request_factory()
    second = first.model_copy(
        update={"provenance": {"runtime_trace": "different-opaque-trace"}}
    )
    service.adjudicate(first, principal="test-principal")
    try:
        service.adjudicate(second, principal="test-principal")
    except OrchestrationServiceError as exc:
        assert exc.code == "invalid_or_duplicate_round"
        assert "different request content" in exc.message
    else:
        raise AssertionError("conflicting request content reused a terminal round")
