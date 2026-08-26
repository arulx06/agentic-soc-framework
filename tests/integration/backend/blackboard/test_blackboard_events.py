"""Stage-4B event integration: real ACKs/commits emit real BLACKBOARD_*
events through the Stage-3 envelope, with corrected Stage-4A outcome
fidelity (PARTIAL_COMMIT never masquerades as COMMITTED)."""

from __future__ import annotations

import pytest

import pytest
from fastapi.testclient import TestClient

from blackboard.contracts import AckStatus
from backend.app.contracts.events_v1 import EventEnvelopeV1
from backend.app.services.blackboard_service import BlackboardService
from backend.app.services.replay_controller import ReplayController
from tests.integration.backend.blackboard.api_fixtures import (
    ApiEnv,
    make_api_app,
)
from tests.unit.blackboard.helpers import (
    FailOnCommitHooks,
    UnavailableOnPrepareHooks,
    draft,
)

PRINCIPAL = {"X-Blackboard-Principal": "dev-tester"}


def _make_env(tmp_path, name):
    service = BlackboardService(root=tmp_path / name)
    controller = ReplayController(blackboard=service)
    client = TestClient(make_api_app(controller, service))
    return client, controller, service


def _ring(env: ApiEnv, replay_id: str | None = None):
    ring = env.drain_ring()
    if replay_id is None:
        return list(ring)
    return [e for e in ring if e.replay_id == replay_id]


def _types(events):
    return [e.event_type.value for e in events]


def _validate_envelopes(events):
    for e in events:
        clone = EventEnvelopeV1.model_validate(e.model_dump())
        assert clone.sequence_number >= 0


class TestCommittedEventPath:
    def test_proposed_acks_committed_share_one_chronology(self, api_env: ApiEnv):
        c = api_env.client
        w = c.post(
            "/api/v1/blackboard/records",
            json={"record_key": "ev/k", "payload": {"n": 1}},
            headers=PRINCIPAL,
        )
        assert w.status_code == 201
        op_id = w.json()["operation_id"]

        events = _ring(api_env, "blackboard-ops")
        _validate_envelopes(events)

        seqs = [e.sequence_number for e in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)

        proposed = [
            e for e in events if e.event_type.value == "BLACKBOARD_WRITE_PROPOSED"
        ]
        acks = [
            e
            for e in events
            if e.event_type.value == "BLACKBOARD_REPLICA_ACK"
            and e.payload["operation_id"] == op_id
        ]
        committed = [
            e
            for e in events
            if e.event_type.value == "BLACKBOARD_WRITE_COMMITTED"
            and e.payload["operation_id"] == op_id
        ]

        assert len(proposed) == 1 and proposed[0].payload["record_key"] == "ev/k"
        assert len(acks) == 3
        assert {a.payload["replica_id"] for a in acks} == {
            "replica_a",
            "replica_b",
            "replica_c",
        }
        assert all(a.payload["ack_status"] == "ACK_PREPARED" for a in acks)
        assert len(committed) == 1

        # Deterministic emission policy: PROPOSED -> 3 real ACKs -> COMMITTED.
        order = [e.event_type.value for e in events if e.payload.get("operation_id") in (op_id, None)]
        assert order.index("BLACKBOARD_WRITE_PROPOSED") < min(
            i for i, t in enumerate(order) if t == "BLACKBOARD_REPLICA_ACK"
        )
        commit_idx = order.index("BLACKBOARD_WRITE_COMMITTED")
        assert commit_idx > max(
            i for i, t in enumerate(order) if t == "BLACKBOARD_REPLICA_ACK"
        )

        body = committed[0].payload
        assert body["ack_count"] == 3
        assert body["required_quorum"] == 2
        assert body["author_id"] == "dev-tester"
        assert body["commit_latency_ms"] >= 0
        assert {a["replica_id"] for a in body["acknowledgements"]} == {
            "replica_a",
            "replica_b",
            "replica_c",
        }


