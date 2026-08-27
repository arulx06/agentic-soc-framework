"""Bounded core instrumentation for Stage 4A.

These are implementation instrumentation values (latencies and operation
counts) — explicitly NOT final research metrics, and never benchmarked
against the full dataset.

All retained history is bounded:

* latency series are ``deque(maxlen=latency_samples_limit)``;
* recent global operations live in a ring of ``recent_operations_limit``
  trimmed summary entries (never full payloads);
* recent rejections live in a ring of ``recent_rejections_limit`` entries.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from blackboard.contracts import (
    AckStatus,
    ReadOutcome,
    WriteOutcome,
    WriteResultV1,
)


class LatencySeries:
    """Bounded latency sample series with percentile snapshots."""

    def __init__(self, limit: int):
        self._samples: deque[float] = deque(maxlen=limit)
        self._lock = threading.Lock()

    def record(self, ms: float) -> None:
        with self._lock:
            self._samples.append(float(ms))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            samples = sorted(self._samples)
        if not samples:
            return {"count": 0}
        count = len(samples)

        def pct(p: float) -> float:
            idx = min(count - 1, max(0, int(round(p * (count - 1)))))
            return round(samples[idx], 3)

        mean = sum(samples) / count
        return {
            "count": count,
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "max_ms": round(samples[-1], 3),
            "mean_ms": round(mean, 3),
        }


class BlackboardInstrumentation:
    """Counters + bounded latency/history rings for the coordinator."""

    COUNTER_KEYS = (
        "writes_started",
        "committed",
        "committed_with_divergence",
        "partial_commit",
        "rejected_stale",
        "rejected_conflict",
        "rejected_schema",
        "rejected_integrity",
        "rejected_authorization",
        "failed_quorum",
        "failed_storage",
        "listener_errors",
        "aborts_issued",
        "resyncs_applied",
        "resyncs_refused",
        "reads_started",
        "read_consistent",
        "read_degraded_consistent",
        "read_not_found",
        "read_insufficient_quorum",
        "read_inconsistent",
        "read_unavailable",
        "read_authorization_rejected",
    )

    def __init__(
        self,
        *,
        latency_samples_limit: int = 512,
        recent_operations_limit: int = 256,
        recent_rejections_limit: int = 64,
    ):
        self.latency_samples_limit = latency_samples_limit
        self.recent_operations_limit = recent_operations_limit
        self.recent_rejections_limit = recent_rejections_limit

        self._counters = {key: 0 for key in self.COUNTER_KEYS}
        self._series = {
            "write_global_ms": LatencySeries(latency_samples_limit),
            "read_global_ms": LatencySeries(latency_samples_limit),
        }
        self._replica_series: dict[str, LatencySeries] = {}
        self._recent_operations: deque[dict[str, Any]] = deque(
            maxlen=recent_operations_limit
        )
        self._recent_rejections: deque[dict[str, Any]] = deque(
            maxlen=recent_rejections_limit
        )
        self._lock = threading.Lock()

    # -- helpers ---------------------------------------------------------

    def _replica_series_for(self, name: str) -> LatencySeries:
        with self._lock:
            series = self._replica_series.get(name)
            if series is None:
                series = LatencySeries(self.latency_samples_limit)
                self._replica_series[name] = series
            return series

    def observe_replica_latency(
        self, replica_id: str, operation_kind: str, status_ok: bool, ms: float
    ) -> None:
        key = f"replica[{replica_id}].{operation_kind.lower()}"
        if not status_ok:
            key = f"{key}.unhealthy"
        self._replica_series_for(key).record(ms)

    def record_write_result(self, result: WriteResultV1) -> None:
        outcome = result.outcome
        if outcome is WriteOutcome.COMMITTED:
            # Readiness invariant for future BLACKBOARD_WRITE_COMMITTED
            # events: COMMITTED must always carry a compatible committed
            # quorum. Enforced here as well as in the coordinator.
            durable = [
                ack
                for ack in result.acks
                if ack.ack_status is AckStatus.ACK_COMMITTED
                and ack.record_id == result.record_id
                and ack.content_hash == result.content_hash
            ]
            if len(durable) < 2:
                raise AssertionError(
                    f"invariant violated: COMMITTED with {len(durable)} "
                    f"compatible ACK_COMMITTED (operation {result.operation_id})"
                )
        divergence = any(
            state == "DIVERGENT_REQUIRES_RECONCILIATION"
            for state in result.replica_sync.values()
        )
        counter_for_outcome = {
            WriteOutcome.COMMITTED: (
                "committed_with_divergence" if divergence else "committed"
            ),
            WriteOutcome.PARTIAL_COMMIT: "partial_commit",
            WriteOutcome.REJECTED_STALE: "rejected_stale",
            WriteOutcome.REJECTED_CONFLICT: "rejected_conflict",
            WriteOutcome.REJECTED_SCHEMA: "rejected_schema",
            WriteOutcome.REJECTED_AUTHORIZATION: "rejected_authorization",
            WriteOutcome.FAILED_QUORUM: "failed_quorum",
            WriteOutcome.FAILED_STORAGE: "failed_storage",
        }[outcome]
        summary = {
            "operation_id": result.operation_id,
            "outcome": outcome.value,
            "record_key": result.record_key,
            "record_version": result.record_version,
            "content_hash": result.content_hash,
            "duration_ms": round(result.duration_ms, 3),
            "at_utc": result.completed_at_utc,
        }
        rejection = None
        if outcome is not WriteOutcome.COMMITTED:
            rejection = dict(summary)
            rejection["reason"] = result.reason
        with self._lock:
            self._counters[counter_for_outcome] += 1
            if outcome is not WriteOutcome.COMMITTED:
                if any(
                    ack.ack_status is AckStatus.REJECT_INTEGRITY
                    for ack in result.acks
                ):
                    self._counters["rejected_integrity"] += 1
            self._recent_operations.append(summary)
            if rejection is not None:
                self._recent_rejections.append(rejection)
        self._series["write_global_ms"].record(result.duration_ms)

    def record_read(self, outcome: ReadOutcome, duration_ms: float) -> None:
        counter_for_read = {
            ReadOutcome.CONSISTENT: "read_consistent",
            ReadOutcome.DEGRADED_CONSISTENT: "read_degraded_consistent",
            ReadOutcome.NOT_FOUND: "read_not_found",
            ReadOutcome.INSUFFICIENT_QUORUM: "read_insufficient_quorum",
            ReadOutcome.INCONSISTENT: "read_inconsistent",
            ReadOutcome.UNAVAILABLE: "read_unavailable",
            ReadOutcome.AUTHORIZATION_REJECTED: "read_authorization_rejected",
        }[outcome]
        with self._lock:
            self._counters[counter_for_read] += 1
        self._series["read_global_ms"].record(duration_ms)

    def increment(self, key: str) -> None:
        with self._lock:
            if key in self._counters:
                self._counters[key] += 1

    def note_operation(self, summary: dict[str, Any]) -> None:
        with self._lock:
            self._recent_operations.append(summary)

    # -- snapshots ---------------------------------------------------------

    def counters(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def latencies(self) -> dict[str, dict[str, Any]]:
        out = {name: s.snapshot() for name, s in self._series.items()}
        out.update(
            {name: s.snapshot() for name, s in self._replica_series.items()}
        )
        return out

    def recent_operations(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(self._recent_operations)

    def recent_rejections(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(self._recent_rejections)

    def snapshot(self) -> dict[str, Any]:
        return {
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "counters": self.counters(),
            "latencies": self.latencies(),
            "recent_operations": list(self.recent_operations()),
            "recent_rejections": list(self.recent_rejections()),
            "bounds": {
                "latency_samples_limit": self.latency_samples_limit,
                "recent_operations_limit": self.recent_operations_limit,
                "recent_rejections_limit": self.recent_rejections_limit,
            },
        }
