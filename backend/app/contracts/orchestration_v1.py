"""Versioned public projections for the Stage-6 orchestration service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from orchestration.contracts import OrchestrationDecisionV1, OrchestrationOutcome


class ApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrchestratorStatusV1(ApiContract):
    schema_version: Literal["orchestrator_status_v1"] = "orchestrator_status_v1"
    orchestrator_id: str
    health: Literal["HEALTHY", "DEGRADED", "UNAVAILABLE"]
    available: bool
    messages_proposed: int
    votes_issued: int
    authentication_failures_observed: int
    timeouts: int
    omissions: int
    last_error: str | None
    recent_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    recent_outcomes_limit: int


class OrchestratorListingV1(ApiContract):
    schema_version: Literal["orchestrator_listing_v1"] = "orchestrator_listing_v1"
    replicas: list[OrchestratorStatusV1]
    note: str


class OrchestrationHealthV1(ApiContract):
    schema_version: Literal["orchestration_health_v1"] = "orchestration_health_v1"
    status: Literal["ok", "degraded", "offline"]
    orchestrators_available: int
    orchestrators_total: Literal[3] = 3
    required_quorum: Literal[2] = 2
    event_namespace: Literal["orchestration-ops"] = "orchestration-ops"
    decision_history_persistent: Literal[False] = False
    instrumentation: dict[str, Any]


class OrchestrationDecisionListingV1(ApiContract):
    schema_version: Literal["orchestration_decision_listing_v1"] = (
        "orchestration_decision_listing_v1"
    )
    decisions: list[OrchestrationDecisionV1]
    total_retained: int
    limit: int
    offset: int
    history_complete: Literal[False] = False
    bounds: dict[str, int]
