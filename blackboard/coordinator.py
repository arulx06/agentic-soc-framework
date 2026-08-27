"""Three-replica Blackboard coordinator.

Commit policy
-------------
A proposal commits when at least ``quorum_size`` (default 2 of 3)
replicas returned PREPARED acknowledgements that are COMPATIBLE — i.e.
they agree on record_id, record_key, record_version and content_hash.
Incompatible prepared acknowledgements are never combined into a quorum.

THIS IS NOT FULL BYZANTINE FAULT TOLERANCE (no PBFT, no Byzantine
agreement protocol). The mechanism is a quorum-replicated Blackboard with
a two-of-three commit policy under explicit authenticated / fail-stop
assumptions: replicas execute the protocol honestly, may crash, and may
be temporarily unreachable. A partitioned or lying replica majority is
outside the Stage-4A fault model.

Lifecycle per write:

    PROPOSE → authorize → validate/hash → PREPARE on replicas
            → collect ACKs → quorum?
                yes → COMMIT on prepared replicas (misses become explicit
                       DIVERGENT_REQUIRES_RECONCILIATION state)
                no  → ABORT everywhere (prepared state never visible)

Writes within one coordinator instance are serialized by a lifecycle lock
so competing same-key proposals resolve deterministically; independent
coordinator instances over the same stores are still protected by the
per-replica SQLite compare-and-stage transactions.
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from blackboard.authorization import (
    AllowAllDevelopmentAuthorizer,
    AuthzRequest,
    AuthorizationDecision,
    Authorizer,
    BlackboardOperation,
)
from blackboard.contracts import (
    AckStatus,
    BlackboardRecordDraft,
    BlackboardRecordV1,
    ReadOutcome,
    ReadResultV1,
    ReplicaAckV1,
    ReplicaReadObservationV1,
    ReplicationSyncState,
    WriteOutcome,
    WriteResultV1,
    ensure_record_size,
)
from blackboard.hooks import BlackboardFaultHooks, HookContext, HookPoint
from blackboard.instrumentation import BlackboardInstrumentation
from blackboard.replica import (
    BlackboardReplica,
    ReplicaHealth,
    new_operation_id,
    row_to_record,
)
from blackboard.settings import BlackboardSettings

_QUORUM_MET = "QUORUM_MET"
_INSUFFICIENT = "INSUFFICIENT_COMPATIBLE_ACKS"
_INCOMPATIBLE = "INCOMPATIBLE_PREPARED_ACKS"


@dataclass(frozen=True)
class QuorumDecision:
    """Pure evaluation of prepared acknowledgements against the policy."""

    decision: str
    compatible_replica_ids: tuple[str, ...]
    group_record_id: str | None
    group_content_hash: str | None
    group_sizes: tuple[tuple[int, str], ...]


def evaluate_quorum(
    acks: Sequence[ReplicaAckV1], required: int = 2
) -> QuorumDecision:
    """Group prepared acks by full compatibility identity; the largest
    compatible group must reach ``required``. Deterministic tie-breaking:
    groups sort by (-size, content_hash)."""
    groups: dict[tuple[str, str, int, str], list[ReplicaAckV1]] = {}
    for ack in acks:
        if ack.ack_status is not AckStatus.ACK_PREPARED:
            continue
        if (
            ack.record_id is None
            or ack.record_key is None
            or ack.record_version is None
            or ack.content_hash is None
        ):
            continue
        key = (
            ack.record_id,
            ack.record_key,
            ack.record_version,
            ack.content_hash,
        )
        groups.setdefault(key, []).append(ack)

    ordered = sorted(
        groups.items(),
        key=lambda item: (-len(item[1]), item[0][3]),
    )
    sizes = tuple((len(members), key[3]) for key, members in ordered)
    if not ordered:
        return QuorumDecision(_INSUFFICIENT, (), None, None, sizes)
    best_key, best_members = ordered[0]
    if len(best_members) >= required:
        return QuorumDecision(
            _QUORUM_MET,
            tuple(a.replica_id for a in best_members),
            best_key[0],
            best_key[3],
            sizes,
        )
    if len(ordered) > 1:
        return QuorumDecision(_INCOMPATIBLE, (), None, None, sizes)
    return QuorumDecision(_INSUFFICIENT, (), None, None, sizes)


@dataclass(frozen=True)
class _Observation:
    replica_id: str
    responded: bool
    found: bool = False
    record_version: int | None = None
    content_hash: str | None = None
    record: BlackboardRecordV1 | None = None
    detail: str | None = None


class BlackboardCoordinator:
    """Coordinates writes and consistent reads across exactly three
    independently persisted replicas."""

    def __init__(
        self,
        replicas: Sequence[BlackboardReplica],
        *,
        authorizer: Authorizer | None = None,
        hooks: BlackboardFaultHooks | None = None,
        settings: BlackboardSettings | None = None,
        instrumentation: BlackboardInstrumentation | None = None,
    ):
        if len(replicas) != 3:
            raise ValueError(
                f"the Blackboard requires exactly three replicas, got {len(replicas)}"
            )
        ids = [r.replica_id for r in replicas]
        if len(set(ids)) != len(ids):
            raise ValueError(f"replica identities must be unique, got {ids}")
        self._replicas: tuple[BlackboardReplica, ...] = tuple(replicas)
        self.replica_ids: tuple[str, ...] = tuple(ids)
        self.authorizer: Authorizer = (
            authorizer if authorizer is not None else AllowAllDevelopmentAuthorizer()
        )
        self.hooks = hooks if hooks is not None else BlackboardFaultHooks()
        self.settings = settings if settings is not None else BlackboardSettings()
        self.instrumentation = (
            instrumentation
            if instrumentation is not None
            else BlackboardInstrumentation(
                latency_samples_limit=self.settings.latency_samples_limit,
                recent_operations_limit=self.settings.recent_operations_limit,
                recent_rejections_limit=self.settings.recent_rejections_limit,
            )
        )
        self._write_lock = threading.RLock()
        self._op_counter = itertools.count(1)

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------

    @property
    def replicas(self) -> tuple[BlackboardReplica, ...]:
        return self._replicas

    def _replica(self, replica_id: str) -> BlackboardReplica:
        for r in self._replicas:
            if r.replica_id == replica_id:
                return r
        raise KeyError(replica_id)

    def _new_op_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._op_counter):06d}-{new_operation_id()[:12]}"

    def _notify_listener(
        self, phase_listener, phase: str, info: Any
    ) -> None:
        """Observability seam: a failing listener is counted and isolated.

        It can NEVER change protocol behaviour — prepare semantics, commit
        quorum, PARTIAL_COMMIT handling and persistence are identical with
        or without (or with a crashing) listener.
        """
        if phase_listener is None:
            return
        try:
            phase_listener(phase, info)
        except Exception:
            self.instrumentation.increment("listener_errors")

    def _authorize(
        self,
        principal: str,
        operation: BlackboardOperation,
        record_type: str | None,
        record_key: str | None,
    ) -> AuthorizationDecision:
        return self.authorizer.decide(
            AuthzRequest(
                principal=principal,
                operation=operation,
                record_type=record_type,
                record_key=record_key,
            )
        )

    @staticmethod
    def _now_utc() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _write_result(
        self,
        *,
        operation_id: str,
        outcome: WriteOutcome,
        principal: str,
        started_at: str,
        started_perf: float,
        reason: str | None,
        record: BlackboardRecordV1 | None = None,
        acks: Sequence[ReplicaAckV1] = (),
        replica_sync: Mapping[str, str] | None = None,
    ) -> WriteResultV1:
        result = WriteResultV1(
            operation_id=operation_id,
            outcome=outcome,
            reason=reason,
            principal=principal,
            record_id=None if record is None else record.record_id,
            record_key=None if record is None else record.record_key,
            record_type=None if record is None else record.record_type.value,
            record_version=None if record is None else record.record_version,
            content_hash=None if record is None else record.content_hash,
            acks=tuple(acks),
            replica_sync=dict(replica_sync or {}),
            started_at_utc=started_at,
            completed_at_utc=self._now_utc(),
            duration_ms=(time.perf_counter() - started_perf) * 1000.0,
        )
        self.instrumentation.record_write_result(result)
        return result

    def _observe_replicas_latency(self, acks: Sequence[ReplicaAckV1]) -> None:
        healthy = {
            AckStatus.ACK_PREPARED,
            AckStatus.ACK_COMMITTED,
            AckStatus.ABORTED,
        }
        for ack in acks:
            ok = ack.ack_status in healthy
            kind = ack.operation_kind.lower()
            self.instrumentation.observe_replica_latency(
                ack.replica_id, kind, ok, float(ack.latency_ms or 0.0)
            )

    # ------------------------------------------------------------------
    # WRITE path
    # ------------------------------------------------------------------

    def propose(
        self,
        draft: BlackboardRecordDraft | BlackboardRecordV1,
        principal: str,
        *,
        phase_listener: Any | None = None,
    ) -> WriteResultV1:
        """Run the full write lifecycle.

        ``phase_listener(phase, info)`` is an OPTIONAL observation hook for
        integration layers: called once with ``("PROPOSED", identity-dict)``
        before dispatch and once per replica with ``("PREPARED", ack)``.
        It never alters protocol behaviour and defaults to None.
        """
        operation_id = self._new_op_id("bbw")
        started_at = self._now_utc()
        started_perf = time.perf_counter()
        self.instrumentation.increment("writes_started")

        if not isinstance(principal, str) or not principal.strip():
            return self._write_result(
                operation_id=operation_id,
                outcome=WriteOutcome.REJECTED_AUTHORIZATION,
                principal=str(principal),
                started_at=started_at,
                started_perf=started_perf,
                reason="principal must be a non-empty string",
            )

        # -- schema validation & integrity derivation --------------------
        try:
            if isinstance(draft, BlackboardRecordDraft):
                record = draft.to_record()
            elif isinstance(draft, BlackboardRecordV1):
                record = draft
            else:
                raise TypeError("draft must be BlackboardRecordDraft or record")
            ensure_record_size(record, self.settings.max_record_canonical_bytes)
        except Exception as exc:
            return self._write_result(
                operation_id=operation_id,
                outcome=WriteOutcome.REJECTED_SCHEMA,
                principal=principal,
                started_at=started_at,
                started_perf=started_perf,
                reason=f"{type(exc).__name__}: {exc}",
            )

        decision = self._authorize(
            principal,
            BlackboardOperation.WRITE,
            record.record_type.value,
            record.record_key,
        )
        if not decision.allowed:
            return self._write_result(
                operation_id=operation_id,
                outcome=WriteOutcome.REJECTED_AUTHORIZATION,
                principal=principal,
                started_at=started_at,
                started_perf=started_perf,
                reason=f"{decision.policy_id}: {decision.reason}",
                record=record,
            )

        self.hooks.observe(
            HookContext(
                hook_point=HookPoint.BLACKBOARD_WRITE,
                operation_id=operation_id,
                principal=principal,
                record_key=record.record_key,
                record_id=record.record_id,
            )
        )

        with self._write_lock:
            self._notify_listener(
                phase_listener,
                "PROPOSED",
                {
                    "operation_id": operation_id,
                    "record_id": record.record_id,
                    "record_key": record.record_key,
                    "record_type": record.record_type.value,
                    "record_version": record.record_version,
                    "content_hash": record.content_hash,
                    "author_id": record.author_id,
                    "source_component": record.source_component,
                    "logical_timestamp": record.logical_timestamp,
                    "window_id": record.window_id,
                },
            )
            prepare_acks: list[ReplicaAckV1] = []
            for replica in self._replicas:
                ack = replica.prepare(operation_id, record)
                prepare_acks.append(ack)
                self._notify_listener(phase_listener, "PREPARED", ack)
            self._observe_replicas_latency(prepare_acks)

            prepared_acks = [
                a for a in prepare_acks if a.ack_status is AckStatus.ACK_PREPARED
            ]

            if not prepared_acks:
                outcome, reason = self._classify_total_rejection(prepare_acks)
                sync = {
                    r.replica_id: ReplicationSyncState.NOT_PREPARED.value
                    for r in self._replicas
                }
                return self._write_result(
                    operation_id=operation_id,
                    outcome=outcome,
                    principal=principal,
                    started_at=started_at,
                    started_perf=started_perf,
                    reason=reason,
                    record=record,
                    acks=prepare_acks,
                    replica_sync=sync,
                )

            quorum = evaluate_quorum(prepare_acks, self.settings.quorum_size)
            if quorum.decision != _QUORUM_MET:
                abort_acks = self._abort_prepared(
                    operation_id, record, prepare_acks
                )
                self.instrumentation.increment("aborts_issued")
                self._observe_replicas_latency(abort_acks)
                sync = self._sync_map_after_failure(prepare_acks + abort_acks)
                return self._write_result(
                    operation_id=operation_id,
                    outcome=WriteOutcome.FAILED_QUORUM,
                    principal=principal,
                    started_at=started_at,
                    started_perf=started_perf,
                    reason=(
                        "incompatible prepared acknowledgements cannot form a "
                        "quorum"
                        if quorum.decision == _INCOMPATIBLE
                        else "insufficient compatible prepared acknowledgements"
                    ),
                    record=record,
                    acks=prepare_acks + abort_acks,
                    replica_sync=sync,
                )

            # COMMIT phase — promote the staged intent on every member of
            # the compatible group; prepared-but-INCOMPATIBLE losers get an
            # explicit abort so no divergent staging survives.
            winning_ids = set(quorum.compatible_replica_ids)
            commit_acks: list[ReplicaAckV1] = []
            loser_abort_acks: list[ReplicaAckV1] = []
            replica_sync: dict[str, str] = {}
            for ack in prepare_acks:
                replica = self._replica(ack.replica_id)
                if ack.ack_status is not AckStatus.ACK_PREPARED:
                    replica_sync[ack.replica_id] = (
                        ReplicationSyncState.UNAVAILABLE.value
                        if ack.ack_status is AckStatus.UNAVAILABLE
                        else ReplicationSyncState.NOT_PREPARED.value
                    )
                    continue
                if ack.replica_id not in winning_ids:
                    l_ack = replica.abort(
                        operation_id, record.record_key, record.record_version
                    )
                    loser_abort_acks.append(l_ack)
                    replica_sync[ack.replica_id] = (
                        ReplicationSyncState.ABORTED.value
                        if l_ack.ack_status is AckStatus.ABORTED
                        else ReplicationSyncState.UNAVAILABLE.value
                    )
                    continue
                c_ack = replica.commit(operation_id, record)
                commit_acks.append(c_ack)
                if c_ack.ack_status is AckStatus.ACK_COMMITTED:
                    replica_sync[ack.replica_id] = ReplicationSyncState.SYNCED.value
                else:
                    replica_sync[ack.replica_id] = (
                        ReplicationSyncState.DIVERGENT_REQUIRES_RECONCILIATION.value
                    )
                    replica.mark_diverged(
                        f"missed commit op={operation_id} "
                        f"key={record.record_key} v={record.record_version} "
                        f"status={c_ack.ack_status.value}"
                    )
            self._observe_replicas_latency(commit_acks)
            self._observe_replicas_latency(loser_abort_acks)
            self.instrumentation.increment("aborts_issued")

            # Non-prepared replicas get an explicit best-effort abort so no
            # staging survives a successful global commit.
            cleanup_acks = self._abort_unprepared(operation_id, prepare_acks)
            self._observe_replicas_latency(cleanup_acks)

            # -----------------------------------------------------------------
            # Final outcome requires a COMMITTED quorum, not just the
            # prepared one: entering the commit phase is permission, not
            # durability proof. Every successful commit promoted the same
            # (key, version, record_id) intent, so counting ACK_COMMITTED
            # acknowledgements carrying this record's identity equals
            # counting compatible ones.
            # -----------------------------------------------------------------
            durable_acks = [
                c
                for c in commit_acks
                if c.ack_status is AckStatus.ACK_COMMITTED
                and c.content_hash == record.content_hash
                and c.record_id == record.record_id
            ]
            n_durable = len(durable_acks)
            required = self.settings.quorum_size
            if n_durable >= required:
                outcome = WriteOutcome.COMMITTED
                reason = None
            elif n_durable == 1:
                # One replica holds durable committed data while the rest of
                # the prepared group failed: report indeterminate partial
                # state honestly; never erase the committed replica here.
                outcome = WriteOutcome.PARTIAL_COMMIT
                committed_replicas = [a.replica_id for a in durable_acks]
                failed_replicas = [
                    a.replica_id
                    for a in prepare_acks
                    if a.replica_id in winning_ids
                    and a.replica_id not in committed_replicas
                ]
                reason = (
                    f"partial/indeterminate commit: {n_durable} of {required} "
                    f"required commit acknowledgements succeeded "
                    f"(committed={committed_replicas}, "
                    f"failed={failed_replicas}); state requires reconciliation"
                )
            else:
                outcome = WriteOutcome.FAILED_STORAGE
                reason = (
                    "quorum prepared but zero replicas completed the commit phase"
                )
            return self._write_result(
                operation_id=operation_id,
                outcome=outcome,
                principal=principal,
                started_at=started_at,
                started_perf=started_perf,
                reason=reason,
                record=record,
                acks=prepare_acks + commit_acks + loser_abort_acks + cleanup_acks,
                replica_sync=replica_sync,
            )

    def _classify_total_rejection(
        self, prepare_acks: Sequence[ReplicaAckV1]
    ) -> tuple[WriteOutcome, str]:
        statuses = {a.ack_status for a in prepare_acks}
        terminal = statuses - {AckStatus.UNAVAILABLE, AckStatus.STORAGE_ERROR}
        if not terminal:
            return (
                WriteOutcome.FAILED_QUORUM,
                "no responsive replica could prepare the proposal",
            )
        terminal_acks = [
            a
            for a in prepare_acks
            if a.ack_status in terminal
        ]
        if len(terminal) == 1:
            status = next(iter(terminal))
            mapping = {
                AckStatus.REJECT_STALE: WriteOutcome.REJECTED_STALE,
                AckStatus.REJECT_CONFLICT: WriteOutcome.REJECTED_CONFLICT,
                AckStatus.REJECT_SCHEMA: WriteOutcome.REJECTED_SCHEMA,
                AckStatus.REJECT_INTEGRITY: WriteOutcome.REJECTED_SCHEMA,
                AckStatus.REJECT_AUTHORIZATION: WriteOutcome.REJECTED_AUTHORIZATION,
            }
            if status is AckStatus.REJECT_STALE:
                current = max(
                    (
                        a.current_version_at_replica or 0
                        for a in prepare_acks
                        if a.ack_status is AckStatus.REJECT_STALE
                    ),
                    default=None,
                )
                return (
                    WriteOutcome.REJECTED_STALE,
                    f"proposal is stale; current committed version is {current}",
                )
            if status in mapping:
                detail = next((a.reason for a in terminal_acks if a.reason), status.value)
                return mapping[status], f"{status.value}: {detail}"
        return (
            WriteOutcome.FAILED_QUORUM,
            f"mixed rejection statuses across replicas: "
            f"{sorted(s.value for s in statuses)}",
        )

    def _abort_prepared(
        self,
        operation_id: str,
        record: BlackboardRecordV1,
        prepare_acks: Sequence[ReplicaAckV1],
    ) -> list[ReplicaAckV1]:
        """Abort staging on exactly the replicas that acknowledged PREPARED
        (an UNAVAILABLE or rejecting replica staged nothing)."""
        acks = []
        for ack in prepare_acks:
            if ack.ack_status is not AckStatus.ACK_PREPARED:
                continue
            replica = self._replica(ack.replica_id)
            acks.append(
                replica.abort(
                    operation_id, record.record_key, record.record_version
                )
            )
        return acks

    def _abort_unprepared(
        self, operation_id: str, prepare_acks: Sequence[ReplicaAckV1]
    ) -> list[ReplicaAckV1]:
        acks = []
        for ack in prepare_acks:
            if ack.ack_status is AckStatus.ACK_PREPARED:
                continue
            replica = self._replica(ack.replica_id)
            if ack.record_key is None or ack.record_version is None:
                continue
            acks.append(
                replica.abort(
                    operation_id, ack.record_key, ack.record_version
                )
            )
        return acks

    def _sync_map_after_failure(
        self, all_acks: Sequence[ReplicaAckV1]
    ) -> dict[str, str]:
        sync: dict[str, str] = {}
        for ack in all_acks:
            if ack.ack_status is AckStatus.ABORTED:
                sync.setdefault(ack.replica_id, ReplicationSyncState.ABORTED.value)
            elif ack.ack_status is AckStatus.UNAVAILABLE:
                sync.setdefault(
                    ack.replica_id, ReplicationSyncState.UNAVAILABLE.value
                )
            else:
                sync.setdefault(
                    ack.replica_id, ReplicationSyncState.NOT_PREPARED.value
                )
        return sync

    # ------------------------------------------------------------------
    # READ path
    # ------------------------------------------------------------------

    def read_latest(self, principal: str, record_key: str) -> ReadResultV1:
        return self._read(principal, record_key, None)

    def read_version(
        self, principal: str, record_key: str, record_version: int
    ) -> ReadResultV1:
        return self._read(principal, record_key, record_version)

    def _read(
        self, principal: str, record_key: str, record_version: int | None
    ) -> ReadResultV1:
        started_perf = time.perf_counter()
        read_op = self._new_op_id("bbr")
        self.instrumentation.increment("reads_started")

        def finish(outcome: ReadOutcome, **kwargs: Any) -> ReadResultV1:
            result = ReadResultV1(
                read_operation_id=read_op,
                principal=principal,
                record_key=record_key,
                requested_version=record_version,
                outcome=outcome,
                duration_ms=(time.perf_counter() - started_perf) * 1000.0,
                **kwargs,
            )
            self.instrumentation.record_read(outcome, result.duration_ms)
            return result

        if not isinstance(principal, str) or not principal.strip():
            return finish(
                ReadOutcome.AUTHORIZATION_REJECTED,
                reason="principal must be a non-empty string",
            )
        decision = self._authorize(principal, BlackboardOperation.READ, None, record_key)
        if not decision.allowed:
            return finish(
                ReadOutcome.AUTHORIZATION_REJECTED,
                reason=f"{decision.policy_id}: {decision.reason}",
            )

        self.hooks.observe(
            HookContext(
                hook_point=HookPoint.BLACKBOARD_READ,
                operation_id=read_op,
                principal=principal,
                record_key=record_key,
            )
        )

        observations: list[_Observation] = []
        public_obs: list[ReplicaReadObservationV1] = []
        for replica in self._replicas:
            obs = self._observe_replica(replica, record_key, record_version, read_op)
            observations.append(obs)
            public_obs.append(
                ReplicaReadObservationV1(
                    replica_id=obs.replica_id,
                    responded=obs.responded,
                    found=obs.found,
                    record_version=obs.record_version,
                    content_hash=obs.content_hash,
                    detail=obs.detail,
                )
            )

        responses = [o for o in observations if o.responded]
        present = [o for o in responses if o.found]
        absent = [o for o in responses if not o.found]

        unavailable = tuple(o.replica_id for o in observations if not o.responded)
        required = self.settings.quorum_size

        def no_authority(
            outcome: ReadOutcome, reason: str, divergent: tuple[str, ...] = ()
        ):
            """Few-responder and disagreement results never return a record
            as authoritative Blackboard state."""
            return finish(
                outcome,
                observations=tuple(public_obs),
                divergent_replicas=divergent,
                unavailable_replicas=unavailable,
                reason=reason,
            )

        if not responses:
            return no_authority(ReadOutcome.UNAVAILABLE, "no replica responded")

        if not present:
            # Absence obeys the same quorum discipline as presence.
            if len(responses) >= required:
                degraded_note = (
                    None
                    if len(responses) == len(self._replicas)
                    else "absence confirmed by responding majority only; "
                    "some replicas unavailable"
                )
                return finish(
                    ReadOutcome.NOT_FOUND,
                    observations=tuple(public_obs),
                    unavailable_replicas=unavailable,
                    reason=degraded_note,
                )
            return no_authority(
                ReadOutcome.INSUFFICIENT_QUORUM,
                f"absence confirmed by only {len(responses)} of {required} "
                f"required replicas",
            )

        groups: dict[tuple[int, str], list[_Observation]] = {}
        for o in present:
            groups.setdefault((o.record_version or 0, o.content_hash or ""), []).append(o)
        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][1]))
        best_group = ordered[0][1]
        best_key = ordered[0][0]
        best_size = len(best_group)

        # Observed disagreement set (non-best holders plus responders with
        # no value). Health is mutated ONLY on conclusive degraded outcomes.
        divergent_ids = [
            o.replica_id
            for o in present
            if (o.record_version or 0, o.content_hash or "") != best_key
        ] + [o.replica_id for o in absent]
        for o in observations:
            if o.detail and o.detail.startswith("integrity"):
                self._replica(o.replica_id).mark_diverged(
                    f"stored-record integrity failure op={read_op}: {o.detail}"
                )

        if len(responses) < required:
            return no_authority(
                ReadOutcome.INSUFFICIENT_QUORUM,
                f"only {len(responses)} of {required} required replicas "
                f"responded; a value cannot be confirmed",
                divergent=tuple(divergent_ids),
            )

        if (
            best_size == len(responses)
            and len(responses) == len(self._replicas)
        ):
            return finish(
                ReadOutcome.CONSISTENT,
                record=best_group[0].record,
                observations=tuple(public_obs),
            )

        if best_size >= required:
            for rid in divergent_ids:
                replica = self._replica(rid)
                obs = next(x for x in observations if x.replica_id == rid)
                if obs.found:
                    replica.mark_diverged(
                        f"read divergence op={read_op} key={record_key} "
                        f"observed=v{obs.record_version}/{obs.content_hash} "
                        f"majority=v{best_key[0]}/{best_key[1]}"
                    )
                else:
                    replica.mark_diverged(
                        f"read lag op={read_op} key={record_key}: no committed "
                        f"value while majority holds v{best_key[0]}/{best_key[1]}"
                    )
            return finish(
                ReadOutcome.DEGRADED_CONSISTENT,
                record=best_group[0].record,
                observations=tuple(public_obs),
                divergent_replicas=tuple(divergent_ids),
                unavailable_replicas=unavailable,
                reason="compatible majority returned; some replicas "
                "unavailable/divergent/lagging",
            )

        return no_authority(
            ReadOutcome.INCONSISTENT,
            "no compatible majority across replicas",
            divergent=tuple(divergent_ids),
        )

    def _observe_replica(
        self,
        replica: BlackboardReplica,
        record_key: str,
        record_version: int | None,
        read_op: str,
    ) -> _Observation:
        if replica.health is ReplicaHealth.UNAVAILABLE:
            return _Observation(
                replica_id=replica.replica_id,
                responded=False,
                detail=replica.unavailable_reason or "marked unavailable",
            )
        try:
            row = replica.get_committed_row(record_key, record_version)
        except Exception as exc:
            return _Observation(
                replica_id=replica.replica_id,
                responded=False,
                detail=f"{type(exc).__name__}: {exc}",
            )
        if row is None:
            return _Observation(
                replica_id=replica.replica_id,
                responded=True,
                found=False,
            )
        try:
            record = row_to_record(row)
        except Exception as exc:
            return _Observation(
                replica_id=replica.replica_id,
                responded=True,
                found=False,
                detail=f"integrity: stored record failed verification ({exc})",
            )
        return _Observation(
            replica_id=replica.replica_id,
            responded=True,
            found=True,
            record_version=record.record_version,
            content_hash=record.content_hash,
            record=record,
        )

    # ------------------------------------------------------------------
    # Explicit replication repair (operational, never automatic)
    # ------------------------------------------------------------------

    def resync_replicas_from_majority(
        self,
        principal: str,
        record_key: str,
        replica_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Bring lagging/divergent replicas back to the compatible majority
        for ONE record key. Explicit, operator-driven, tested — never run
        automatically by reads."""
        started_perf = time.perf_counter()
        repair_op = self._new_op_id("bbs")

        decision = self._authorize(
            principal, BlackboardOperation.WRITE, None, record_key
        )
        if not decision.allowed:
            return {
                "repair_operation_id": repair_op,
                "status": "AUTHORIZATION_REJECTED",
                "reason": f"{decision.policy_id}: {decision.reason}",
                "duration_ms": (time.perf_counter() - started_perf) * 1000.0,
            }

        probe = self._read_internal_majority(record_key)
        if probe is None:
            return {
                "repair_operation_id": repair_op,
                "status": "NO_MAJORITY_SOURCE",
                "reason": "no compatible majority exists to repair from",
                "duration_ms": (time.perf_counter() - started_perf) * 1000.0,
            }

        targets = (
            [self._replica(rid) for rid in replica_ids]
            if replica_ids is not None
            else list(self._replicas)
        )
        report: dict[str, str] = {}
        applied = refused = 0
        for replica in targets:
            ack = replica.upsert_external(repair_op, probe)

            def _head_row():
                try:
                    return replica.get_committed_row(record_key)
                except Exception:
                    return None

            head_row = _head_row()
            aligned = (
                head_row is not None
                and head_row["record_id"] == probe.record_id
            )
            if ack.ack_status is AckStatus.ACK_COMMITTED and aligned:
                # Aligned on the MAJORITY HEAD — not merely on one slot.
                # A replica whose head legitimately holds newer committed
                # data keeps it: never erase commits for symmetry.
                replica.clear_divergence()
                report[replica.replica_id] = f"REPAIRED ({ack.reason})"
                applied += 1
            elif aligned and ack.ack_status is AckStatus.ACK_COMMITTED:
                replica.clear_divergence()
                report[replica.replica_id] = "REPAIRED (already identical)"
                applied += 1
            else:
                if (
                    head_row is not None
                    and head_row["record_version"] > probe.record_version
                ):
                    replica.mark_diverged(
                        f"resync op={repair_op} key={record_key}: head "
                        f"v{head_row['record_version']} ahead of majority head "
                        f"v{probe.record_version}; committed data preserved"
                    )
                    report[replica.replica_id] = (
                        "PRESERVED_DIVERGENT_HEAD "
                        f"(local head v{head_row['record_version']} kept)"
                    )
                else:
                    report[replica.replica_id] = (
                        f"REFUSED ({ack.ack_status.value}: {ack.reason})"
                    )
                refused += 1
        if applied:
            self.instrumentation.increment("resyncs_applied")
        if refused:
            self.instrumentation.increment("resyncs_refused")
        return {
            "repair_operation_id": repair_op,
            "status": "REPAIRED" if applied and not refused else "PARTIAL" if applied else "REFUSED",
            "source": {
                "record_id": probe.record_id,
                "version": probe.record_version,
                "content_hash": probe.content_hash,
            },
            "replicas": report,
            "duration_ms": (time.perf_counter() - started_perf) * 1000.0,
        }

    def _read_internal_majority(self, record_key: str) -> BlackboardRecordV1 | None:
        observations = [
            self._observe_replica(r, record_key, None, "internal-majority-probe")
            for r in self._replicas
        ]
        present = [o for o in observations if o.responded and o.found]
        groups: dict[tuple[int, str], list[_Observation]] = {}
        for o in present:
            groups.setdefault(
                (o.record_version or 0, o.content_hash or ""), []
            ).append(o)
        if not groups:
            return None
        required = self.settings.quorum_size
        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][1]))
        best_group = ordered[0][1]
        if len(best_group) < required:
            return None
        return best_group[0].record

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------

    def replica_health(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in self._replicas:
            out[r.replica_id] = {
                "health": r.health.value,
                "unavailable_reason": r.unavailable_reason,
                "storage_error_count": r.storage_error_count,
                "last_error": r.last_error,
                "divergence_history": list(r.divergence_history),
            }
        return out

    # ------------------------------------------------------------------
    # Bounded committed-state projection (Stage-4B listing/snapshot support)
    # ------------------------------------------------------------------

    def head_version(self, record_key: str) -> int:
        """Operational head hint from the first responsive replica (0 if
        none). Safety never depends on this hint — the per-replica CAS
        governs correctness; stale callers are simply rejected."""
        for replica in self._replicas:
            if replica.health is ReplicaHealth.UNAVAILABLE:
                continue
            row = replica.get_committed_row(record_key)
            if row is not None:
                return int(row["record_version"])
            return 0
        return 0

    def committed_view(
        self,
        *,
        key_prefix: str | None = None,
        limit: int = 100,
        offset: int = 0,
        scan_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Quorum-filtered merged view of committed rows across healthy
        replicas.

        Scanning is CHUNKED per replica (bounded memory) up to an explicit,
        configurable bound (``scan_max_rows`` or
        ``settings.committed_scan_max_rows``). If a responsive replica still
        has rows beyond the scanned scope the result says so via
        ``truncated``/``truncated_replicas`` — a truncated view is never
        represented as a complete total. Rows supported by fewer than
        quorum_size replicas are excluded and counted honestly instead of
        silently served.
        """
        if scan_max_rows is None:
            scan_max_rows = self.settings.committed_scan_max_rows
        chunk_size = self.settings.committed_scan_chunk_size

        per_replica: dict[str, list[dict[str, Any]]] = {}
        scanned_rows: dict[str, int] = {}
        truncated_replicas: list[str] = []
        for replica in self._replicas:
            if replica.health is ReplicaHealth.UNAVAILABLE:
                continue
            rows: list[dict[str, Any]] = []
            offset_in_replica = 0
            exhausted = False
            while len(rows) < scan_max_rows:
                fetch_limit = min(chunk_size, scan_max_rows - len(rows))
                chunk = replica.db.iter_committed_rows(
                    key_prefix=key_prefix,
                    limit=fetch_limit,
                    offset=offset_in_replica,
                )
                rows.extend(chunk)
                offset_in_replica += len(chunk)
                if len(chunk) < fetch_limit:
                    exhausted = True
                    break
            hit_bound = not exhausted
            # Disambiguate "stopped exactly at the bound" from "more remain".
            if hit_bound:
                probe = replica.db.iter_committed_rows(
                    key_prefix=key_prefix, limit=1, offset=offset_in_replica
                )
                if probe:
                    truncated_replicas.append(replica.replica_id)
            scanned_rows[replica.replica_id] = len(rows)
            per_replica[replica.replica_id] = rows

        support: dict[tuple[str, int, str], set[str]] = {}
        sample: dict[tuple[str, int, str], dict[str, Any]] = {}
        for rid, rows in per_replica.items():
            for row in rows:
                k = (
                    row["record_key"],
                    int(row["record_version"]),
                    row["record_id"],
                )
                support.setdefault(k, set()).add(rid)
                sample.setdefault(k, row)

        verified = {
            k: members
            for k, members in support.items()
            if len(members) >= self.settings.quorum_size
        }
        unverified_excluded = len(support) - len(verified)

        ordered_keys = sorted(verified.keys())
        total = len(ordered_keys)
        page = ordered_keys[offset : offset + limit]

        items = []
        for k in page:
            row = sample[k]
            items.append(
                {
                    "record_key": row["record_key"],
                    "record_type": row["record_type"],
                    "record_version": int(row["record_version"]),
                    "record_id": row["record_id"],
                    "content_hash": row["content_hash"],
                    "author_id": row["author_id"],
                    "source_component": row["source_component"],
                    "logical_timestamp": row.get("logical_timestamp"),
                    "window_id": row.get("window_id"),
                    "supporting_replicas": sorted(verified[k]),
                }
            )
        return {
            "items": items,
            "total_verified": total,
            "unverified_excluded": unverified_excluded,
            "responsive_replicas": sorted(per_replica.keys()),
            "truncated": bool(truncated_replicas),
            "truncated_replicas": truncated_replicas,
            "scanned_rows_per_replica": scanned_rows,
            "scan_bounds": {
                "max_rows_per_replica": scan_max_rows,
                "chunk_size": chunk_size,
            },
        }

    def close(self) -> None:
        for r in self._replicas:
            r.close()
