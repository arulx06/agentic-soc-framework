"""Stage-4B Blackboard integration service.

Bridges the verified Stage-4A replicated core into the Stage-3 backend:

* Finding Gateway subscriber -> typed NETWORK_/BEHAVIOR_FINDING_RECORDs
  (accepted findings ONLY; rejected findings can never become accepted
  scientific records here);
* final DEVICE_STATE / DEVICE_ONLY SREP records at replay completion;
* BLACKBOARD_* events published through the SAME Stage-3 envelope and the
  same per-run chronological sequence namespace;
* read wrappers preserving the full Stage-4A read-outcome discipline
  (INSUFFICIENT_QUORUM / INCONSISTENT / UNAVAILABLE stay distinct);
* bounded snapshot/status projections for the API.

Scientific boundary: this service maps and exposes existing backend
values. It computes NO risk, validity, trust or SREP quantities. A
Blackboard failure must never break the scientific path — all public
methods swallow-and-count unexpected errors behind structured results.

Write-outcome fidelity (Stage-4A corrective semantics): COMMITTED requires
>=2 compatible ACK_COMMITTED; exactly 1 is PARTIAL_COMMIT and is emitted
as BLACKBOARD_WRITE_PARTIAL — never as BLACKBOARD_WRITE_COMMITTED.
"""

from __future__ import annotations

import itertools
import threading
import time
import uuid
from typing import Any, Callable

from blackboard import (
    AckStatus,
    BlackboardCoordinator,
    BlackboardRecordDraft,
    BlackboardRecordType,
    BlackboardReplica,
    BlackboardSettings,
    ReadOutcome,
    ReplicaHealth,
    WriteOutcome,
)
from backend.app.config import (
    BLACKBOARD_DEV_WRITE_PAYLOAD_MAX_BYTES,
    BLACKBOARD_SNAPSHOT_MAX_KEYS,
    BLACKBOARD_SNAPSHOT_RECENT_LIMIT,
)
from backend.app.contracts.blackboard_v1 import (
    BLACKBOARD_HEALTH_SCHEMA_VERSION,
    BLACKBOARD_SNAPSHOT_SCHEMA_VERSION,
    BlackboardHealthV1,
    BlackboardSnapshotV1,
    DevWriteRequestV1,
    DevWriteResponseV1,
    RecordSummaryV1,
    ReplicaStatusV1,
)
from backend.app.contracts.events_v1 import ReplayEventType

MAX_PROPOSE_RETRIES = 5


class BlackboardServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


#: WriteOutcome -> terminal BLACKBOARD_* event type. PARTIAL_COMMIT maps
#: to BLACKBOARD_WRITE_PARTIAL — NEVER to BLACKBOARD_WRITE_COMMITTED.
OUTCOME_EVENT: dict[WriteOutcome, ReplayEventType] = {
    WriteOutcome.COMMITTED: ReplayEventType.BLACKBOARD_WRITE_COMMITTED,
    WriteOutcome.PARTIAL_COMMIT: ReplayEventType.BLACKBOARD_WRITE_PARTIAL,
    WriteOutcome.REJECTED_STALE: ReplayEventType.BLACKBOARD_STALE_WRITE,
    WriteOutcome.REJECTED_CONFLICT: ReplayEventType.BLACKBOARD_CONFLICT,
    WriteOutcome.REJECTED_SCHEMA: ReplayEventType.BLACKBOARD_WRITE_REJECTED,
    WriteOutcome.REJECTED_AUTHORIZATION: ReplayEventType.BLACKBOARD_WRITE_REJECTED,
    WriteOutcome.FAILED_QUORUM: ReplayEventType.BLACKBOARD_QUORUM_FAILED,
    WriteOutcome.FAILED_STORAGE: ReplayEventType.BLACKBOARD_STORAGE_FAILED,
}

Publisher = Callable[..., None]


