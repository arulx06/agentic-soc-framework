"""Stage-4B public Blackboard snapshot/status contracts.

Versioned API projection of the verified Stage-4A core. These models only
REPRESENT backend-produced state; they never recompute scientific values.
Read-outcome and write-outcome distinctions (INSUFFICIENT_QUORUM,
INCONSISTENT, PARTIAL_COMMIT ...) are preserved verbatim — never
normalized into generic success/failure.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

BLACKBOARD_SNAPSHOT_SCHEMA_VERSION = "blackboard_snapshot_v1"
BLACKBOARD_HEALTH_SCHEMA_VERSION = "blackboard_health_v1"


class ReplicaStatusV1(BaseModel):
    """Operational replication status. Deliberately contains NO trust
    score / reliability dimension — those are later Agent-Trust/L-ZTAF
    concepts."""

    replica_id: str
    health: str  # HEALTHY | UNAVAILABLE | DIVERGED
    available: bool
    storage_error_count: int = 0
    last_error: str | None = None
    committed_record_count: int = 0
    pending_record_count: int = 0
    divergence_history: list[str] = Field(default_factory=list)
    head: dict[str, Any] | None = None  # {record_key, record_version} | None


class RecordSummaryV1(BaseModel):
    """Bounded committed-record summary (no payload by default)."""

    record_key: str
    record_type: str
    record_version: int
    record_id: str
    content_hash: str
    author_id: str
    source_component: str
    logical_timestamp: str | None = None
    window_id: int | None = None
    supporting_replicas: list[str] = Field(default_factory=list)


class BlackboardSnapshotV1(BaseModel):
    schema_version: str = Field(default=BLACKBOARD_SNAPSHOT_SCHEMA_VERSION)
    snapshot_id: str
    generated_at_utc: str

    scope_replay_id: str | None = None

    latest_by_key: dict[str, RecordSummaryV1] = Field(default_factory=dict)
    recent_records: list[RecordSummaryV1] = Field(default_factory=list)

    replica_statuses: list[ReplicaStatusV1] = Field(default_factory=list)
    divergent_replicas: list[str] = Field(default_factory=list)

    # Bounded instrumentation counters — implementation metrics, NOT final
    # research performance results.
    counters: dict[str, int] = Field(default_factory=dict)
    latencies: dict[str, Any] = Field(default_factory=dict)
    recent_rejections: list[dict[str, Any]] = Field(default_factory=list)

    unverified_rows_excluded: int = 0

    #: True when any responsive replica had more committed rows than the
    #: configured scan bound: the view is BOUNDED/TRUNCATED, not complete.
    truncated: bool = False
    truncated_replicas: list[str] = Field(default_factory=list)

    bounds: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class BlackboardHealthV1(BaseModel):
    schema_version: str = Field(default=BLACKBOARD_HEALTH_SCHEMA_VERSION)
    status: str  # ok | degraded | offline
    replicas_available: int
    replicas_total: int
    divergent_replicas: list[str] = Field(default_factory=list)
    counters: dict[str, int] = Field(default_factory=dict)


class DevWriteRequestV1(BaseModel):
    """Restricted development/test write: SYSTEM_RECORD type only.

    Scientific Finding records can never originate here — they enter the
    Blackboard exclusively through the Finding Gateway integration.
    """

    record_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    logical_timestamp: str | None = None
    window_id: int | None = None


class DevWriteResponseV1(BaseModel):
    schema_version: str = Field(default=BLACKBOARD_HEALTH_SCHEMA_VERSION)
    outcome: str  # WriteOutcome value — PARTIAL_COMMIT stays distinct
    operation_id: str
    record_id: str | None = None
    record_key: str | None = None
    record_version: int | None = None
    content_hash: str | None = None
    reason: str | None = None
    replica_sync: dict[str, str] = Field(default_factory=dict)
    durable_commit_ack_count: int = 0
