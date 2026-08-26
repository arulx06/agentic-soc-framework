"""Typed, versioned Blackboard record and result contracts.

Identity semantics
------------------
record_key      identity of ONE logical Blackboard item;
record_version  monotonically increasing version of that logical item
                (committed versions start at 1);
record_id       immutable identity of ONE concrete version, derived as
                ``{record_key}#v{record_version}#{content_hash[:12]}`` —
                two proposals for the same next version with different
                content therefore carry different record_ids.

The contract is an immutable value object (pydantic frozen model). The
integrity validator recomputes ``content_hash`` over exactly the fields in
``HASHED_FIELDS`` and re-derives ``record_id`` on every construction,
validation and storage load. Operational fields (operation ids, acks,
latencies, wall-clock stamps) never live on the record and therefore never
enter the hash.

Ground-truth firewall: payload and provenance are checked recursively with
the Stage-3 firewall (backend.app.contracts.common) plus a Blackboard-local
extension that rejects DataSense scenario-identity keys — a scenario name
itself encodes category/target information, so runtime records must carry
the opaque ``session_trace`` digest instead.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from backend.app.contracts.common import find_ground_truth_violations
from blackboard.hashing import canonical_content_hash, canonical_json_str

BLACKBOARD_RECORD_SCHEMA_VERSION = "blackboard_record_v1"
BLACKBOARD_ACK_SCHEMA_VERSION = "blackboard_ack_v1"
BLACKBOARD_WRITE_RESULT_SCHEMA_VERSION = "blackboard_write_result_v1"
BLACKBOARD_READ_RESULT_SCHEMA_VERSION = "blackboard_read_result_v1"


# --------------------------------------------------------------------------
# Record-type registry (Stage 4A scope only)
# --------------------------------------------------------------------------


class BlackboardRecordType(str, enum.Enum):
    """Record categories grounded in existing backend capabilities.

    Later stages (orchestration votes, trust decisions, watchdog state,
    threat-intelligence correlation ...) may extend this registry
    explicitly. They are deliberately absent here.
    """

    NETWORK_FINDING_RECORD = "NETWORK_FINDING_RECORD"
    BEHAVIOR_FINDING_RECORD = "BEHAVIOR_FINDING_RECORD"
    DEVICE_STATE_RECORD = "DEVICE_STATE_RECORD"
    DEVICE_RISK_SNAPSHOT_RECORD = "DEVICE_RISK_SNAPSHOT_RECORD"
    DEVICE_ONLY_SREP_RECORD = "DEVICE_ONLY_SREP_RECORD"
    SYSTEM_RECORD = "SYSTEM_RECORD"


RECORD_TYPES: frozenset[BlackboardRecordType] = frozenset(BlackboardRecordType)


# --------------------------------------------------------------------------
# Ground-truth firewall (reuses the Stage-3 recursive checker)
# --------------------------------------------------------------------------

#: Keys forbidden IN ADDITION to the shared Stage-3 set. A DataSense
#: scenario id/name embeds attack category and target device, so raw
#: scenario identity must travel only as the opaque `session_trace`
#: digest defined in pipeline.findings.
BLACKBOARD_EXTRA_FORBIDDEN_KEYS = frozenset(
    {"scenario_id", "scenario_name", "scenario_ids", "scenario_names", "filename"}
)


def _walk_extra_forbidden_keys(value: Any, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            key_path = f"{path}.{k}"
            if isinstance(k, str) and k.strip().lower() in BLACKBOARD_EXTRA_FORBIDDEN_KEYS:
                out.append(key_path)
            _walk_extra_forbidden_keys(v, key_path, out)
    elif isinstance(value, (list, tuple, set)):
        for i, item in enumerate(list(value)[:500]):
            _walk_extra_forbidden_keys(item, f"{path}[{i}]", out)
    elif isinstance(value, BaseModel):
        _walk_extra_forbidden_keys(value.model_dump(), path, out)


def find_blackboard_firewall_violations(value: Any, path: str = "$") -> list[str]:
    """All ground-truth leakage paths (shared set + Blackboard extension)."""
    violations = list(find_ground_truth_violations(value, path))
    _walk_extra_forbidden_keys(value, path, violations)
    return violations


def assert_blackboard_firewall(value: Any, what: str) -> None:
    violations = find_blackboard_firewall_violations(value)
    if violations:
        raise ValueError(f"ground-truth leakage in {what} at: {violations[:10]}")


# --------------------------------------------------------------------------
# Hashed-field definition
# --------------------------------------------------------------------------

#: Exactly these record fields participate in the canonical content hash —
#: nothing replica-local, operational or wall-clock based.
HASHED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "record_key",
    "record_type",
    "record_version",
    "logical_timestamp",
    "window_id",
    "author_id",
    "source_component",
    "payload",
    "provenance",
)


def derive_record_id(record_key: str, record_version: int, content_hash: str) -> str:
    """Immutable identity of one concrete version of one logical item."""
    return f"{record_key}#v{record_version}#{content_hash[:12]}"


class RecordIntegrityError(ValueError):
    """Raised when a record's stored hash/id does not match its content."""


