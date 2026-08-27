"""Commit-phase durability: COMMITTED requires a compatible ACK_COMMITTED
quorum, never merely a prepared one."""

from __future__ import annotations

from blackboard import ReplicaHealth
from blackboard.contracts import AckStatus, ReadOutcome, WriteOutcome
from tests.unit.blackboard.helpers import (
    FailOnCommitHooks,
    UnavailableOnPrepareHooks,
    draft,
    make_coordinator,
)


def _durable_commit_acks(result):
    return [
        a
        for a in result.acks
        if a.ack_status is AckStatus.ACK_COMMITTED
        and a.operation_kind == "COMMIT"
        and a.record_id == result.record_id
        and a.content_hash == result.content_hash
    ]


def _assert_committed_implies_durable_quorum(result) -> None:
    """Readiness invariant for future BLACKBOARD_WRITE_COMMITTED events:
    WriteOutcome.COMMITTED must imply >= 2 compatible ACK_COMMITTED."""
    if result.outcome is not WriteOutcome.COMMITTED:
        return
    durable = _durable_commit_acks(result)
    assert len(durable) >= 2, (
        f"invariant violated: outcome=COMMITTED with {len(durable)} "
        f"compatible ACK_COMMITTED (op={result.operation_id})"
    )


class TestCommitPhaseMatrix:
    def test_three_commits_committed(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            r = coord.propose(draft(), "system")
            assert r.outcome is WriteOutcome.COMMITTED
            assert len(_durable_commit_acks(r)) == 3
            _assert_committed_implies_durable_quorum(r)
        finally:
            coord.close()

    def test_two_commits_plus_one_failure_is_committed_with_divergence(
        self, bb_root
    ):
        hooks = FailOnCommitHooks({"replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            r = coord.propose(draft(), "system")
            assert r.outcome is WriteOutcome.COMMITTED
            durable = _durable_commit_acks(r)
            assert len(durable) == 2
            assert r.replica_sync["replica_c"] == "DIVERGENT_REQUIRES_RECONCILIATION"
            assert coord.replicas[2].health is ReplicaHealth.DIVERGED
            _assert_committed_implies_durable_quorum(r)
        finally:
            coord.close()

    def test_single_commit_is_partial_not_committed(self, bb_root):
        """Exactly one ACK_COMMITTED must NEVER be reported as COMMITTED."""
        hooks = FailOnCommitHooks({"replica_b", "replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            r = coord.propose(draft(), "system")
            assert r.outcome is WriteOutcome.PARTIAL_COMMIT
            assert r.outcome is not WriteOutcome.COMMITTED

            # Identity / operation context preserved.
            durable = _durable_commit_acks(r)
            assert len(durable) == 1
            assert durable[0].record_id == r.record_id
            assert r.record_key == "device_state:dev1"
            assert r.record_version == 1
            assert "partial" in (r.reason or "")
            assert "reconciliation" in (r.reason or "")

            # Successful vs failed commit replicas explicitly distinguished;
            # the single committed replica was NOT erased for symmetry.
            assert r.replica_sync["replica_a"] == "SYNCED"
            assert r.replica_sync["replica_b"] == "DIVERGENT_REQUIRES_RECONCILIATION"
            assert r.replica_sync["replica_c"] == "DIVERGENT_REQUIRES_RECONCILIATION"
            assert coord.replicas[1].health is ReplicaHealth.DIVERGED
            assert coord.replicas[2].health is ReplicaHealth.DIVERGED
            assert coord.replicas[0].get_committed_row("device_state:dev1") is not None

            # Majority reads do not expose the lone committed replica: two
            # responders deny any value, so existence itself disagrees.
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.INCONSISTENT
            assert rd.record is None
            assert set(rd.divergent_replicas) == {"replica_b", "replica_c"}
        finally:
            coord.close()

    def test_zero_commits_is_failed_storage(self, bb_root):
        hooks = FailOnCommitHooks({"replica_a", "replica_b", "replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            r = coord.propose(draft(), "system")
            assert r.outcome is WriteOutcome.FAILED_STORAGE
            assert len(_durable_commit_acks(r)) == 0
        finally:
            coord.close()


class TestPartialCommitSurvivesRestart:
    def test_restart_never_retroactively_blesses_partial_state(self, bb_root):
        """After restart the one-committed-replica operation is still not
        treated as a successful committed quorum."""
        coord1 = make_coordinator(bb_root)
        try:
            seed = coord1.propose(draft(version=1), "system")
            assert seed.outcome is WriteOutcome.COMMITTED
            v1_hash = seed.content_hash

            # Install commit-phase faults ONLY for the v2 operation.
            hooks = FailOnCommitHooks({"replica_b", "replica_c"})
            for replica in coord1.replicas:
                replica.hooks = hooks
            partial = coord1.propose(draft(version=2), "system")
            assert partial.outcome is WriteOutcome.PARTIAL_COMMIT
            partial_record_id = partial.record_id
        finally:
            coord1.close()

        # Fresh coordinator against the same stores, no fault hooks.
        coord2 = make_coordinator(bb_root)
        try:
            # The last QUORUM-committed value stays the authoritative head.
            rd = coord2.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.DEGRADED_CONSISTENT
            assert rd.record.record_version == 1
            assert rd.record.content_hash == v1_hash
            assert rd.divergent_replicas == ("replica_a",)
            assert coord2.replicas[0].health is ReplicaHealth.DIVERGED

            # The partial version is visible to nobody as authoritative.
            rv = coord2.read_version("reader", "device_state:dev1", 2)
            assert rv.outcome is ReadOutcome.INCONSISTENT
            assert rv.record is None

            # Explicit repair must not erase the newer committed replica
            # just to regain symmetry.
            report = coord2.resync_replicas_from_majority("admin", "device_state:dev1")
            row_a = coord2.replicas[0].get_committed_row("device_state:dev1", 2)
            assert row_a is not None
            assert row_a["record_id"] == partial_record_id  # preserved
            assert report["status"] in {"PARTIAL", "REFUSED"}
        finally:
            coord2.close()


class TestCommittedImpliesQuorumInvariant:
    """Regression guard: every code path returning COMMITTED must carry at
    least two compatible ACK_COMMITTED acknowledgements."""

    def test_invariant_holds_across_all_success_paths(self, bb_root):
        # Each path uses its OWN record key so per-replica head positions
        # from an earlier fault scenario cannot contaminate later paths.
        coord = make_coordinator(bb_root)
        try:
            results = []

            # Path 1: fully healthy writes.
            for version in (1, 2, 3):
                results.append(
                    coord.propose(draft(key="inv:k1", version=version), "system")
                )

            # Path 2: prepare-time unavailability, 2-of-3 commit.
            coord.replicas[2].set_unavailable("maintenance")
            results.append(coord.propose(draft(key="inv:k2"), "system"))
            coord.replicas[2].set_available()

            # Path 3: commit-time failure on one replica, 2-of-3 durable.
            fail_hooks = FailOnCommitHooks({"replica_b"})
            for replica in coord.replicas:
                replica.hooks = fail_hooks
            results.append(coord.propose(draft(key="inv:k3"), "system"))

            # Path 4: hook-driven prepare unavailability, 2-of-3 durable.
            unavailable_hooks = UnavailableOnPrepareHooks({"replica_c"})
            for replica in coord.replicas:
                replica.hooks = unavailable_hooks
            results.append(coord.propose(draft(key="inv:k4"), "system"))

            committed = [r for r in results if r.outcome is WriteOutcome.COMMITTED]
            assert len(committed) == 6
            assert all(r.outcome is not WriteOutcome.PARTIAL_COMMIT for r in results)
            for r in committed:
                _assert_committed_implies_durable_quorum(r)
        finally:
            coord.close()
