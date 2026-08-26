"""Commit-phase partial failure, divergence marking and explicit repair."""

from __future__ import annotations

from blackboard import ReplicaHealth
from blackboard.contracts import AckStatus, WriteOutcome
from tests.unit.blackboard.helpers import (
    FailOnCommitHooks,
    UnavailableOnPrepareHooks,
    draft,
    make_coordinator,
)


class TestPartialCommit:
    def test_missed_commit_becomes_explicit_divergence(self, bb_root):
        hooks = FailOnCommitHooks({"replica_b"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.COMMITTED
            assert (
                result.replica_sync["replica_b"]
                == "DIVERGENT_REQUIRES_RECONCILIATION"
            )
            assert result.replica_sync["replica_a"] == "SYNCED"
            assert coord.replicas[1].health is ReplicaHealth.DIVERGED

            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome.value == "DEGRADED_CONSISTENT"
            assert rd.divergent_replicas == ("replica_b",)
            assert rd.record.record_version == 1
        finally:
            coord.close()

    def test_total_commit_failure_is_failed_storage_with_no_visible_state(
        self, bb_root
    ):
        hooks = FailOnCommitHooks({"replica_a", "replica_b", "replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.FAILED_STORAGE
            for replica in coord.replicas:
                assert replica.db.count_committed() == 0
            # Staging survives (stranded) but is invisible to reads.
            assert coord.read_latest("system", "device_state:dev1").outcome.value == "NOT_FOUND"
            stranded_ops = [
                a.operation_id
                for a in result.acks
                if a.ack_status is AckStatus.ACK_PREPARED
            ]
            assert len(set(stranded_ops)) == 1

            # Operational cleanup: disable the injected fault, abort the
            # stranded staging explicitly...
            hooks.enabled = False
            op_id = result.operation_id
            for replica in coord.replicas:
                ack = replica.abort(op_id, "device_state:dev1", 1)
                assert ack.ack_status is AckStatus.ABORTED
            # ...after which the key is writable again.
            ok = coord.propose(draft(), "system")
            assert ok.outcome is WriteOutcome.COMMITTED
        finally:
            coord.close()

    def test_unavailable_during_prepare_then_recovery(self, bb_root):
        hooks = UnavailableOnPrepareHooks({"replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            first = coord.propose(draft(), "system")
            assert first.outcome is WriteOutcome.COMMITTED
            coord.replicas[2].set_available()
            second = coord.propose(draft(version=2), "system")
            assert second.outcome is WriteOutcome.COMMITTED
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome.value == "CONSISTENT" or (
                rd.outcome.value == "DEGRADED_CONSISTENT"
            )
        finally:
            coord.close()


class TestExplicitRepair:
    def test_resync_from_majority_restores_consistency(self, bb_root):
        hooks = FailOnCommitHooks({"replica_b"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            first = coord.propose(draft(), "system")
            assert first.outcome is WriteOutcome.COMMITTED
            assert coord.replicas[1].health is ReplicaHealth.DIVERGED

            report = coord.resync_replicas_from_majority("admin", "device_state:dev1")
            assert report["status"] in {"REPAIRED", "PARTIAL"}
            assert report["replicas"]["replica_b"].startswith("REPAIRED")
            assert coord.replicas[1].health is ReplicaHealth.HEALTHY

            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome.value == "CONSISTENT"
            assert rd.divergent_replicas == ()
        finally:
            coord.close()

    def test_resync_refused_when_no_majority_source(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            # Commit only on one replica directly: no compatible majority.
            rec = draft(key="lonely:key").to_record()
            replica = coord.replicas[0]
            assert replica.prepare("op-solo", rec).ack_status is AckStatus.ACK_PREPARED
            assert replica.commit("op-solo", rec).ack_status is AckStatus.ACK_COMMITTED

            report = coord.resync_replicas_from_majority("admin", "lonely:key")
            assert report["status"] == "NO_MAJORITY_SOURCE"
        finally:
            coord.close()

    def test_resync_requires_write_authorization(self, bb_root):
        from blackboard.authorization import BlackboardOperation, PrincipalPolicyAuthorizer

        policy = PrincipalPolicyAuthorizer({"admin": frozenset({BlackboardOperation.WRITE})})
        coord = make_coordinator(bb_root, authorizer=policy)
        try:
            report = coord.resync_replicas_from_majority(
                "not_admin", "device_state:dev1"
            )
            assert report["status"] == "AUTHORIZATION_REJECTED"
        finally:
            coord.close()
