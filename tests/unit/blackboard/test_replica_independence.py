"""Replica independence: three genuinely separate state machines and stores."""

from __future__ import annotations

import sqlite3

import pytest

from blackboard import BlackboardReplica, ReplicaHealth
from tests.unit.blackboard.helpers import draft


def _stage_and_commit(replica: BlackboardReplica, op: str, rec) -> None:
    ack = replica.prepare(op, rec)
    assert ack.ack_status.value == "ACK_PREPARED"
    cack = replica.commit(op, rec)
    assert cack.ack_status.value == "ACK_COMMITTED"


class TestPhysicalIndependence:
    def test_three_distinct_sqlite_files(self, bb_root):
        replicas = [
            BlackboardReplica(rid, bb_root / f"{rid}.db")
            for rid in ("replica_a", "replica_b", "replica_c")
        ]
        for r in replicas:
            assert r.db.db_path.is_file()
        paths = {r.db.db_path for r in replicas}
        assert len(paths) == 3
        for r in replicas:
            r.close()

    def test_separate_connections_and_locks(self, bb_root):
        replicas = [BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in
                    ("replica_a", "replica_b", "replica_c")]
        assert len({id(r.db) for r in replicas}) == 3
        conns = [r.db._conn for r in replicas]
        assert all(isinstance(c, sqlite3.Connection) for c in conns)
        assert len({id(c) for c in conns}) == 3
        for r in replicas:
            r.close()

    def test_replica_identity_persisted_per_store(self, bb_root):
        replicas = [BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in
                    ("replica_a", "replica_b")]
        try:
            for r in replicas:
                marker = r.db._conn.execute(
                    "SELECT v FROM meta WHERE k='replica_id'"
                ).fetchone()
                assert marker["v"] == r.replica_id
        finally:
            for r in replicas:
                r.close()


class TestStateIndependence:
    def test_commit_on_one_replica_invisible_to_others(self, bb_root):
        a, b, c = (BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in
                   ("replica_a", "replica_b", "replica_c"))
        try:
            rec = draft().to_record()
            _stage_and_commit(a, "op-ind-1", rec)
            assert a.get_committed_row("device_state:dev1") is not None
            assert b.get_committed_row("device_state:dev1") is None
            assert c.get_committed_row("device_state:dev1") is None
            assert a.db.count_committed() == 1
            assert b.db.count_committed() == 0
            assert c.db.count_committed() == 0
        finally:
            for r in (a, b, c):
                r.close()

    def test_operational_counters_do_not_alias(self, bb_root):
        a, b = (BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in
                ("replica_a", "replica_b"))
        try:
            rec = draft().to_record()
            a.prepare("op-cnt-1", rec)
            assert a.prepared_count == 1
            assert b.prepared_count == 0
        finally:
            a.close()
            b.close()

    def test_health_mutation_isolated(self, bb_root):
        a, b = (BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in
                ("replica_a", "replica_b"))
        try:
            a.mark_diverged("unit-test divergence")
            assert a.health is ReplicaHealth.DIVERGED
            assert b.health is ReplicaHealth.HEALTHY
            a.set_unavailable("maintenance")
            assert a.health is ReplicaHealth.UNAVAILABLE
            assert b.health is ReplicaHealth.HEALTHY
        finally:
            a.close()
            b.close()

    def test_divergence_history_bounded_and_private(self, bb_root):
        a, b = (BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in
                ("replica_a", "replica_b"))
        try:
            for i in range(20):
                a.mark_diverged(f"d{i}")
            assert len(a.divergence_history) == 16  # default bound
            assert a.divergence_history[-1] == "d19"
            assert b.divergence_history == ()
        finally:
            a.close()
            b.close()


class TestCoordinatorRequiresThree:
    def test_rejects_two_replicas(self, bb_root):
        from blackboard import BlackboardCoordinator

        reps = [BlackboardReplica("replica_a", bb_root / "a.db")]
        with pytest.raises(ValueError, match="exactly three"):
            BlackboardCoordinator(reps)

    def test_rejects_duplicate_ids(self, bb_root):
        from blackboard import BlackboardCoordinator

        reps = [BlackboardReplica("replica_a", bb_root / f"a{i}.db") for i in range(3)]
        with pytest.raises(ValueError, match="unique"):
            BlackboardCoordinator(reps)

    @pytest.mark.parametrize("rids", [("replica_a", "replica_b", "replica_c")])
    def test_accepts_exactly_three(self, bb_root, rids):
        from blackboard import BlackboardCoordinator

        coord = BlackboardCoordinator(
            [BlackboardReplica(rid, bb_root / f"{rid}.db") for rid in rids]
        )
        try:
            assert coord.replica_ids == rids
        finally:
            coord.close()
