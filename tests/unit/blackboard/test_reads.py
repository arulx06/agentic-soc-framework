"""Read-consistency semantics across the three replicas."""

from __future__ import annotations

from blackboard import BlackboardReplica, ReplicaHealth
from blackboard.contracts import AckStatus, ReadOutcome
from tests.unit.blackboard.helpers import draft, make_coordinator


def _commit_direct(replica: BlackboardReplica, op: str, rec) -> None:
    assert replica.prepare(op, rec).ack_status is AckStatus.ACK_PREPARED
    assert replica.commit(op, rec).ack_status is AckStatus.ACK_COMMITTED


class TestReadOutcomes:
    def test_not_found_on_empty_board(self, coordinator):
        rd = coordinator.read_latest("reader", "missing:key")
        assert rd.outcome is ReadOutcome.NOT_FOUND
        assert rd.record is None
        assert len(rd.observations) == 3
        assert all(not o.found for o in rd.observations)

    def test_consistent_full_agreement(self, coordinator):
        coordinator.propose(draft(version=1), "system")
        coordinator.propose(draft(version=2), "system")
        rd = coordinator.read_latest("reader", "device_state:dev1")
        assert rd.outcome is ReadOutcome.CONSISTENT
        assert rd.reason is None
        assert rd.record.record_version == 2
        assert rd.divergent_replicas == ()
        assert rd.unavailable_replicas == ()

    def test_degraded_with_one_replica_unavailable(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            coord.propose(draft(), "system")
            coord.replicas[2].set_unavailable("down")
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.DEGRADED_CONSISTENT
            assert rd.unavailable_replicas == ("replica_c",)
            assert rd.record is not None
        finally:
            coord.close()

    def test_not_found_with_partial_availability(self, bb_root):
        """Two absent confirmations meet quorum even with one replica down."""
        coord = make_coordinator(bb_root)
        try:
            coord.replicas[2].set_unavailable("down")
            rd = coord.read_latest("reader", "never:written")
            assert rd.outcome is ReadOutcome.NOT_FOUND
            assert rd.unavailable_replicas == ("replica_c",)
            assert rd.record is None
        finally:
            coord.close()

    def test_single_absence_is_insufficient_quorum(self, bb_root):
        """One 'absent' answer plus two unavailable replicas does NOT yield
        authoritative NOT_FOUND."""
        coord = make_coordinator(bb_root)
        try:
            coord.replicas[1].set_unavailable("down")
            coord.replicas[2].set_unavailable("down")
            rd = coord.read_latest("reader", "never:written")
            assert rd.outcome is ReadOutcome.INSUFFICIENT_QUORUM
            assert rd.record is None
            assert len(rd.unavailable_replicas) == 2
        finally:
            coord.close()

    def test_divergent_minority_detected_and_marked(self, bb_root):
        """One replica holding a different committed value at the head slot
        yields DEGRADED_CONSISTENT with explicit divergent marking."""
        coord = make_coordinator(bb_root)
        try:
            result = coord.propose(draft(), "system")
            assert result.outcome.value == "COMMITTED"

            # Force a missed commit on replica_b for version 2.
            coord.replicas[1].set_unavailable("simulated outage")
            v2 = coord.propose(draft(version=2), "system")
            assert v2.outcome.value == "COMMITTED"
            coord.replicas[1].set_available()
            assert coord.replicas[1].health is not ReplicaHealth.UNAVAILABLE

            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.DEGRADED_CONSISTENT
            assert rd.divergent_replicas == ("replica_b",)
            assert rd.record.record_version == 2
            assert coord.replicas[1].health is ReplicaHealth.DIVERGED
        finally:
            coord.close()

    def test_three_way_divergence_is_inconsistent(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            replicas = coord.replicas
            for i, (replica, value) in enumerate(
                zip(replicas, ("one", "two", "three"))
            ):
                rec = draft(
                    payload={"entity_id": "dev1", "writer": value}, version=1
                ).to_record()
                _commit_direct(replica, f"op-div-{i}", rec)

            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.INCONSISTENT
            assert rd.record is None
            assert len(rd.divergent_replicas) >= 2
        finally:
            coord.close()

    def test_single_responder_is_insufficient_quorum(self, bb_root):
        """A single responsive replica is NEVER consistent — its value must
        not be returned as authoritative Blackboard state."""
        coord = make_coordinator(bb_root)
        try:
            coord.propose(draft(), "system")
            coord.replicas[1].set_unavailable("down")
            coord.replicas[2].set_unavailable("down")
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.INSUFFICIENT_QUORUM
            assert rd.record is None
            # The lone response remains visible as debug metadata only.
            found_obs = [o for o in rd.observations if o.found]
            assert len(found_obs) == 1
            assert len(rd.unavailable_replicas) == 2
        finally:
            coord.close()

    def test_two_disagreeing_replicas_are_inconsistent(self, bb_root):
        """Two responsive replicas that disagree → INCONSISTENT even though
        a strict numeric majority of responders exists."""
        coord = make_coordinator(bb_root)
        try:
            rec_a = draft(payload={"writer": "a"}, version=1).to_record()
            assert coord.replicas[0].prepare("op-x-a", rec_a).ack_status is AckStatus.ACK_PREPARED
            assert coord.replicas[0].commit("op-x-a", rec_a).ack_status is AckStatus.ACK_COMMITTED

            rec_c = draft(payload={"writer": "c"}, version=1).to_record()
            assert coord.replicas[2].prepare("op-x-c", rec_c).ack_status is AckStatus.ACK_PREPARED
            assert coord.replicas[2].commit("op-x-c", rec_c).ack_status is AckStatus.ACK_COMMITTED

            coord.replicas[1].set_unavailable("down")
            rd = coord.read_latest("reader", "device_state:dev1")
            assert rd.outcome is ReadOutcome.INCONSISTENT
            assert rd.record is None
        finally:
            coord.close()


class TestSpecificVersionReads:
    def test_read_exact_version(self, coordinator):
        for v in (1, 2, 3):
            coordinator.propose(draft(version=v), "system")
        got = coordinator.read_version("reader", "device_state:dev1", 2)
        assert got.outcome is ReadOutcome.CONSISTENT
        assert got.requested_version == 2
        assert got.record.record_version == 2

    def test_missing_version_not_found(self, coordinator):
        coordinator.propose(draft(version=1), "system")
        got = coordinator.read_version("reader", "device_state:dev1", 99)
        assert got.outcome is ReadOutcome.NOT_FOUND

    def test_reads_never_expose_pending_staging(self, bb_root):
        coord = make_coordinator(bb_root)
        try:
            rec = draft().to_record()
            staged = coord.replicas[0].prepare("op-never-committed", rec)
            assert staged.ack_status is AckStatus.ACK_PREPARED
            for replica in coord.replicas:
                row = replica.get_committed_row(rec.record_key)
                assert row is None
            rd = coord.read_latest("reader", rec.record_key)
            assert rd.outcome is ReadOutcome.NOT_FOUND
        finally:
            coord.close()


class TestAuthorizationOnReads:
    def test_denied_read_reports_authorization_rejected(self, bb_root):
        from blackboard.authorization import BlackboardOperation, PrincipalPolicyAuthorizer

        policy = PrincipalPolicyAuthorizer(
            {"reader": frozenset({BlackboardOperation.READ})}
        )
        coord = make_coordinator(bb_root, authorizer=policy)
        try:
            rd = coord.read_latest("intruder", "device_state:dev1")
            assert rd.outcome is ReadOutcome.AUTHORIZATION_REJECTED
            assert "unknown principal" in rd.reason
        finally:
            coord.close()
