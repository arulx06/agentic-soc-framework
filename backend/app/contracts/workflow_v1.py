"""Stage-8B workflow/action/feedback transport contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkflowSnapshotV1(BaseModel):
    schema_version: Literal["workflow_snapshot_v1"] = "workflow_snapshot_v1"
    replay_id: str
    workflow_mode: Literal["FIVE_AGENT_LIVE"] = "FIVE_AGENT_LIVE"
    workflow_id: str
    current_window_id: int | None = None
    last_window_id: int | None = None
    recent_windows: list[dict[str, Any]] = Field(default_factory=list)
    five_agent_statuses: list[dict[str, Any]] = Field(default_factory=list)
    latest_threat_correlations: list[dict[str, Any]] = Field(default_factory=list)
    latest_risk_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    latest_access_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    latest_enforcement_decisions: list[dict[str, Any]] = Field(default_factory=list)
    recent_failures: list[dict[str, Any]] = Field(default_factory=list)
    bounds: dict[str, Any] = Field(default_factory=dict)
    instrumentation: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ActionListingV1(BaseModel):
    schema_version: Literal["action_listing_v1"] = "action_listing_v1"
    replay_id: str
    actions: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    history_complete: Literal[False] = False
    bounds: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequestV1(BaseModel):
    window_id: int = Field(ge=0)
    entity_id: str = Field(min_length=1, max_length=128)
    related_action_id: str = Field(min_length=1, max_length=128)
    related_finding_ids: list[str] = Field(default_factory=list)
    feedback_source: str = Field(min_length=1, max_length=64)
    confirmed: bool = Field(default=True)
    verdict: str = Field(min_length=1, max_length=32)
    reason_code: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=512)
    provenance: dict[str, Any] = Field(default_factory=dict)