class BlackboardService:
    """Process-level facade over one three-replica coordinator."""

    def __init__(
        self,
        root=None,
        *,
        settings: BlackboardSettings | None = None,
        enabled: bool = True,
    ):
        self.settings = settings or BlackboardSettings()
        self._root = root
        self.enabled = enabled
        self._coordinator: BlackboardCoordinator | None = None
        self._lock = threading.RLock()
        self.publisher: Publisher | None = None
        self.integration_errors = 0
        self.findings_recorded = {"network": 0, "behavior": 0}
        self._last_health: dict[str, str] | None = None
        self._snap_ids = itertools.count(1)

    # ------------------------------------------------------------------
    # Coordinator lifecycle (lazy: importing/wiring must not create files)
    # ------------------------------------------------------------------

    @property
    def coordinator(self) -> BlackboardCoordinator:
        with self._lock:
            if self._coordinator is None:
                root = self._root
                if root is None:
                    from blackboard.settings import RUNTIME_BLACKBOARD_ROOT

                    root = RUNTIME_BLACKBOARD_ROOT
                replicas = [
                    BlackboardReplica(
                        rid,
                        root / f"{rid}.db",
                        max_record_bytes=self.settings.max_record_canonical_bytes,
                        pending_lease_seconds=self.settings.pending_lease_seconds,
                    )
                    for rid in ("replica_a", "replica_b", "replica_c")
                ]
                self._coordinator = BlackboardCoordinator(
                    replicas, settings=self.settings
                )
            return self._coordinator

    def close(self) -> None:
        with self._lock:
            if self._coordinator is not None:
                self._coordinator.close()
                self._coordinator = None

    # ------------------------------------------------------------------
    # Event plumbing
    # ------------------------------------------------------------------

    def _publish_event(
        self,
        event_type: ReplayEventType,
        payload: dict[str, Any],
        *,
        replay_id: str | None = None,
        window_id: int | None = None,
        logical_timestamp: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        if self.publisher is None:
            return
        try:
            self.publisher(
                event_type,
                payload,
                replay_id=replay_id,
                window_id=window_id,
                logical_timestamp=logical_timestamp,
                entity_id=entity_id,
            )
        except Exception:
            # Eventing must never break coordination or science.
            self.integration_errors += 1

    @staticmethod
    def _identity_fields(record) -> dict[str, Any]:
        return {
            "operation_id": None,
            "record_id": record.record_id,
            "record_key": record.record_key,
            "record_type": record.record_type.value,
            "record_version": record.record_version,
            "content_hash": record.content_hash,
            "author_id": record.author_id,
            "source_component": record.source_component,
            "logical_timestamp": record.logical_timestamp,
            "window_id": record.window_id,
        }

    def _phase_listener(self, ctx: dict[str, Any]):
        def listen(phase: str, info: dict[str, Any]) -> None:
            if phase == "PROPOSED":
                payload = {k: v for k, v in info.items()}
                payload["phase"] = "PROPOSED"
                self._publish_event(
                    ReplayEventType.BLACKBOARD_WRITE_PROPOSED,
                    payload,
                    replay_id=ctx.get("replay_id"),
                    window_id=info.get("window_id"),
                    logical_timestamp=info.get("logical_timestamp"),
                    entity_id=ctx.get("entity_id"),
                )
            elif phase == "PREPARED":
                ack = info
                payload = {
                    "operation_id": ack.operation_id,
                    "replica_id": ack.replica_id,
                    "record_id": ack.record_id,
                    "record_key": ack.record_key,
                    "record_version": ack.record_version,
                    "content_hash": ack.content_hash,
                    "ack_status": ack.ack_status.value,
                    "reason": ack.reason,
                    "latency_ms": round(float(ack.latency_ms or 0.0), 3),
                    "current_version_at_replica": ack.current_version_at_replica,
                }
                self._publish_event(
                    ReplayEventType.BLACKBOARD_REPLICA_ACK,
                    payload,
                    replay_id=ctx.get("replay_id"),
                    window_id=ctx.get("window_id"),
                    logical_timestamp=ctx.get("logical_timestamp"),
                    entity_id=ctx.get("entity_id"),
                )

        return listen

    def _emit_terminal(self, result, ctx: dict[str, Any]) -> None:
        event_type = OUTCOME_EVENT[result.outcome]
        durable = [
            a
            for a in result.acks
            if a.ack_status is AckStatus.ACK_COMMITTED
            and a.operation_kind == "COMMIT"
        ]
        payload: dict[str, Any] = {
            "outcome": result.outcome.value,
            "operation_id": result.operation_id,
            "record_id": result.record_id,
            "record_key": result.record_key,
            "record_type": result.record_type,
            "record_version": result.record_version,
            "content_hash": result.content_hash,
            "ack_count": len(durable),
            "required_quorum": self.settings.quorum_size,
            "acknowledgements": [
                {
                    "replica_id": a.replica_id,
                    "operation_kind": a.operation_kind,
                    "ack_status": a.ack_status.value,
                }
                for a in result.acks
            ],
            "author_id": ctx.get("author_id"),
            "source_component": ctx.get("source_component"),
            "logical_timestamp": ctx.get("logical_timestamp"),
            "window_id": ctx.get("window_id"),
            "commit_latency_ms": round(result.duration_ms, 3),
            "reason": result.reason,
            "replica_sync": dict(result.replica_sync),
        }
        if result.outcome is WriteOutcome.COMMITTED:
            payload.pop("reason", None)
        self._publish_event(
            event_type,
            payload,
            replay_id=ctx.get("replay_id"),
            window_id=ctx.get("window_id"),
            logical_timestamp=ctx.get("logical_timestamp"),
            entity_id=ctx.get("entity_id"),
        )
        # Aborts genuinely happened on quorum failure — say so explicitly.
        aborted = [
            a.replica_id
            for a in result.acks
            if a.ack_status is AckStatus.ABORTED and a.operation_kind == "ABORT"
        ]
        if aborted:
            self._publish_event(
                ReplayEventType.BLACKBOARD_WRITE_ABORTED,
                {
                    "operation_id": result.operation_id,
                    "record_key": result.record_key,
                    "aborted_replicas": aborted,
                    "outcome": result.outcome.value,
                },
                replay_id=ctx.get("replay_id"),
                window_id=ctx.get("window_id"),
                entity_id=ctx.get("entity_id"),
            )

    def _watch_replica_health(self, ctx: dict[str, Any] | None = None) -> None:
        try:
            current = {
                rid: info["health"]
                for rid, info in self.coordinator.replica_health().items()
            }
        except Exception:
            self.integration_errors += 1
            return
        if self._last_health is not None and current != self._last_health:
            for rid, health in current.items():
                if self._last_health.get(rid) != health:
                    detail = self.coordinator.replica_health()[rid]
                    self._publish_event(
                        ReplayEventType.BLACKBOARD_REPLICA_STATUS,
                        {
                            "replica_id": rid,
                            "health": health,
                            "storage_error_count": detail["storage_error_count"],
                            "last_error": detail["last_error"],
                            "divergence_history": detail["divergence_history"][-5:],
                        },
                        replay_id=(ctx or {}).get("replay_id"),
                    )
        self._last_health = current

    # ------------------------------------------------------------------
    # Core write helper
    # ------------------------------------------------------------------

    def propose_explicit(
        self,
        draft: BlackboardRecordDraft,
        principal: str,
        *,
        ctx: dict[str, Any] | None = None,
    ):
        """Propose an EXPLICIT record version through the full lifecycle
        (events included). Stale/conflict outcomes are preserved verbatim."""
        ctx = dict(ctx or {})
        listener = (
            self._phase_listener(ctx) if self.publisher is not None else None
        )
        result = self.coordinator.propose(
            draft, principal=principal, phase_listener=listener
        )
        if draft.author_id:
            ctx.update(author_id=draft.author_id, source_component=draft.source_component)
        ctx.setdefault("window_id", draft.window_id)
        ctx.setdefault("logical_timestamp", draft.logical_timestamp)
        self._emit_terminal(result, ctx)
        self._watch_replica_health(ctx)
        return result

    def _propose_next_version(
        self,
        *,
        key: str,
        record_type: BlackboardRecordType,
        author_id: str,
        source_component: str,
        payload: dict[str, Any],
        provenance: dict[str, Any],
        logical_timestamp: str | None,
        window_id: int | None,
        ctx: dict[str, Any],
        principal: str | None = None,
    ):
        coord = self.coordinator
        result = None
        for _ in range(MAX_PROPOSE_RETRIES):
            version = coord.head_version(key) + 1
            draft = BlackboardRecordDraft(
                record_key=key,
                record_type=record_type,
                record_version=version,
                author_id=author_id,
                source_component=source_component,
                payload=payload,
                provenance=provenance,
                logical_timestamp=logical_timestamp,
                window_id=window_id,
            )
            ctx.setdefault("window_id", window_id)
            ctx.setdefault("logical_timestamp", logical_timestamp)
            ctx.update(
                author_id=author_id, source_component=source_component
            )
            result = self.propose_explicit(
                draft, principal or author_id, ctx=ctx
            )
            if result.outcome is not WriteOutcome.REJECTED_STALE:
                break
        return result

    # ------------------------------------------------------------------
    # Finding Gateway adapter (accepted findings only)
    # ------------------------------------------------------------------

    def record_finding(self, finding, *, replay_id: str):
        """Map an ACCEPTED NetworkFinding / BehaviorFinding to a typed
        record. Called exclusively from the Gateway subscription path."""
        if not self.enabled:
            return None
        ftype = getattr(finding, "finding_type", "")
        ctx: dict[str, Any] = {"replay_id": replay_id, "entity_id": finding.entity_id}
        try:
            if ftype == "NetworkFinding":
                key = f"finding/network/{replay_id}/{finding.entity_id}"
                payload = {
                    "evidence_kind": "network",
                    "entity_id": finding.entity_id,
                    "attack_probability": float(finding.attack_probability),
                    "predicted_class": finding.predicted_class,
                    "confidence": float(finding.confidence),
                    "source_model": finding.source_model,
                }
                rtype = BlackboardRecordType.NETWORK_FINDING_RECORD
                author = "network_detector"
                component = "pipeline.network_detector"
            elif ftype == "BehaviorFinding":
                key = f"finding/behavior/{replay_id}/{finding.entity_id}"
                payload = {
                    "evidence_kind": "behavior",
                    "entity_id": finding.entity_id,
                    "deviation_score": float(finding.deviation_score),
                    "profile_type": finding.profile_type,
                    "confidence": float(finding.confidence),
                    "explanation": finding.explanation,
                    "source_model": finding.source_model,
                }
                rtype = BlackboardRecordType.BEHAVIOR_FINDING_RECORD
                author = "behavior_profiler"
                component = "pipeline.behavior_profiler"
            else:
                return None
            result = self._propose_next_version(
                key=key,
                record_type=rtype,
                author_id=author,
                source_component=component,
                payload=payload,
                provenance=dict(getattr(finding, "provenance", {})),
                logical_timestamp=finding.timestamp_utc,
                window_id=int(finding.window_id),
                ctx=ctx,
            )
            if result.outcome in (WriteOutcome.COMMITTED, WriteOutcome.PARTIAL_COMMIT):
                kind = "network" if ftype == "NetworkFinding" else "behavior"
                self.findings_recorded[kind] += 1
            return result
        except Exception as exc:  # never break the scientific path
            self.integration_errors += 1
            self._publish_event(
                ReplayEventType.BLACKBOARD_WRITE_REJECTED,
                {
                    "outcome": "REJECTED_SCHEMA",
                    "reason": f"integration error: {type(exc).__name__}",
                    "record_key": ctx.get("entity_id"),
                    "replay_id": replay_id,
                },
                replay_id=replay_id,
                entity_id=getattr(finding, "entity_id", None),
            )
            return None

    # ------------------------------------------------------------------
    # Final-state records (bounded policy: once per completed replay)
    # ------------------------------------------------------------------

    def record_device_state(self, *, replay_id: str, state_contract) -> None:
        if not self.enabled:
            return
        try:
            payload = {
                "network_observed": state_contract.network_observed,
                "behavior_observed": state_contract.behavior_observed,
                "behavior_supported": state_contract.behavior_supported,
                "network_risk": state_contract.network_risk,
                "behavior_risk": state_contract.behavior_risk,
                "propagated_risk": state_contract.propagated_risk,
                "systemic_risk": state_contract.systemic_risk,
                "is_attacker": state_contract.is_attacker,
                "is_protected_asset": state_contract.is_protected_asset,
                "operational_state": state_contract.operational_state,
                "compromise_state": state_contract.compromise_state,
            }
            self._propose_next_version(
                key=f"device_state/{replay_id}/{state_contract.entity_id}",
                record_type=BlackboardRecordType.DEVICE_STATE_RECORD,
                author_id="device_abm",
                source_component="simulation.abm",
                payload=payload,
                provenance=dict(state_contract.provenance),
                logical_timestamp=state_contract.logical_timestamp,
                window_id=state_contract.window_id,
                ctx={
                    "replay_id": replay_id,
                    "entity_id": state_contract.entity_id,
                },
            )
        except Exception:
            self.integration_errors += 1

    def record_srep_snapshot(self, *, replay_id: str, srep_contract) -> None:
        if not self.enabled:
            return
        try:
            payload = {
                "mode": srep_contract.mode,
                "mode_note": srep_contract.mode_note,
                "defended_blast_radius": srep_contract.defended_blast_radius,
                "compromised_protected_assets": srep_contract.compromised_protected_assets,
                "top_risky_protected_nodes": srep_contract.top_risky_protected_nodes[:10],
                "steps_replayed": srep_contract.steps_replayed,
                "last_window_id": srep_contract.window_id,
            }
            self._propose_next_version(
                key=f"srep_snapshot/{replay_id}",
                record_type=BlackboardRecordType.DEVICE_ONLY_SREP_RECORD,
                author_id="device_srep",
                source_component="srep.device_srep",
                payload=payload,
                provenance={},
                logical_timestamp=None,
                window_id=srep_contract.window_id,
                ctx={"replay_id": replay_id},
            )
        except Exception:
            self.integration_errors += 1

    # ------------------------------------------------------------------
    # Reads (full Stage-4A discipline, with factual READ events)
    # ------------------------------------------------------------------

    def _read_event(self, key: str, result, requested_version: int | None) -> None:
        try:
            inconsistent = result.outcome is ReadOutcome.INCONSISTENT
            obs = [
                {
                    "replica_id": o.replica_id,
                    "responded": o.responded,
                    "found": o.found,
                    "record_version": o.record_version,
                    "content_hash": o.content_hash,
                }
                for o in result.observations
            ]
            self._publish_event(
                ReplayEventType.BLACKBOARD_READ_INCONSISTENT
                if inconsistent
                else ReplayEventType.BLACKBOARD_READ,
                {
                    "read_operation_id": result.read_operation_id,
                    "record_key": key,
                    "requested_version": requested_version,
                    "outcome": result.outcome.value,
                    "observations": obs,
                    "divergent_replicas": list(result.divergent_replicas),
                    "unavailable_replicas": list(result.unavailable_replicas),
                },
            )
        except Exception:
            self.integration_errors += 1

    def read_latest(self, key: str, principal: str):
        result = self.coordinator.read_latest(principal, key)
        if result.outcome is not ReadOutcome.AUTHORIZATION_REJECTED:
            self._read_event(key, result, None)
        self._watch_replica_health()
        return result

    def read_version(self, key: str, version: int, principal: str):
        result = self.coordinator.read_version(principal, key, version)
        if result.outcome is not ReadOutcome.AUTHORIZATION_REJECTED:
            self._read_event(key, result, version)
        self._watch_replica_health()
        return result

    # ------------------------------------------------------------------
    # Restricted development/test writes (SYSTEM_RECORD only)
    # ------------------------------------------------------------------

    def dev_write(self, request: DevWriteRequestV1, principal: str) -> DevWriteResponseV1:
        payload_bytes = len(repr(request.payload))
        if payload_bytes > BLACKBOARD_DEV_WRITE_PAYLOAD_MAX_BYTES:
            raise BlackboardServiceError(
                "payload_too_large",
                f"development-write payload exceeds "
                f"{BLACKBOARD_DEV_WRITE_PAYLOAD_MAX_BYTES} bytes",
                413,
            )
        ctx: dict[str, Any] = {}
        result = self._propose_next_version(
            key=request.record_key,
            record_type=BlackboardRecordType.SYSTEM_RECORD,
            author_id=principal,
            source_component="api.development_write",
            payload=request.payload,
            provenance=request.provenance,
            logical_timestamp=request.logical_timestamp,
            window_id=request.window_id,
            ctx=ctx,
            principal=principal,
        )
        durable = [
            a
            for a in result.acks
            if a.ack_status is AckStatus.ACK_COMMITTED
            and a.operation_kind == "COMMIT"
        ]
        return DevWriteResponseV1(
            schema_version=BLACKBOARD_HEALTH_SCHEMA_VERSION,
            outcome=result.outcome.value,
            operation_id=result.operation_id,
            record_id=result.record_id,
            record_key=result.record_key,
            record_version=result.record_version,
            content_hash=result.content_hash,
            reason=result.reason,
            replica_sync=dict(result.replica_sync),
            durable_commit_ack_count=len(durable),
        )

    # ------------------------------------------------------------------
    # Status / listing / snapshot projections
    # ------------------------------------------------------------------

    def replica_statuses(self) -> list[ReplicaStatusV1]:
        health = self.coordinator.replica_health()
        out = []
        for replica in self.coordinator.replicas:
            rid = replica.replica_id
            info = health[rid]
            out.append(
                ReplicaStatusV1(
                    replica_id=rid,
                    health=info["health"],
                    available=replica.health is not ReplicaHealth.UNAVAILABLE,
                    storage_error_count=info["storage_error_count"],
                    last_error=info["last_error"],
                    committed_record_count=replica.db.count_committed(),
                    pending_record_count=replica.db.count_pending(),
                    divergence_history=list(info["divergence_history"]),
                    head=None,
                )
            )
        return out

    def list_records(
        self,
        *,
        record_type: str | None = None,
        key_prefix: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        view = self.coordinator.committed_view(
            key_prefix=key_prefix,
            limit=self.settings.committed_scan_max_rows,
            offset=0,
        )
        items = view["items"]
        if record_type is not None:
            items = [i for i in items if i["record_type"] == record_type]
        total = len(items)
        page = items[offset : offset + limit]
        return {
            "items": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "unverified_rows_excluded": view["unverified_excluded"],
            "responsive_replicas": view["responsive_replicas"],
            "truncated": view["truncated"],
            "truncated_replicas": view["truncated_replicas"],
            "scanned_rows_per_replica": view["scanned_rows_per_replica"],
            "scan_bounds": view["scan_bounds"],
        }

    def health(self) -> BlackboardHealthV1:
        statuses = self.replica_statuses()
        available = sum(1 for s in statuses if s.available)
        divergent = [s.replica_id for s in statuses if s.health == "DIVERGED"]
        if available == len(statuses) and not divergent:
            status = "ok"
        elif available >= self.settings.quorum_size:
            status = "degraded"
        else:
            status = "offline"
        return BlackboardHealthV1(
            status=status,
            replicas_available=available,
            replicas_total=len(statuses),
            divergent_replicas=divergent,
            counters=self.counters(),
        )

    def counters(self) -> dict[str, int]:
        return self.coordinator.instrumentation.counters()

    def snapshot(self) -> BlackboardSnapshotV1:
        view = self.coordinator.committed_view(
            limit=self.settings.committed_scan_max_rows, offset=0
        )
        items = view["items"]

        # Items arrive ordered by (key asc, version asc): the LAST entry per
        # key is that key's head. Distinct keys are capped deterministically.
        latest_by_key: dict[str, RecordSummaryV1] = {}
        for item in items:
            k = item["record_key"]
            summary = RecordSummaryV1(**item)
            existing = latest_by_key.get(k)
            if existing is not None:
                latest_by_key[k] = summary
            elif len(latest_by_key) < BLACKBOARD_SNAPSHOT_MAX_KEYS:
                latest_by_key[k] = summary

        recent = [
            RecordSummaryV1(**i) for i in items[-BLACKBOARD_SNAPSHOT_RECENT_LIMIT:]
        ]

        snap = BlackboardSnapshotV1(
            snapshot_id=f"bbsnap-{next(self._snap_ids):06d}-{uuid.uuid4().hex[:8]}",
            generated_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            latest_by_key=latest_by_key,
            recent_records=recent,
            replica_statuses=self.replica_statuses(),
            divergent_replicas=[
                s.replica_id for s in self.replica_statuses() if s.health == "DIVERGED"
            ],
            counters=self.counters(),
            latencies=self.coordinator.instrumentation.latencies(),
            recent_rejections=list(
                self.coordinator.instrumentation.recent_rejections()
            ),
            unverified_rows_excluded=view["unverified_excluded"],
            truncated=view["truncated"],
            truncated_replicas=list(view["truncated_replicas"]),
            bounds={
                "snapshot_recent_limit": BLACKBOARD_SNAPSHOT_RECENT_LIMIT,
                "snapshot_max_keys": BLACKBOARD_SNAPSHOT_MAX_KEYS,
                "committed_scan_max_rows": self.settings.committed_scan_max_rows,
                "committed_scan_chunk_size": self.settings.committed_scan_chunk_size,
                "view_complete": not view["truncated"],
            },
            provenance={
                "source_component": "backend.app.services.blackboard_service",
                "note": "operational projection of the Stage-4A replicated core",
            },
        )
        # Defence in depth: the projection itself must pass the firewall.
        from backend.app.contracts.common import assert_no_ground_truth

        assert_no_ground_truth(snap.model_dump(), "blackboard_snapshot")
        return snap

    def restart_persistence_check(self) -> bool:
        """True when the coordinator can be reconstructed against the same
        stores without losing committed state (used by API tests)."""
        root = self._coordinator.replicas[0].db.db_path.parent
        counts_before = [
            r.db.count_committed() for r in self._coordinator.replicas
        ]
        self.close()
        self._root = root
        coord = self.coordinator
        counts_after = [r.db.count_committed() for r in coord.replicas]
        return counts_before == counts_after
