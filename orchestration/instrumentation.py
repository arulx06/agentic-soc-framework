"""Thread-safe bounded operational instrumentation for Stage 6."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any


class OrchestrationInstrumentation:
    COUNTERS = (
        "rounds_started",
        "decisions_reached",
        "no_quorum",
        "timed_out",
        "insufficient_responses",
        "proposals_received",
        "proposals_rejected",
        "votes_received",
        "votes_rejected",
        "authentication_failures",
        "duplicate_messages",
        "conflicting_votes",
        "orchestrator_timeouts",
        "orchestrator_delays",
        "orchestrator_omissions",
        "orchestrator_disagreements",
    )

    def __init__(self, latency_limit: int = 256, rejection_limit: int = 64):
        if latency_limit < 1 or rejection_limit < 1:
            raise ValueError("instrumentation bounds must be positive")
        self.latency_limit = latency_limit
        self.rejection_limit = rejection_limit
        self._counters = {name: 0 for name in self.COUNTERS}
        self._latencies = {
            name: deque(maxlen=latency_limit)
            for name in ("proposal_ms", "vote_ms", "quorum_ms", "decision_ms")
        }
        self._rejections: deque[dict[str, Any]] = deque(maxlen=rejection_limit)
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            if name not in self._counters:
                raise KeyError(name)
            self._counters[name] += amount

    def latency(self, name: str, milliseconds: float) -> None:
        with self._lock:
            self._latencies[name].append(float(milliseconds))

    def rejection(self, evidence: dict[str, Any]) -> None:
        with self._lock:
            self._rejections.append(dict(evidence))

    @staticmethod
    def _summary(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0}
        values.sort()
        count = len(values)
        percentile = lambda p: values[min(count - 1, round(p * (count - 1)))]
        return {
            "count": count,
            "mean_ms": round(sum(values) / count, 3),
            "p50_ms": round(percentile(0.50), 3),
            "p95_ms": round(percentile(0.95), 3),
            "max_ms": round(values[-1], 3),
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            latencies = {
                name: self._summary(list(values))
                for name, values in self._latencies.items()
            }
            rejections = list(self._rejections)
        return {
            "counters": counters,
            "latencies": latencies,
            "recent_rejections": rejections,
            "bounds": {
                "latency_samples": self.latency_limit,
                "recent_rejections": self.rejection_limit,
            },
        }
