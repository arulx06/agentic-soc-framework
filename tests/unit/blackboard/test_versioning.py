"""Optimistic versioning, stale-write rejection and conflict semantics."""

from __future__ import annotations

from blackboard.contracts import AckStatus, WriteOutcome
from tests.unit.blackboard.helpers import draft


class TestVersionProgression:
    def test_v1_v2_v3_monotonic(self, coordinator):
        hashes = []
        for v, risk in ((1, 0.1), (2, 0.2), (3, 0.3)):
            result = coordinator.propose(
                draft(version=v, payload={"entity_id": "dev1", "network_risk": risk}),
                "system",
            )
            assert result.outcome is WriteOutcome.COMMITTED, result.reason
            assert result.record_version == v
            hashes.append(result.content_hash)
        assert len(set(hashes)) == 3

        for v in (1, 2, 3):
            got = coordinator.read_version("reader", "device_state:dev1", v)
            assert got.outcome.value == "CONSISTENT"
            assert got.record.record_version == v

        latest = coordinator.read_latest("reader", "device_state:dev1")
        assert latest.record.record_version == 3

    def test_new_key_must_start_at_version_one(self, coordinator):
        result = coordinator.propose(draft(key="fresh:key", version=7), "system")
        assert result.outcome is WriteOutcome.REJECTED_SCHEMA
        assert "ahead" in result.reason

    def test_expected_version_ahead_rejected(self, coordinator):
        assert coordinator.propose(draft(), "system").outcome is WriteOutcome.COMMITTED
        ahead = coordinator.propose(draft(version=5), "system")
        assert ahead.outcome is WriteOutcome.REJECTED_SCHEMA
        assert "ahead" in ahead.reason


class TestStaleWrites:
    def test_stale_proposal_rejected_with_structured_context(self, coordinator):
        for v in (1, 2, 3):
            coordinator.propose(draft(version=v), "system")

        stale = coordinator.propose(
            draft(version=1, payload={"mutated": True}), "system"
        )
        assert stale.outcome is WriteOutcome.REJECTED_STALE
        acks = [a for a in stale.acks if a.ack_status is AckStatus.REJECT_STALE]
        assert len(acks) == 3
        assert {a.current_version_at_replica for a in acks} == {3}

        latest = coordinator.read_latest("reader", "device_state:dev1")
        assert latest.record.record_version == 3
        assert "injected" not in latest.record.payload

    def test_stale_write_leaves_committed_hash_unchanged(self, coordinator):
        coordinator.propose(draft(), "system")
        before = coordinator.read_latest("reader", "device_state:dev1").record.content_hash
        coordinator.propose(draft(version=1, payload={"x": "different"}), "system")
        after = coordinator.read_latest("reader", "device_state:dev1").record.content_hash
        assert before == after


class TestConflictSemanticsAtReplicaLayer:
    """Competing proposals for the same logical next version."""

    def _commit_direct(self, replica, op, rec):
        assert replica.prepare(op, rec).ack_status is AckStatus.ACK_PREPARED
        assert replica.commit(op, rec).ack_status is AckStatus.ACK_COMMITTED

    def test_second_different_content_for_same_slot_rejected(self, bb_root):
        from blackboard import BlackboardReplica

        replica = BlackboardReplica("replica_a", bb_root / "a.db")
        try:
            proposal_a = draft(payload={"winner": True}).to_record()
            proposal_b = draft(payload={"winner": False}).to_record()
            assert proposal_a.content_hash != proposal_b.content_hash

            first = replica.prepare("op-conf-a", proposal_a)
            assert first.ack_status is AckStatus.ACK_PREPARED

            second = replica.prepare("op-conf-b", proposal_b)
            assert second.ack_status is AckStatus.REJECT_CONFLICT

            # The staged winner still commits; the loser never touched state.
            self._commit_direct(replica, "op-conf-a", proposal_a)
            row = replica.get_committed_row(proposal_a.record_key)
            assert row["record_id"] == proposal_a.record_id
            assert replica.db.count_pending() == 0
        finally:
            replica.close()

    def test_identical_reprepare_is_idempotent(self, bb_root):
        from blackboard import BlackboardReplica

        replica = BlackboardReplica("replica_a", bb_root / "a.db")
        try:
            rec = draft().to_record()
            assert replica.prepare("op-x", rec).ack_status is AckStatus.ACK_PREPARED
            again = replica.prepare("op-y", rec)
            assert again.ack_status is AckStatus.ACK_PREPARED
            self._commit_direct(replica, "op-y", rec)
        finally:
            replica.close()

    def test_expired_lease_takeover(self, bb_root):
        from blackboard import BlackboardReplica
        from blackboard.hashing import canonical_json_str

        replica = BlackboardReplica("replica_a", bb_root / "a.db")
        try:
            stranded = draft(payload={"stale_writer": True}).to_record()
            replica.db.prepare_insert(
                record_key=stranded.record_key,
                record_version=stranded.record_version,
                record_id=stranded.record_id,
                content_hash=stranded.content_hash,
                operation_id="ancient-op",
                record_json=canonical_json_str(stranded.model_dump()),
                created_at_utc="2026-01-01T00:00:00Z",
                now_epoch=1.0,
                lease_seconds=300.0,
            )
            challenger = draft(payload={"challenger": True}).to_record()
            ack = replica.prepare("new-op", challenger)
            assert ack.ack_status is AckStatus.ACK_PREPARED
            assert "lease" in (ack.reason or "")
        finally:
            replica.close()