# --------------------------------------------------------------------------
# Timestamp / scalar helpers
# --------------------------------------------------------------------------


def validate_utc_timestamp(ts_utc: str) -> None:
    """ISO-8601 string with explicit UTC offset (mirrors pipeline.findings)."""
    if not isinstance(ts_utc, str):
        raise TypeError("timestamp must be an ISO-8601 string")
    text = ts_utc.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        raise ValueError("timestamp must carry an explicit UTC offset")
    _ = dt.astimezone(timezone.utc)


_RECORD_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def _check_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > 128:
        raise ValueError(f"{name} must be at most 128 characters")


# --------------------------------------------------------------------------
# Record contract
# --------------------------------------------------------------------------


class BlackboardRecordV1(BaseModel):
    """Immutable, versioned Blackboard record (schema blackboard_record_v1).

    Construction, validation and loading all verify that ``content_hash``
    is the canonical SHA-256 over :data:`HASHED_FIELDS` and that
    ``record_id`` is the derivation of (key, version, hash). Use
    :func:`build_record` to create records; ``model_construct`` bypasses
    verification and exists for fault-injection tests only.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(default=BLACKBOARD_RECORD_SCHEMA_VERSION)

    record_id: str
    record_key: str
    record_type: BlackboardRecordType
    record_version: int

    logical_timestamp: str | None = None
    window_id: int | None = None

    author_id: str
    source_component: str

    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    content_hash: str

    @field_validator("schema_version")
    @classmethod
    def _supported_schema(cls, v: str) -> str:
        if v != BLACKBOARD_RECORD_SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {v!r}")
        return v

    @field_validator("record_key")
    @classmethod
    def _key_shape(cls, v: str) -> str:
        if not _RECORD_KEY_RE.match(v):
            raise ValueError(
                "record_key must match ^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
            )
        return v

    @field_validator("record_version")
    @classmethod
    def _version_positive(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError("record_version must be an integer >= 1")
        return v

    @field_validator("window_id")
    @classmethod
    def _window_non_negative(cls, v: int | None) -> int | None:
        if v is not None and (isinstance(v, bool) or v < 0):
            raise ValueError("window_id must be an integer >= 0 when present")
        return v

    @field_validator("author_id", "source_component")
    @classmethod
    def _identifiers(cls, v: str, info) -> str:
        _check_identifier(info.field_name, v)
        return v

    @field_validator("payload", "provenance")
    @classmethod
    def _firewall(cls, v: dict[str, Any], info) -> dict[str, Any]:
        assert_blackboard_firewall(v, info.field_name)
        return v

    @field_validator("logical_timestamp")
    @classmethod
    def _logical_ts(cls, v: str | None) -> str | None:
        if v is not None:
            validate_utc_timestamp(v)
        return v

    @field_validator("content_hash", "record_id")
    @classmethod
    def _opaque_hexish(cls, v: str, info) -> str:
        if not isinstance(v, str) or not v:
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @model_validator(mode="after")
    def _verify_integrity(self) -> "BlackboardRecordV1":
        verify_record_integrity(self)
        return self


def _hashed_field_dict(
    *,
    schema_version: str,
    record_key: str,
    record_type: BlackboardRecordType,
    record_version: int,
    logical_timestamp: str | None,
    window_id: int | None,
    author_id: str,
    source_component: str,
    payload: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Canonical projection: exactly HASHED_FIELDS, nothing else."""
    return {
        "schema_version": schema_version,
        "record_key": record_key,
        "record_type": record_type.value if isinstance(record_type, BlackboardRecordType) else str(record_type),
        "record_version": record_version,
        "logical_timestamp": logical_timestamp,
        "window_id": window_id,
        "author_id": author_id,
        "source_component": source_component,
        "payload": payload,
        "provenance": provenance,
    }


def compute_content_hash(fields: dict[str, Any]) -> str:
    """SHA-256 over the canonical serialization of the hashed projection."""
    projection = {k: fields[k] for k in HASHED_FIELDS}
    return canonical_content_hash(projection)


