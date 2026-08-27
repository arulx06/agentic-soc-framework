"""Mechanical Stage-6 control-plane routing policy."""

from __future__ import annotations

from typing import Protocol

from orchestration.contracts import OrchestrationRequestV1


class RoutingPolicy(Protocol):
    policy_id: str
    policy_version: str

    def propose(self, request: OrchestrationRequestV1) -> tuple[str, str]: ...


class DeterministicPriorityPolicy:
    """Choose minimum priority, then route ID; no security reasoning occurs."""

    policy_id = "stage6_deterministic_priority"
    policy_version = "1"

    def propose(self, request: OrchestrationRequestV1) -> tuple[str, str]:
        candidate = min(request.candidate_routes, key=lambda item: (item.priority, item.route_id))
        return candidate.route_id, "MIN_PRIORITY_ROUTE_ID_TIEBREAK"
