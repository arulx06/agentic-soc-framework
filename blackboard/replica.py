"""One independent Blackboard replica: its own state machine, lock, SQLite
store and health.

A replica is a fail-stop participant under an authenticated threat model:
it computes protocol steps honestly, may crash, may be set operationally
unavailable, and stages proposals it cannot itself make visible as
committed state.
"""

from __future__ import annotations

import enum
import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from blackboard.contracts import (
    AckStatus,
    BlackboardRecordV1,
    ReplicaAckV1,
    RecordIntegrityError,
    ensure_record_size,
    verify_record_integrity,
)
from blackboard.contracts import assert_blackboard_firewall
from blackboard.hashing import canonical_json_str
from blackboard.hooks import (
    BlackboardFaultHooks,
    HookContext,
    HookPoint,
    HookUnavailableError,
    ReplicaOperationKind,
)
from blackboard.storage import (
    CommitOutcome,
    PrepareOutcome,
    ReplicaDatabase,
)

DEFAULT_MAX_RECORD_BYTES = 262_144
DEFAULT_PENDING_LEASE_SECONDS = 300.0


class ReplicaHealth(str, enum.Enum):
    HEALTHY = "HEALTHY"
    UNAVAILABLE = "UNAVAILABLE"
    DIVERGED = "DIVERGED"


def record_to_storage_values(
    record: BlackboardRecordV1,
    *,
    operation_id: str,
    committed_at_utc: str,
) -> dict[str, Any]:
    """Canonical storage projection of a record."""
    return {
        "record_key": record.record_key,
        "record_version": record.record_version,
        "record_id": record.record_id,
        "record_type": record.record_type.value,
        "schema_version": record.schema_version,
        "logical_timestamp": record.logical_timestamp,
        "window_id": record.window_id,
        "author_id": record.author_id,
        "source_component": record.source_component,
        "payload_json": canonical_json_str(record.payload),
        "provenance_json": canonical_json_str(record.provenance),
        "content_hash": record.content_hash,
        "operation_id": operation_id,
        "committed_at_utc": committed_at_utc,
        # Full-record JSON used by commit_promote to move staging into the
        # committed table atomically.
        "record_json": _full_record_json(record),
    }


def _full_record_json(record: BlackboardRecordV1) -> str:
    return canonical_json_str(
        {
            "schema_version": record.schema_version,
            "record_id": record.record_id,
            "record_key": record.record_key,
            "record_type": record.record_type.value,
            "record_version": record.record_version,
            "logical_timestamp": record.logical_timestamp,
            "window_id": record.window_id,
            "author_id": record.author_id,
            "source_component": record.source_component,
            "payload_json": canonical_json_str(record.payload),
            "provenance_json": canonical_json_str(record.provenance),
            "content_hash": record.content_hash,
        }
    )


def row_to_record(row: dict[str, Any]) -> BlackboardRecordV1:
    """Rebuild a record from a storage row, re-verifying integrity so that
    any tampering with persisted bytes is detected on load."""
    _cj = canonical_json_str

    def _loads(text: str | None) -> dict[str, Any]:
        return {} if text is None else json.loads(text)

    payload = _loads(row["payload_json"])
    provenance = _loads(row["provenance_json"])
    record = BlackboardRecordV1.model_validate(
        {
            "schema_version": row["schema_version"],
            "record_id": row["record_id"],
            "record_key": row["record_key"],
            "record_type": row["record_type"],
            "record_version": int(row["record_version"]),
            "logical_timestamp": row.get("logical_timestamp"),
            "window_id": row.get("window_id"),
            "author_id": row["author_id"],
            "source_component": row["source_component"],
            "payload": payload,
            "provenance": provenance,
            "content_hash": row["content_hash"],
        }
    )
    # Re-canonicalize payload/provenance to detect byte-level tampering
    # that pydantic re-validation would tolerate (same semantic value).
    if _cj(payload) != row["payload_json"] or _cj(provenance) != row[
        "provenance_json"
    ]:
        raise RecordIntegrityError(
            f"stored serialization drift for {row['record_id']}"
        )
    return record


