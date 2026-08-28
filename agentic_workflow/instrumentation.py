"""Bounded instrumentation for Stage-8A core."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any


class AgenticInstrumentation:
    COUNTERS = (
        "agent_executions",
        "agent_failures",
        "threat_matched",
        "threat_unmapped",
        "threat_unsupported",
        "risk_recommendations",
        "access_allow",
        "access_monitor",
        "access_block",
        "action_commits",
        "action_duplicates",
        "action_conflicts",
    )

    def __init__(self, latency_limit: int = 256, history_limit: int = 64):
        if latency_limit < 1 or history_limit < 1:
            raise ValueError("limits must be positive")
        self.latency_limit = latency_limit
        self.history_limit = history_limit
        self._counters = {k: 0 for k in self.COUNTERS}
        self._latencies: dict[str, deque[float]] = {
            k: deque(maxlen=latency_limit)
            for k in (
                "network_agent_ms",
                "behavior_agent_ms",
                "threat_correlator_ms",
                "risk_analyst_ms",
                "access_controller_ms",
            )
        }
        self._recent: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._lock = threading.Lock()

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            if key not in self._counters:
                raise KeyError(key)
            self._counters[key] += amount

    def record_latency(self, key: str, ms: float) -> None:
        with self._lock:
            if key not in self._latencies:
                raise KeyError(key)
            self._latencies[key].append(float(ms))

    def note(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._recent.append(dict(entry))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            latencies = {}
            for k, dq in self._latencies.items():
                vals = sorted(dq)
                if not vals:
                    latencies[k] = {"count": 0}
                else:
                    n = len(vals)
                    latencies[k] = {
                        "count": n,
                        "mean_ms": round(sum(vals) / n, 3),
                        "p50_ms": round(vals[n // 2], 3),
                        "p95_ms": round(vals[int(n * 0.95)], 3),
                        "max_ms": round(vals[-1], 3),
                    }
            recent = list(self._recent)
        return {
            "counters": counters,
            "latencies": latencies,
            "recent": recent,
            "bounds": {"latency_limit": self.latency_limit, "history_limit": self.history_limit},
        }
