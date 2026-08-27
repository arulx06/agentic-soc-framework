"""Bounded runtime memory and core instrumentation."""

from __future__ import annotations

from collections import deque

import pytest

from blackboard.contracts import WriteOutcome
from blackboard.settings import BlackboardSettings
from tests.unit.blackboard.helpers import draft, make_coordinator


class TestBoundedHistories:
    def test_recent_operations_ring_stays_capped(self, bounded_coord):
        for v in range(1, 41):
            result = bounded_coord.propose(draft(version=v), "system")
            assert result.outcome is WriteOutcome.COMMITTED

        snapshot = bounded_coord.instrumentation.snapshot()
        ops = snapshot["recent_operations"]
        assert len(ops) == 10  # NOT 40 — ring, not unbounded list
        assert ops[-1]["record_version"] == 40
        assert ops[0]["record_version"] == 31
        assert isinstance(
            bounded_coord.instrumentation._recent_operations, deque
        )

    def test_rejection_ring_stays_capped(self, bounded_coord):
        bounded_coord.propose(draft(), "system")
        for _ in range(20):
            bounded_coord.propose(draft(payload={"retry": True}), "system")

        rejections = bounded_coord.instrumentation.recent_rejections()
        assert len(rejections) <= 5

    def test_latency_series_capped(self, bounded_coord):
        for v in range(1, 31):
            bounded_coord.propose(draft(version=v), "system")
            bounded_coord.read_latest("reader", "device_state:dev1")

        lat = bounded_coord.instrumentation.latencies()
        write_series = lat["write_global_ms"]
        read_series = lat["read_global_ms"]
        assert write_series["count"] <= 16
        assert read_series["count"] <= 16
        for series in (write_series, read_series):
            assert {"p50_ms", "p95_ms", "max_ms", "mean_ms"} <= set(series)


class TestInstrumentationValues:
    def test_counters_track_outcomes(self, coordinator):
        coordinator.propose(draft(), "system")                       # committed
        coordinator.propose(draft(version=2), "system")              # committed
        coordinator.propose(draft(version=1), "system")              # stale
        coordinator.replicas[2].set_unavailable("down")
        coordinator.propose(draft(version=3), "system")              # 2-of-3 commit

        counters = coordinator.instrumentation.counters()
        assert counters["writes_started"] == 4
        assert counters["committed"] == 3
        assert counters["rejected_stale"] == 1
        assert counters["failed_quorum"] == 0

    def test_replica_prepare_and_commit_latencies_measured(self, coordinator):
        coordinator.propose(draft(), "system")
        lat = coordinator.instrumentation.latencies()
        for rid in ("replica_a", "replica_b", "replica_c"):
            assert f"replica[{rid}].prepare" in lat
            assert f"replica[{rid}].commit" in lat
            assert lat[f"replica[{rid}].prepare"]["count"] >= 1
            assert lat[f"replica[{rid}].commit"]["count"] >= 1

    def test_read_outcomes_counted(self, coordinator):
        coordinator.read_latest("reader", "absent:key")
        coordinator.read_latest("reader", "absent:key")
        counters = coordinator.instrumentation.counters()
        assert counters["reads_started"] >= 2
        assert counters["read_not_found"] >= 2


class TestSettingsValidation:
    def test_invalid_bounds_rejected(self):
        with pytest.raises(ValueError):
            BlackboardSettings(recent_operations_limit=0)
        with pytest.raises(ValueError):
            BlackboardSettings(pending_lease_seconds=0)
        with pytest.raises(ValueError):
            BlackboardSettings(max_record_canonical_bytes=-1)

    def test_default_runtime_root_is_not_under_data_raw(self):
        from blackboard.settings import RUNTIME_BLACKBOARD_ROOT

        parts = RUNTIME_BLACKBOARD_ROOT.parts
        assert "data" not in parts or "raw" not in parts
        assert parts[-2:] == ("runtime", "blackboard")
