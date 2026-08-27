"""Persistence: committed state survives restart; pending/aborted never
become committed."""

from __future__ import annotations

from blackboard.contracts import AckStatus, WriteOutcome
from tests.unit.blackboard.helpers import draft, make_coordinator


class TestRestartSemantics:
    def test_committed_records_survive_coordinator_restart(self, bb_root):
        coord1 = make_coordinator(bb_root)
        results = {}
        for v in (1, 2):
            r = coord1.propose(draft(version=v), "system")
            assert r.outcome is WriteOutcome.COMMITTED
            results[v] = r.content_hash
        coord1.close()

        coord2 = make_coordinator(bb_root)
        try:
            latest = coord2.read_latest("reader", "device_state:dev1")
            assert latest.outcome.value == "CONSISTENT"
            assert latest.record.record_version == 2
            assert latest.record.content_hash == results[2]
            assert latest.record.payload == {"entity_id": "dev1", "network_risk": 0.25}

            first = coord2.read_version("reader", "device_state:dev1", 1)
            assert first.record.content_hash == results[1]
        finally:
            coord2.close()

    def test_pending_staging_never_becomes_committed_after_restart(self, bb_root):
        coord1 = make_coordinator(bb_root)
        committed = coord1.propose(draft(), "system")
        assert committed.outcome is WriteOutcome.COMMITTED

        # Stage a proposal at the next slot directly on replica_a only.
        stranded = draft(version=2, payload={"stranded": True}).to_record()
        ack = coord1.replicas[0].prepare("op-stranded", stranded)
        assert ack.ack_status is AckStatus.ACK_PREPARED
        coord1.close()

        coord2 = make_coordinator(bb_root)
        try:
            # Still not visible as committed anywhere.
            rd = coord2.read_latest("reader", "device_state:dev1")
            assert rd.record.record_version == 1

            # A conflicting challenger CANNOT silently overwrite the staging
            # on replica_a — but the 2-of-3 policy lets b+c commit globally,
            # which leaves replica_a explicitly behind, never corrupted.
            blocked = coord2.propose(
                draft(version=2, payload={"challenger": True}), "system"
            )
            assert blocked.outcome is WriteOutcome.COMMITTED
            assert blocked.replica_sync["replica_a"] == "NOT_PREPARED"

            replica_a = coord2.replicas[0]
            assert replica_a.get_committed_row("device_state:dev1", 2) is None
            assert replica_a.db.count_pending() == 1

            rd2 = coord2.read_latest("reader", "device_state:dev1")
            assert rd2.outcome.value == "DEGRADED_CONSISTENT"
            assert rd2.divergent_replicas == ("replica_a",)

            # Explicit repair brings replica_a to the majority value and
            # clears the stranded staging.
            report = coord2.resync_replicas_from_majority("admin", "device_state:dev1")
            assert report["status"] in {"REPAIRED", "PARTIAL"}
            assert replica_a.db.count_pending() == 0
            head = replica_a.get_committed_row("device_state:dev1", 2)
            assert head["record_id"] == blocked.record_id

            rd3 = coord2.read_latest("reader", "device_state:dev1")
            assert rd3.outcome.value == "CONSISTENT"
        finally:
            coord2.close()

    def test_aborted_proposals_stay_aborted_after_restart(self, bb_root):
        coord1 = make_coordinator(bb_root)
        rec = draft(key="abort:case").to_record()
        assert coord1.replicas[0].prepare("op-abort-me", rec).ack_status is AckStatus.ACK_PREPARED
        abort_ack = coord1.replicas[0].abort("op-abort-me", rec.record_key, 1)
        assert abort_ack.ack_status is AckStatus.ABORTED
        assert coord1.replicas[0].db.count_pending() == 0
        coord1.close()

        coord2 = make_coordinator(bb_root)
        try:
            rd = coord2.read_latest("reader", "abort:case")
            assert rd.outcome.value == "NOT_FOUND"
            # Key is writable after restart.
            result = coord2.propose(draft(key="abort:case"), "system")
            assert result.outcome is WriteOutcome.COMMITTED
        finally:
            coord2.close()

    def test_failed_quorum_leaves_no_committed_partial_state_after_restart(
        self, bb_root
    ):
        from tests.unit.blackboard.helpers import UnavailableOnPrepareHooks

        hooks = UnavailableOnPrepareHooks({"replica_b", "replica_c"})
        coord1 = make_coordinator(bb_root, hooks=hooks)
        failed = coord1.propose(draft(), "system")
        assert failed.outcome is WriteOutcome.FAILED_QUORUM
        coord1.close()

        coord2 = make_coordinator(bb_root)
        try:
            for replica in coord2.replicas:
                assert replica.db.count_committed() == 0
                assert replica.db.count_pending() == 0
            assert coord2.read_latest("system", "device_state:dev1").outcome.value == "NOT_FOUND"

            retry = coord2.propose(draft(), "system")
            assert retry.outcome is WriteOutcome.COMMITTED
        finally:
            coord2.close()
