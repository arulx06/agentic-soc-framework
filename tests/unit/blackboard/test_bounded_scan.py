"""Explicit bounded-scan semantics for merged committed views.

The old implementation silently capped the per-replica scan at a hidden
10,000-row literal. The view now scans in configurable chunks up to a named
bound and reports truncation explicitly instead of implying completeness.
"""

from __future__ import annotations

from blackboard import BlackboardSettings
from blackboard.contracts import WriteOutcome
from tests.unit.blackboard.helpers import draft, make_coordinator


def _write_keys(coord, n: int, prefix="scan"):
    for i in range(n):
        r = coord.propose(draft(key=f"{prefix}:k{i}"), "system")
        assert r.outcome is WriteOutcome.COMMITTED


class TestBoundedScanSemantics:
    def test_truncation_is_explicit_not_silent(self, bb_root):
        settings = BlackboardSettings(
            committed_scan_max_rows=5, committed_scan_chunk_size=2
        )
        coord = make_coordinator(bb_root, settings=settings)
        try:
            _write_keys(coord, 7)  # more committed rows than the bound

            view = coord.committed_view()
            assert view["truncated"] is True
            assert set(view["truncated_replicas"]) == {
                "replica_a",
                "replica_b",
                "replica_c",
            }
            # Only the scanned scope is counted, and it is labelled as such.
            assert view["total_verified"] == 5
            assert view["scanned_rows_per_replica"] == {
                "replica_a": 5,
                "replica_b": 5,
                "replica_c": 5,
            }
            assert view["scan_bounds"] == {
                "max_rows_per_replica": 5,
                "chunk_size": 2,
            }
        finally:
            coord.close()

    def test_complete_view_when_bound_covers_the_store(self, bb_root):
        settings = BlackboardSettings(
            committed_scan_max_rows=20, committed_scan_chunk_size=3
        )
        coord = make_coordinator(bb_root, settings=settings)
        try:
            _write_keys(coord, 7)
            view = coord.committed_view()
            assert view["truncated"] is False
            assert view["truncated_replicas"] == []
            assert view["total_verified"] == 7
        finally:
            coord.close()

    def test_exact_fit_at_bound_is_complete_not_truncated(self, bb_root):
        settings = BlackboardSettings(
            committed_scan_max_rows=7, committed_scan_chunk_size=2
        )
        coord = make_coordinator(bb_root, settings=settings)
        try:
            _write_keys(coord, 7)
            view = coord.committed_view()
            assert view["truncated"] is False
            assert view["total_verified"] == 7
        finally:
            coord.close()

    def test_prefix_scoped_scan_obeys_same_bounds(self, bb_root):
        settings = BlackboardSettings(
            committed_scan_max_rows=2, committed_scan_chunk_size=1
        )
        coord = make_coordinator(bb_root, settings=settings)
        try:
            _write_keys(coord, 4, prefix="in-scope")
            _write_keys(coord, 1, prefix="other")
            view = coord.committed_view(key_prefix="in-scope:")
            assert view["truncated"] is True
            assert view["total_verified"] == 2  # scanned scope only
            # The unscoped view hits the same tiny bound on the first two
            # keys (sorted order), so it is truncated there as well.
            full = coord.committed_view()
            assert full["truncated"] is True
            assert full["total_verified"] == 2
        finally:
            coord.close()

    def test_settings_validate_bounds(self):
        import pytest

        with pytest.raises(ValueError):
            BlackboardSettings(committed_scan_max_rows=0)
        with pytest.raises(ValueError):
            BlackboardSettings(committed_scan_chunk_size=0)