class BlackboardReplica:
    """Independent replica state machine over its own SQLite store."""

    def __init__(
        self,
        replica_id: str,
        db_path: Path,
        *,
        hooks: BlackboardFaultHooks | None = None,
        max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
        pending_lease_seconds: float = DEFAULT_PENDING_LEASE_SECONDS,
        divergence_history_limit: int = 16,
    ):
        self.replica_id = replica_id
        self.db = ReplicaDatabase(db_path, replica_id)
        self.hooks = hooks if hooks is not None else BlackboardFaultHooks()
        self.max_record_bytes = max_record_bytes
        self.pending_lease_seconds = pending_lease_seconds

        self._op_lock = threading.RLock()
        self._health = ReplicaHealth.HEALTHY
        self._unavailable_reason: str | None = None
        self._divergence_history: deque[str] = deque(maxlen=divergence_history_limit)
        self.last_error: str | None = None
        self.storage_error_count = 0
        self.prepared_count = 0
        self.committed_count = 0
        self.aborted_count = 0

    # ------------------------------------------------------------------
    # Health / operational control
    # ------------------------------------------------------------------

    @property
    def health(self) -> ReplicaHealth:
        return self._health

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable_reason

    @property
    def divergence_history(self) -> tuple[str, ...]:
        return tuple(self._divergence_history)

    def set_unavailable(self, reason: str) -> None:
        with self._op_lock:
            self._health = ReplicaHealth.UNAVAILABLE
            self._unavailable_reason = reason

    def set_available(self) -> None:
        with self._op_lock:
            self._health = ReplicaHealth.HEALTHY
            self._unavailable_reason = None

    def mark_diverged(self, detail: str) -> None:
        with self._op_lock:
            self._health = ReplicaHealth.DIVERGED
            self._divergence_history.append(detail)

    def clear_divergence(self) -> None:
        with self._op_lock:
            if self._health is ReplicaHealth.DIVERGED:
                self._health = ReplicaHealth.HEALTHY

    # ------------------------------------------------------------------
    # Lifecycle operations
    # ------------------------------------------------------------------

    def _ctx(
        self,
        operation_id: str,
        kind: ReplicaOperationKind,
        record: BlackboardRecordV1 | None = None,
    ) -> HookContext:
        return HookContext(
            hook_point=HookPoint.REPLICA_WRITE,
            operation_id=operation_id,
            replica_id=self.replica_id,
            operation_kind=kind,
            record_key=None if record is None else record.record_key,
            record_id=None if record is None else record.record_id,
        )

    def _base_ack(
        self,
        operation_id: str,
        kind: ReplicaOperationKind,
        status: AckStatus,
        started: float,
        record: BlackboardRecordV1 | None,
        reason: str | None,
        current_version_at_replica: int | None = None,
    ) -> ReplicaAckV1:
        return ReplicaAckV1(
            operation_id=operation_id,
            replica_id=self.replica_id,
            operation_kind=kind.value,
            ack_status=status,
            reason=reason,
            record_id=None if record is None else record.record_id,
            record_key=None if record is None else record.record_key,
            record_version=None if record is None else record.record_version,
            content_hash=None if record is None else record.content_hash,
            logical_timestamp=None if record is None else record.logical_timestamp,
            current_version_at_replica=current_version_at_replica,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            observed_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def prepare(
        self, operation_id: str, record: BlackboardRecordV1
    ) -> ReplicaAckV1:
        started = time.perf_counter()
        ctx = self._ctx(operation_id, ReplicaOperationKind.PREPARE, record)
        staged: BlackboardRecordV1 | None = None
        try:
            if self._health is ReplicaHealth.UNAVAILABLE:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.UNAVAILABLE,
                    started,
                    record,
                    self._unavailable_reason or "replica marked unavailable",
                )
            self.hooks.observe(ctx)
            substitute = self.hooks.intercept_record(ctx, record)
            staged = record if substitute is None else substitute

            if not isinstance(staged, BlackboardRecordV1):
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.REJECT_SCHEMA,
                    started,
                    None,
                    "staged object is not a BlackboardRecordV1",
                )
            try:
                verify_record_integrity(staged)
            except RecordIntegrityError as exc:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.REJECT_INTEGRITY,
                    started,
                    staged,
                    f"integrity verification failed: {exc}",
                )
            try:
                assert_blackboard_firewall(staged.payload, "payload")
                assert_blackboard_firewall(staged.provenance, "provenance")
                ensure_record_size(staged, self.max_record_bytes)
            except ValueError as exc:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.REJECT_SCHEMA,
                    started,
                    staged,
                    str(exc),
                )

            result = self.db.prepare_insert(
                record_key=staged.record_key,
                record_version=staged.record_version,
                record_id=staged.record_id,
                content_hash=staged.content_hash,
                operation_id=operation_id,
                record_json=_full_record_json(staged),
                created_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                lease_seconds=self.pending_lease_seconds,
            )
            if result.outcome in (
                PrepareOutcome.PREPARED,
                PrepareOutcome.PREPARED_LEASE_TAKEOVER,
            ):
                self.prepared_count += 1
                reason = (
                    "took over expired pending lease"
                    if result.outcome is PrepareOutcome.PREPARED_LEASE_TAKEOVER
                    else None
                )
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.ACK_PREPARED,
                    started,
                    staged,
                    reason,
                )
            if result.outcome is PrepareOutcome.REJECT_STALE:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.REJECT_STALE,
                    started,
                    staged,
                    f"current committed version is {result.current_version}",
                    current_version_at_replica=result.current_version,
                )
            if result.outcome is PrepareOutcome.REJECT_AHEAD:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.PREPARE,
                    AckStatus.REJECT_SCHEMA,
                    started,
                    staged,
                    f"expected_version ahead of committed state "
                    f"(current={result.current_version})",
                    current_version_at_replica=result.current_version,
                )
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.PREPARE,
                AckStatus.REJECT_CONFLICT,
                started,
                staged,
                "a different proposal holds this (key, next-version) slot "
                f"(pending operation {result.conflicting_operation_id})",
                current_version_at_replica=result.current_version,
            )
        except HookUnavailableError as exc:
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.PREPARE,
                AckStatus.UNAVAILABLE,
                started,
                staged or record,
                f"hook simulated unavailability: {exc}",
            )
        except Exception as exc:  # storage failure — explicit, never silent
            self.storage_error_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.PREPARE,
                AckStatus.STORAGE_ERROR,
                started,
                staged or record,
                self.last_error,
            )

    def commit(
        self, operation_id: str, record: BlackboardRecordV1
    ) -> ReplicaAckV1:
        started = time.perf_counter()
        ctx = self._ctx(operation_id, ReplicaOperationKind.COMMIT, record)
        try:
            if self._health is ReplicaHealth.UNAVAILABLE:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.COMMIT,
                    AckStatus.UNAVAILABLE,
                    started,
                    record,
                    self._unavailable_reason or "replica marked unavailable",
                )
            self.hooks.observe(ctx)
            outcome = self.db.commit_promote(
                record_key=record.record_key,
                record_version=record.record_version,
                record_id=record.record_id,
                operation_id=operation_id,
                committed_at_utc=time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
            )
            if outcome is CommitOutcome.COMMITTED:
                self.committed_count += 1
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.COMMIT,
                    AckStatus.ACK_COMMITTED,
                    started,
                    record,
                    None,
                )
            self.last_error = f"commit could not find matching prepared intent ({outcome.value})"
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.COMMIT,
                AckStatus.STORAGE_ERROR,
                started,
                record,
                self.last_error,
            )
        except HookUnavailableError as exc:
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.COMMIT,
                AckStatus.UNAVAILABLE,
                started,
                record,
                f"hook simulated unavailability: {exc}",
            )
        except Exception as exc:
            self.storage_error_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.COMMIT,
                AckStatus.STORAGE_ERROR,
                started,
                record,
                self.last_error,
            )

    def abort(
        self, operation_id: str, record_key: str, record_version: int
    ) -> ReplicaAckV1:
        started = time.perf_counter()
        try:
            if self._health is ReplicaHealth.UNAVAILABLE:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.ABORT,
                    AckStatus.UNAVAILABLE,
                    started,
                    None,
                    self._unavailable_reason or "replica marked unavailable",
                )
            self.hooks.observe(
                HookContext(
                    hook_point=HookPoint.REPLICA_WRITE,
                    operation_id=operation_id,
                    replica_id=self.replica_id,
                    operation_kind=ReplicaOperationKind.ABORT,
                    record_key=record_key,
                )
            )
            removed = self.db.abort_pending(
                record_key, record_version, operation_id
            )
            self.aborted_count += 1
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.ABORT,
                AckStatus.ABORTED,
                started,
                None,
                None if removed else "no matching pending row (idempotent)",
            )
        except HookUnavailableError as exc:
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.ABORT,
                AckStatus.UNAVAILABLE,
                started,
                None,
                f"hook simulated unavailability: {exc}",
            )
        except Exception as exc:
            self.storage_error_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.ABORT,
                AckStatus.STORAGE_ERROR,
                started,
                None,
                self.last_error,
            )

    # ------------------------------------------------------------------
    # Committed-state reads (never expose pending proposals)
    # ------------------------------------------------------------------

    def get_committed_row(
        self, record_key: str, record_version: int | None = None
    ) -> dict[str, Any] | None:
        if record_version is None:
            return self.db.get_head_row(record_key)
        return self.db.get_committed_row(record_key, record_version)

    def upsert_external(
        self, operation_id: str, record: BlackboardRecordV1
    ) -> ReplicaAckV1:
        """Explicit replication-repair entry point (coordinator-driven)."""
        started = time.perf_counter()
        ctx = self._ctx(operation_id, ReplicaOperationKind.EXTERNAL_UPSERT, record)
        try:
            if self._health is ReplicaHealth.UNAVAILABLE:
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.EXTERNAL_UPSERT,
                    AckStatus.UNAVAILABLE,
                    started,
                    record,
                    self._unavailable_reason or "replica marked unavailable",
                )
            self.hooks.observe(ctx)
            verify_record_integrity(record)
            values = record_to_storage_values(
                record,
                operation_id=operation_id,
                committed_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            values.pop("record_json")
            result = self.db.upsert_committed_external(record_values=values)
            if result.status == "INSERTED":
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.EXTERNAL_UPSERT,
                    AckStatus.ACK_COMMITTED,
                    started,
                    record,
                    "inserted by explicit reconciliation",
                )
            if result.status == "IDENTICAL":
                return self._base_ack(
                    operation_id,
                    ReplicaOperationKind.EXTERNAL_UPSERT,
                    AckStatus.ACK_COMMITTED,
                    started,
                    record,
                    "already identical",
                )
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.EXTERNAL_UPSERT,
                AckStatus.REJECT_CONFLICT,
                started,
                record,
                result.detail or "external upsert refused",
            )
        except HookUnavailableError as exc:
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.EXTERNAL_UPSERT,
                AckStatus.UNAVAILABLE,
                started,
                record,
                f"hook simulated unavailability: {exc}",
            )
        except Exception as exc:
            self.storage_error_count += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return self._base_ack(
                operation_id,
                ReplicaOperationKind.EXTERNAL_UPSERT,
                AckStatus.STORAGE_ERROR,
                started,
                record,
                self.last_error,
            )

    def close(self) -> None:
        self.db.close()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"BlackboardReplica(id={self.replica_id!r}, db={str(self.db.db_path)!r}, "
            f"health={self._health.value})"
        )


def new_operation_id() -> str:
    return uuid.uuid4().hex
