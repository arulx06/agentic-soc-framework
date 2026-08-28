"""EventEnvelopeV1 and the replay event-type registry."""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.app.contracts.common import assert_no_ground_truth


class ReplayEventType(str, enum.Enum):
    REPLAY_CREATED = "REPLAY_CREATED"
    REPLAY_STARTED = "REPLAY_STARTED"
    REPLAY_PAUSED = "REPLAY_PAUSED"
    REPLAY_RESUMED = "REPLAY_RESUMED"
    REPLAY_STEPPED = "REPLAY_STEPPED"
    REPLAY_COMPLETED = "REPLAY_COMPLETED"
    REPLAY_FAILED = "REPLAY_FAILED"

    WINDOW_STARTED = "WINDOW_STARTED"
    WINDOW_COMPLETED = "WINDOW_COMPLETED"

    NETWORK_FINDING = "NETWORK_FINDING"
    BEHAVIOR_FINDING = "BEHAVIOR_FINDING"

    GATEWAY_ACCEPTED = "GATEWAY_ACCEPTED"
    GATEWAY_REJECTED = "GATEWAY_REJECTED"

    DEVICE_STATE = "DEVICE_STATE"

    DEVICE_RISK_GRAPH_SNAPSHOT = "DEVICE_RISK_GRAPH_SNAPSHOT"
    COMMUNICATION_GRAPH_SNAPSHOT = "COMMUNICATION_GRAPH_SNAPSHOT"

    SREP_SNAPSHOT = "SREP_SNAPSHOT"

    # ------------------------------------------------------------------
    # Stage-4B Blackboard backend events (same envelope, same chronology)
    # ------------------------------------------------------------------
    BLACKBOARD_WRITE_PROPOSED = "BLACKBOARD_WRITE_PROPOSED"
    BLACKBOARD_REPLICA_ACK = "BLACKBOARD_REPLICA_ACK"
    BLACKBOARD_WRITE_COMMITTED = "BLACKBOARD_WRITE_COMMITTED"
    BLACKBOARD_WRITE_PARTIAL = "BLACKBOARD_WRITE_PARTIAL"
    BLACKBOARD_WRITE_ABORTED = "BLACKBOARD_WRITE_ABORTED"
    BLACKBOARD_WRITE_REJECTED = "BLACKBOARD_WRITE_REJECTED"
    BLACKBOARD_STALE_WRITE = "BLACKBOARD_STALE_WRITE"
    BLACKBOARD_CONFLICT = "BLACKBOARD_CONFLICT"
    BLACKBOARD_QUORUM_FAILED = "BLACKBOARD_QUORUM_FAILED"
    BLACKBOARD_STORAGE_FAILED = "BLACKBOARD_STORAGE_FAILED"
    BLACKBOARD_READ = "BLACKBOARD_READ"
    BLACKBOARD_READ_INCONSISTENT = "BLACKBOARD_READ_INCONSISTENT"
    BLACKBOARD_REPLICA_STATUS = "BLACKBOARD_REPLICA_STATUS"

    # Stage-6 authenticated orchestrator quorum facts.
    ORCHESTRATION_REQUEST_RECEIVED = "ORCHESTRATION_REQUEST_RECEIVED"
    ORCHESTRATOR_PROPOSAL = "ORCHESTRATOR_PROPOSAL"
    ORCHESTRATOR_VOTE = "ORCHESTRATOR_VOTE"
    ORCHESTRATOR_TIMEOUT = "ORCHESTRATOR_TIMEOUT"
    ORCHESTRATOR_DELAYED = "ORCHESTRATOR_DELAYED"
    ORCHESTRATOR_OMISSION = "ORCHESTRATOR_OMISSION"
    ORCHESTRATOR_STATUS = "ORCHESTRATOR_STATUS"
    ORCHESTRATION_QUORUM_REACHED = "ORCHESTRATION_QUORUM_REACHED"
    ORCHESTRATION_NO_QUORUM = "ORCHESTRATION_NO_QUORUM"
    ORCHESTRATION_DECISION = "ORCHESTRATION_DECISION"

    # Stage-8B scientific workflow events (one per-replay sequence)
    WORKFLOW_WINDOW_STARTED = "WORKFLOW_WINDOW_STARTED"
    AGENT_DISPATCHED = "AGENT_DISPATCHED"
    AGENT_EXECUTION_STARTED = "AGENT_EXECUTION_STARTED"
    AGENT_EXECUTION_COMPLETED = "AGENT_EXECUTION_COMPLETED"
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    AGENT_EXECUTION_SKIPPED = "AGENT_EXECUTION_SKIPPED"
    THREAT_CORRELATION_PRODUCED = "THREAT_CORRELATION_PRODUCED"
    RISK_RECOMMENDATION_PRODUCED = "RISK_RECOMMENDATION_PRODUCED"
    ACCESS_RECOMMENDATION_PRODUCED = "ACCESS_RECOMMENDATION_PRODUCED"
    ENFORCEMENT_DECISION_COMMITTED = "ENFORCEMENT_DECISION_COMMITTED"
    CONFIRMED_FEEDBACK_RECORDED = "CONFIRMED_FEEDBACK_RECORDED"
    WORKFLOW_WINDOW_COMPLETED = "WORKFLOW_WINDOW_COMPLETED"
    WORKFLOW_WINDOW_FAILED = "WORKFLOW_WINDOW_FAILED"


EVENT_TYPES: frozenset[ReplayEventType] = frozenset(ReplayEventType)


class EventEnvelopeV1(BaseModel):
    schema_version: str = Field(default="simulation_event_v1")
    replay_id: str
    event_id: str
    sequence_number: int = Field(ge=0)
    event_type: ReplayEventType
    logical_timestamp: str | None = None
    window_id: int | None = None
    source_component: str
    entity_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _supported_schema(cls, v: str) -> str:
        if v != "simulation_event_v1":
            raise ValueError(f"unsupported schema_version {v!r}")
        return v

    @field_validator("payload", "provenance")
    @classmethod
    def _no_ground_truth(cls, v: dict[str, Any]) -> dict[str, Any]:
        assert_no_ground_truth(v, cls.__name__)
        return v