def verify_record_integrity(record: BlackboardRecordV1) -> None:
    """Raise :class:`RecordIntegrityError` unless hash AND id both match.

    Also detects post-construction mutation of the mutable ``payload`` /
    ``provenance`` dicts (frozen pydantic does not deep-freeze dicts).
    """
    expected_hash = compute_content_hash(
        _hashed_field_dict(
            schema_version=record.schema_version,
            record_key=record.record_key,
            record_type=record.record_type,
            record_version=record.record_version,
            logical_timestamp=record.logical_timestamp,
            window_id=record.window_id,
            author_id=record.author_id,
            source_component=record.source_component,
            payload=record.payload,
            provenance=record.provenance,
        )
    )
    if record.content_hash != expected_hash:
        raise RecordIntegrityError(
            f"content_hash mismatch for {record.record_key!r}: "
            f"stored={record.content_hash!r} computed={expected_hash!r}"
        )
    expected_id = derive_record_id(
        record.record_key, record.record_version, expected_hash
    )
    if record.record_id != expected_id:
        raise RecordIntegrityError(
            f"record_id mismatch: stored={record.record_id!r} "
            f"expected={expected_id!r}"
        )


def build_record(
    *,
    record_key: str,
    record_type: BlackboardRecordType | str,
    record_version: int,
    author_id: str,
    source_component: str,
    payload: dict[str, Any],
    provenance: dict[str, Any] | None = None,
    logical_timestamp: str | None = None,
    window_id: int | None = None,
    schema_version: str = BLACKBOARD_RECORD_SCHEMA_VERSION,
) -> BlackboardRecordV1:
    """Construct a fully verified record (computes hash and record_id).

    Raises ValueError/TypeError/pydantic.ValidationError on any schema,
    firewall or serialization problem (e.g. non-JSON-serializable payload
    values, NaN floats, oversized content handled separately by
    :func:`ensure_record_size`).
    """
    rtype = (
        record_type
        if isinstance(record_type, BlackboardRecordType)
        else BlackboardRecordType(str(record_type))
    )
    fields = _hashed_field_dict(
        schema_version=schema_version,
        record_key=record_key,
        record_type=rtype,
        record_version=record_version,
        logical_timestamp=logical_timestamp,
        window_id=window_id,
        author_id=author_id,
        source_component=source_component,
        payload=payload,
        provenance=provenance or {},
    )
    # Fail fast on non-serializable / NaN content before hashing.
    try:
        content_hash = compute_content_hash(fields)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"record content is not canonically serializable: {exc}") from exc
    return BlackboardRecordV1(
        record_id=derive_record_id(record_key, record_version, content_hash),
        record_key=record_key,
        record_type=rtype,
        record_version=record_version,
        logical_timestamp=logical_timestamp,
        window_id=window_id,
        author_id=author_id,
        source_component=source_component,
        payload=payload,
        provenance=provenance or {},
        content_hash=content_hash,
    )


def ensure_record_size(record: BlackboardRecordV1, max_bytes: int) -> None:
    """Reject records whose full canonical serialization is oversized."""
    size = len(canonical_json_str(record.model_dump()).encode("utf-8"))
    if size > max_bytes:
        raise ValueError(
            f"record canonical size {size} exceeds limit {max_bytes} bytes"
        )


# --------------------------------------------------------------------------
# Proposal draft (pre-hash input accepted by the coordinator)
# --------------------------------------------------------------------------


