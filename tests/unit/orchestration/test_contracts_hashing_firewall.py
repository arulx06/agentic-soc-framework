from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from orchestration.contracts import CandidateRouteV1
from orchestration.firewall import ORCHESTRATION_FORBIDDEN_KEYS
from orchestration.hashing import request_digest


def test_request_digest_normalizes_candidate_order(request_factory):
    candidates = (
        CandidateRouteV1(route_id="route_beta", priority=2),
        CandidateRouteV1(route_id="route_alpha", priority=1),
    )
    forward = request_factory(candidates=candidates)
    reverse = request_factory(candidates=tuple(reversed(candidates)))
    assert request_digest(forward) == request_digest(reverse)


def test_substantive_candidate_change_changes_request_digest(request_factory):
    original = request_factory()
    changed = request_factory(
        candidates=(
            CandidateRouteV1(route_id="route_alpha", priority=99),
            CandidateRouteV1(route_id="route_beta", priority=2),
        )
    )
    assert request_digest(original) != request_digest(changed)


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf, object()])
def test_non_json_and_non_finite_provenance_is_rejected(request_factory, bad_value):
    with pytest.raises((ValidationError, ValueError, TypeError)):
        request_factory(provenance={"runtime_value": bad_value})


@pytest.mark.parametrize("forbidden", sorted(ORCHESTRATION_FORBIDDEN_KEYS))
def test_every_forbidden_ground_truth_key_is_rejected_nested(request_factory, forbidden):
    with pytest.raises(ValidationError, match="ground-truth leakage"):
        request_factory(provenance={"nested": [{"deeper": {forbidden: "secret"}}]})


def test_candidate_routes_are_typed_unique_and_bounded(request_factory):
    duplicate = CandidateRouteV1(route_id="route_alpha", priority=1)
    with pytest.raises(ValidationError, match="must be unique"):
        request_factory(candidates=(duplicate, duplicate))


def test_oversized_nested_collection_is_rejected_not_partially_scanned(request_factory):
    values = [{"runtime": index} for index in range(500)] + [
        {"scenario_id": "must-not-bypass-firewall"}
    ]
    with pytest.raises(ValidationError, match="ground-truth leakage"):
        request_factory(provenance={"items": values})
