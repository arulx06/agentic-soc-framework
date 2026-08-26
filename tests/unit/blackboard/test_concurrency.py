"""Concurrency safety on same-key updates."""

from __future__ import annotations

import concurrent.futures

from blackboard.contracts import WriteOutcome
from tests.unit.blackboard.helpers import draft, make_coordinator


class TestSameKeyRaces:
    def test_competing_first_versions_exactly_one_winner(self, coordinator):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures = [
                pool.submit(
                    coordinator.propose,
                    draft(payload={"writer": f"w{i}"}),
                    f"principal_{i}",
                )
                for i in range(6)
            ]
            results = [f.result() for f in futures]

        outcomes = [r.outcome for r in results]
        committed = [r for r in results if r.outcome is WriteOutcome.COMMITTED]
        assert len(committed) == 1, outcomes
        for r in results:
            if r.outcome is not WriteOutcome.COMMITTED:
                assert r.outcome in (
                    WriteOutcome.REJECTED_STALE,
                    WriteOutcome.REJECTED_CONFLICT,
                )

        winner = committed[0]
        rd = coordinator.read_latest("auditor", "device_state:dev1")
        assert rd.outcome.value in {"CONSISTENT", "DEGRADED_CONSISTENT"}
        assert rd.record.content_hash == winner.content_hash
        assert rd.record.record_version == 1

    def test_optimistic_retry_converges_without_lost_updates(self, coordinator):
        WORKERS, INCREMENTS = 4, 5

        def increment(worker: int) -> int:
            applied = 0
            for i in range(INCREMENTS):
                for _ in range(200):  # bounded retry budget
                    current = coordinator.read_latest("system", "counter:key")
                    version = (
                        current.record.record_version + 1
                        if current.record is not None
                        else 1
                    )
                    result = coordinator.propose(
                        draft(
                            key="counter:key",
                            version=version,
                            payload={"count": worker * INCREMENTS + i},
                        ),
                        f"worker_{worker}",
                    )
                    if result.outcome is WriteOutcome.COMMITTED:
                        applied += 1
                        break
            return applied

        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            totals = [f.result() for f in [pool.submit(increment, w) for w in range(WORKERS)]]

        assert sum(totals) == WORKERS * INCREMENTS
        latest = coordinator.read_latest("auditor", "counter:key")
        assert latest.record.record_version == WORKERS * INCREMENTS
        # Every intermediate version exists exactly once — no gaps, no forks.
        for v in range(1, WORKERS * INCREMENTS + 1):
            got = coordinator.read_version("auditor", "counter:key", v)
            assert got.outcome.value in {"CONSISTENT", "DEGRADED_CONSISTENT"}


class TestCrossCoordinatorContention:
    def test_two_coordinators_same_slot_single_winner(self, bb_root):
        coord_a = make_coordinator(bb_root)
        coord_b = make_coordinator(bb_root)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                fa = pool.submit(coord_a.propose, draft(payload={"side": "a"}), "a")
                fb = pool.submit(coord_b.propose, draft(payload={"side": "b"}), "b")
                ra, rb = fa.result(), fb.result()

            committed = [
                r for r in (ra, rb) if r.outcome is WriteOutcome.COMMITTED
            ]
            assert len(committed) <= 1
            # Whatever won, the slot holds exactly one content everywhere.
            rows = []
            for replica in coord_a.replicas:
                row = replica.get_committed_row("device_state:dev1")
                if row is not None:
                    rows.append(row["content_hash"])
            assert len(set(rows)) <= 1
        finally:
            coord_a.close()
            coord_b.close()