class BlackboardRecordDraft(BaseModel):
    """Caller-supplied proposal without derived integrity fields."""

    model_config = ConfigDict(frozen=True)

    record_key: str
    record_type: BlackboardRecordType
    record_version: int
    logical_timestamp: str | None = None
    window_id: int | None = None
    author_id: str
    source_component: str
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("record_key")
    @classmethod
    def _key_shape(cls, v: str) -> str:
        if not _RECORD_KEY_RE.match(v):
            raise ValueError(
                "record_key must match ^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
            )
        return v

    @field_validator("record_version")
    @classmethod
    def _version_non_negative(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError("record_version must be an integer >= 1")
        return v

    @field_validator("author_id", "source_component")
    @classmethod
    def _identifiers(cls, v: str, info) -> str:
        _check_identifier(info.field_name, v)
        return v

    @field_validator("payload", "provenance")
    @classmethod
    def _firewall(cls, v: dict[str, Any], info) -> dict[str, Any]:
        assert_blackboard_firewall(v, info.field_name)
        return v

    @field_validator("logical_timestamp")
    @classmethod
    def _logical_ts(cls, v: str | None) -> str | None:
        if v is not None:
            validate_utc_timestamp(v)
        return v

    def to_record(self) -> BlackboardRecordV1:
        return build_record(
            record_key=self.record_key,
            record_type=self.record_type,
            record_version=self.record_version,
            logical_timestamp=self.logical_timestamp,
            window_id=self.window_id,
            author_id=self.author_id,
            source_component=self.source_component,
            payload=dict(self.payload),
            provenance=dict(self.provenance),
        )


# --------------------------------------------------------------------------
# Acknowledgements
# --------------------------------------------------------------------------


class AckStatus(str, enum.Enum):
    ACK_PREPARED = "ACK_PREPARED"
    ACK_COMMITTED = "ACK_COMMITTED"
    ABORTED = "ABORTED"
    REJECT_STALE = "REJECT_STALE"
    REJECT_CONFLICT = "REJECT_CONFLICT"
    REJECT_SCHEMA = "REJECT_SCHEMA"
    REJECT_INTEGRITY = "REJECT_INTEGRITY"
    REJECT_AUTHORIZATION = "REJECT_AUTHORIZATION"
    UNAVAILABLE = "UNAVAILABLE"
    STORAGE_ERROR = "STORAGE_ERROR"


class ReplicaAckV1(BaseModel):
    """Explicit per-replica acknowledgement; status is never inferred from
    absence of an exception."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(default=BLACKBOARD_ACK_SCHEMA_VERSION)
    operation_id: str
    replica_id: str
    operation_kind: str
    ack_status: AckStatus
    reason: str | None = None

    record_id: str | None = None
    record_key: str | None = None
    record_version: int | None = None
    content_hash: str | None = None

    #: Head version observed at the replica during the operation, when the
    #: operation consulted committed state (stale/conflict rejections).
    current_version_at_replica: int | None = None

    logical_timestamp: str | None = None
    latency_ms: float | None = None
    observed_at_utc: str


# --------------------------------------------------------------------------
# Global write results
# --------------------------------------------------------------------------


class WriteOutcome(str, enum.Enum):
    COMMITTED = "COMMITTED"
    #: Quorum entered the commit phase but fewer than the required
    #: replicas completed it: durable committed data exists on exactly one
    #: replica. Explicitly NOT COMMITTED and NOT a clean storage failure —
    #: the state is indeterminate pending reconciliation.
    PARTIAL_COMMIT = "PARTIAL_COMMIT"
    REJECTED_STALE = "REJECTED_STALE"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"
    REJECTED_SCHEMA = "REJECTED_SCHEMA"
    REJECTED_AUTHORIZATION = "REJECTED_AUTHORIZATION"
    FAILED_QUORUM = "FAILED_QUORUM"
    FAILED_STORAGE = "FAILED_STORAGE"


class ReplicationSyncState(str, enum.Enum):
    SYNCED = "SYNCED"
    DIVERGENT_REQUIRES_RECONCILIATION = "DIVERGENT_REQUIRES_RECONCILIATION"
    NOT_PREPARED = "NOT_PREPARED"
    ABORTED = "ABORTED"
    UNAVAILABLE = "UNAVAILABLE"


class WriteResultV1(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(default=BLACKBOARD_WRITE_RESULT_SCHEMA_VERSION)
    operation_id: str
    outcome: WriteOutcome
    reason: str | None = None

    principal: str
    record_id: str | None = None
    record_key: str | None = None
    record_type: str | None = None
    record_version: int | None = None
    content_hash: str | None = None

    acks: tuple[ReplicaAckV1, ...] = ()
    replica_sync: dict[str, str] = Field(default_factory=dict)

    started_at_utc: str
    completed_at_utc: str
    duration_ms: float


# --------------------------------------------------------------------------
# Read results
# --------------------------------------------------------------------------


class ReadOutcome(str, enum.Enum):
    CONSISTENT = "CONSISTENT"
    DEGRADED_CONSISTENT = "DEGRADED_CONSISTENT"
    NOT_FOUND = "NOT_FOUND"
    #: Fewer than quorum-size replicas could confirm value OR absence.
    #: Never carries an authoritative record.
    INSUFFICIENT_QUORUM = "INSUFFICIENT_QUORUM"
    INCONSISTENT = "INCONSISTENT"
    UNAVAILABLE = "UNAVAILABLE"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"


class ReplicaReadObservationV1(BaseModel):
    model_config = ConfigDict(frozen=True)

    replica_id: str
    responded: bool
    found: bool = False
    record_version: int | None = None
    content_hash: str | None = None
    detail: str | None = None


class ReadResultV1(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(default=BLACKBOARD_READ_RESULT_SCHEMA_VERSION)
    read_operation_id: str
    principal: str
    record_key: str
    requested_version: int | None = None

    outcome: ReadOutcome
    record: BlackboardRecordV1 | None = None
    reason: str | None = None

    observations: tuple[ReplicaReadObservationV1, ...] = ()
    divergent_replicas: tuple[str, ...] = ()
    unavailable_replicas: tuple[str, ...] = ()

    duration_ms: float