class TestFailureEventPaths:
    def test_stale_write_emits_stale_event(self, api_env: ApiEnv):
        c = api_env.client
        c.post(
            "/api/v1/blackboard/records",
            json={"record_key": "stale/k", "payload": {"v": 1}},
            headers=PRINCIPAL,
        )
        # An explicitly stale proposal (head is already 1) via the service's
        # explicit-version path; auto-versioned writes never go stale.
        stale_draft = draft(key="stale/k", version=1, payload={"v": "old"}).to_record()
        result = api_env.service.propose_explicit(stale_draft, "dev-tester")
        assert result.outcome.value == "REJECTED_STALE"

        events = _ring(api_env, "blackboard-ops")
        stale_events = [e for e in events if e.event_type.value == "BLACKBOARD_STALE_WRITE"]
        assert len(stale_events) == 1
        assert stale_events[0].payload["outcome"] == "REJECTED_STALE"
        assert "current committed version" in stale_events[0].payload["reason"]

    def test_conflict_emits_conflict_event(self, api_env: ApiEnv):
        svc = api_env.service
        coord = svc.coordinator
        occupant = draft(key="conflict/k", payload={"holder": True}).to_record()
        for replica in coord.replicas:
            ack = replica.prepare("op-holder", occupant)
            assert ack.ack_status is AckStatus.ACK_PREPARED

        r = api_env.client.post(
            "/api/v1/blackboard/records",
            json={"record_key": "conflict/k", "payload": {"challenger": True}},
            headers=PRINCIPAL,
        )
        assert r.status_code == 409
        assert r.json()["error_code"] == "write_rejected_conflict"

        events = _ring(api_env, "blackboard-ops")
        conflicts = [e for e in events if e.event_type.value == "BLACKBOARD_CONFLICT"]
        assert len(conflicts) == 1
        assert conflicts[0].payload["outcome"] == "REJECTED_CONFLICT"

    def test_quorum_failure_emits_quorum_failed_and_aborted(self, tmp_path):
        client, controller, service = _make_env(tmp_path, "bbq")
        hooks = UnavailableOnPrepareHooks({"replica_b", "replica_c"})
        for replica in service.coordinator.replicas:
            replica.hooks = hooks
        try:
            r = client.post(
                "/api/v1/blackboard/records",
                json={"record_key": "qf/k", "payload": {"x": 1}},
                headers=PRINCIPAL,
            )
            assert r.status_code == 503
            assert r.json()["error_code"] == "quorum_failed"

            events = [e for e in controller.broker._ring if e.replay_id == "blackboard-ops"]
            types = _types(events)
            assert "BLACKBOARD_QUORUM_FAILED" in types
            assert "BLACKBOARD_WRITE_ABORTED" in types
            quorum = next(
                e for e in events if e.event_type.value == "BLACKBOARD_QUORUM_FAILED"
            )
            assert quorum.payload["outcome"] == "FAILED_QUORUM"
            aborted = next(
                e for e in events if e.event_type.value == "BLACKBOARD_WRITE_ABORTED"
            )
            assert aborted.payload["aborted_replicas"] == ["replica_a"]
            assert "BLACKBOARD_WRITE_COMMITTED" not in types
        finally:
            controller.shutdown()
            service.close()

    def test_partial_commit_never_emits_write_committed(self, tmp_path):
        """Stage-4A corrective fidelity at the EVENT layer: exactly one
        durable commit => BLACKBOARD_WRITE_PARTIAL only."""
        client, controller, service = _make_env(tmp_path, "bbp")
        hooks = FailOnCommitHooks({"replica_b", "replica_c"})
        for replica in service.coordinator.replicas:
            replica.hooks = hooks
        try:
            r = client.post(
                "/api/v1/blackboard/records",
                json={"record_key": "partial/k", "payload": {"x": 1}},
                headers=PRINCIPAL,
            )
            assert r.status_code == 201
            body = r.json()
            assert body["outcome"] == "PARTIAL_COMMIT"
            assert body["durable_commit_ack_count"] == 1
            assert body["replica_sync"]["replica_a"] == "SYNCED"

            events = [e for e in controller.broker._ring if e.replay_id == "blackboard-ops"]
            types = _types(events)
            assert "BLACKBOARD_WRITE_PARTIAL" in types
            assert "BLACKBOARD_WRITE_COMMITTED" not in types
            partial = next(
                e for e in events if e.event_type.value == "BLACKBOARD_WRITE_PARTIAL"
            )
            assert partial.payload["ack_count"] == 1
            assert partial.payload["required_quorum"] == 2
            assert partial.payload["replica_sync"]["replica_b"] == (
                "DIVERGENT_REQUIRES_RECONCILIATION"
            )
        finally:
            controller.shutdown()
            service.close()


class TestReadEvents:
    def test_read_and_inconsistent_read_events(self, api_env: ApiEnv):
        c = api_env.client
        c.get("/api/v1/blackboard/records/read/missing")

        events = _ring(api_env, "blackboard-ops")
        reads = [e for e in events if e.event_type.value == "BLACKBOARD_READ"]
        assert len(reads) == 1
        assert reads[0].payload["outcome"] == "NOT_FOUND"
        assert len(reads[0].payload["observations"]) == 3

        # Two disagreeing replicas + one unavailable -> INCONSISTENT read.
        from tests.unit.blackboard.helpers import draft as bb_draft

        coord = api_env.service.coordinator
        rec_a = bb_draft(key="inc/k", payload={"w": "a"}).to_record()
        rec_c = bb_draft(key="inc/k", payload={"w": "c"}).to_record()
        for replica, rec, op in ((coord.replicas[0], rec_a, "op-a"), (coord.replicas[2], rec_c, "op-c")):
            assert replica.prepare(op, rec).ack_status is AckStatus.ACK_PREPARED
            assert replica.commit(op, rec).ack_status is AckStatus.ACK_COMMITTED
        coord.replicas[1].set_unavailable("outage")

        got = c.get("/api/v1/blackboard/records/inc/k")
        assert got.status_code == 409
        assert got.json()["error_code"] == "inconsistent_read"

        events = _ring(api_env, "blackboard-ops")
        bad = [
            e for e in events if e.event_type.value == "BLACKBOARD_READ_INCONSISTENT"
        ]
        assert len(bad) == 1
        assert bad[0].payload["outcome"] == "INCONSISTENT"


class TestDisabledIntegration:
    def test_disabled_service_returns_structured_503(self, tmp_path):
        service = BlackboardService(root=tmp_path / "off", enabled=False)
        controller = ReplayController(blackboard=service)
        client = TestClient(make_api_app(controller, service))
        try:
            r = client.get("/api/v1/blackboard/health")
            assert r.status_code == 503
            assert r.json()["error_code"] == "blackboard_disabled"
        finally:
            controller.shutdown()
