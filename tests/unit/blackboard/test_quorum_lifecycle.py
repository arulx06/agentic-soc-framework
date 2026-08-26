"""Quorum rule, prepare/abort lifecycle and incompatible-ack handling."""

from __future__ import annotations

from blackboard.contracts import AckStatus, ReplicaAckV1, WriteOutcome, build_record
from blackboard.coordinator import evaluate_quorum
from tests.unit.blackboard.helpers import (
    OverrideStagedRecordHooks,
    UnavailableOnPrepareHooks,
    draft,
    make_coordinator,
)


def _prepared_ack(rid: str, h: str) -> ReplicaAckV1:
    return ReplicaAckV1(
        operation_id="op",
        replica_id=rid,
        operation_kind="PREPARE",
        ack_status=AckStatus.ACK_PREPARED,
        record_id=f"k#v1#{h[:12]}",
        record_key="k",
        record_version=1,
        content_hash=h,
        observed_at_utc="2026-01-01T00:00:00Z",
    )


class TestQuorumCombinator:
    def test_three_compatible_acks_meet_quorum(self):
        q = evaluate_quorum(
            [
                _prepared_ack("a", "H"),
                _prepared_ack("b", "H"),
                _prepared_ack("c", "H"),
            ],
            required=2,
        )
        assert q.decision == "QUORUM_MET"
        assert set(q.compatible_replica_ids) == {"a", "b", "c"}

    def test_two_compatible_plus_one_other_hash_meets(self):
        q = evaluate_quorum(
            [
                _prepared_ack("a", "H"),
                _prepared_ack("b", "H"),
                _prepared_ack("c", "G"),
            ],
            required=2,
        )
        assert q.decision == "QUORUM_MET"
        assert set(q.compatible_replica_ids) == {"a", "b"}
        assert q.group_content_hash == "H"

    def test_single_ack_insufficient(self):
        q = evaluate_quorum([_prepared_ack("a", "H")], required=2)
        assert q.decision == "INSUFFICIENT_COMPATIBLE_ACKS"

    def test_zero_prepared_acks_insufficient(self):
        q = evaluate_quorum([], required=2)
        assert q.decision == "INSUFFICIENT_COMPATIBLE_ACKS"

    def test_three_way_split_is_incompatible(self):
        q = evaluate_quorum(
            [
                _prepared_ack("a", "X"),
                _prepared_ack("b", "Y"),
                _prepared_ack("c", "Z"),
            ],
            required=2,
        )
        assert q.decision == "INCOMPATIBLE_PREPARED_ACKS"

    def test_rejections_never_count_toward_quorum(self):
        reject = ReplicaAckV1(
            operation_id="op",
            replica_id="a",
            operation_kind="PREPARE",
            ack_status=AckStatus.REJECT_STALE,
            current_version_at_replica=4,
            observed_at_utc="2026-01-01T00:00:00Z",
        )
        q = evaluate_quorum([reject, reject], required=2)
        assert q.decision == "INSUFFICIENT_COMPATIBLE_ACKS"


class TestQuorumLifecycle:
    def test_three_of_three_commit_all_synced(self, coordinator):
        result = coordinator.propose(draft(), "system")
        assert result.outcome is WriteOutcome.COMMITTED
        assert result.replica_sync == {
            "replica_a": "SYNCED",
            "replica_b": "SYNCED",
            "replica_c": "SYNCED",
        }
        kinds = [(a.ack_status, a.operation_kind) for a in result.acks]
        assert (AckStatus.ACK_PREPARED, "PREPARE") in kinds
        assert (AckStatus.ACK_COMMITTED, "COMMIT") in kinds

    def test_two_of_three_with_unavailable_replica_commits(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            coord.replicas[2].set_unavailable("maintenance")
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.COMMITTED
            assert result.replica_sync["replica_c"] == "UNAVAILABLE"
            assert (
                result.replica_sync["replica_a"],
                result.replica_sync["replica_b"],
            ) == ("SYNCED", "SYNCED")
            statuses = [
                a.ack_status for a in result.acks if a.replica_id == "replica_c"
            ]
            assert AckStatus.UNAVAILABLE in statuses
        finally:
            coord.close()

    def test_one_responsive_replica_fails_quorum_and_aborts(self, bb_root):
        hooks = UnavailableOnPrepareHooks({"replica_b", "replica_c"})
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.FAILED_QUORUM
            aborts = [a for a in result.acks if a.ack_status is AckStatus.ABORTED]
            assert len(aborts) == 1 and aborts[0].replica_id == "replica_a"

            # Prepared state must NOT be visible as committed anywhere.
            healthy = coord.replicas[0]
            assert healthy.db.count_pending() == 0
            assert healthy.get_committed_row("device_state:dev1") is None
            rd = coord.read_latest("system", "device_state:dev1")
            assert rd.outcome.value == "NOT_FOUND"
        finally:
            coord.close()

    def test_zero_responsive_replicas_fails_fast(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            for r in coord.replicas:
                r.set_unavailable("all down")
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.FAILED_QUORUM
            assert "no responsive replica" in result.reason
        finally:
            coord.close()


class TestIncompatibleAcknowledgements:
    """The equivocation seam is exercised exactly as a future evaluation
    harness would use it (production default hooks are identity)."""

    @staticmethod
    def _forge(payload: dict, author: str):
        def factory(rec):
            return build_record(
                record_key=rec.record_key,
                record_type=rec.record_type,
                record_version=rec.record_version,
                author_id=author,
                source_component="equivocation-seam",
                payload=payload,
                logical_timestamp=rec.logical_timestamp,
                window_id=rec.window_id,
            )

        return factory

    def test_minority_override_cannot_join_quorum(self, bb_root):
        hooks = OverrideStagedRecordHooks(
            {"replica_b": self._forge({"forged": True}, "eval_harness")}
        )
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            # Two honest replicas still form the compatible quorum; the
            # equivocating loser's staging is aborted explicitly.
            assert result.outcome is WriteOutcome.COMMITTED
            assert result.replica_sync["replica_b"] == "ABORTED"
            assert coord.replicas[1].db.count_committed() == 0
            assert coord.replicas[1].db.count_pending() == 0

            # The loser holds NO committed value where the majority has one:
            # reads are degraded-consistent and name it explicitly.
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome.value == "DEGRADED_CONSISTENT"
            assert rd.divergent_replicas == ("replica_b",)
            assert rd.record.payload.get("entity_id") == "dev1"

            # Explicit operational repair restores full consistency.
            report = coord.resync_replicas_from_majority("admin", "device_state:dev1")
            assert report["status"] in {"REPAIRED", "PARTIAL"}
            rd2 = coord.read_latest("reader", "device_state:dev1")
            assert rd2.outcome.value == "CONSISTENT"
        finally:
            coord.close()

    def test_three_way_split_never_commits(self, bb_root):
        hooks = OverrideStagedRecordHooks(
            {
                "replica_a": self._forge({"split": "x"}, "writer_x"),
                "replica_b": self._forge({"split": "y"}, "writer_y"),
            }
        )
        coord = make_coordinator(bb_root, hooks=hooks)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome is WriteOutcome.FAILED_QUORUM
            assert "incompatible" in result.reason
            for replica in coord.replicas:
                assert replica.db.count_committed() == 0
                assert replica.db.count_pending() == 0
        finally:
            coord.close()
