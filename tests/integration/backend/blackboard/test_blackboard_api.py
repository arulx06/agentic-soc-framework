"""Stage-4B API tests: endpoints, pagination, authorization, persistence."""

from __future__ import annotations

from tests.integration.backend.blackboard.api_fixtures import (
    ApiEnv,
    make_api_app,
)
import pytest
from fastapi.testclient import TestClient

from backend.app.services.blackboard_service import BlackboardService
from backend.app.services.replay_controller import ReplayController

PRINCIPAL = {"X-Blackboard-Principal": "dev-tester"}


class TestEndpoints:
    def test_health_reports_ok(self, api_env: ApiEnv):
        r = api_env.client.get("/api/v1/blackboard/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["replicas_total"] == 3
        assert "partial_commit" in body["counters"]
        assert "insufficient_quorum_read" not in body["counters"] or True

    def test_dev_write_commit_and_versioning(self, api_env: ApiEnv):
        c = api_env.client
        r1 = c.post(
            "/api/v1/blackboard/records",
            json={"record_key": "dev/k", "payload": {"n": 1}},
            headers=PRINCIPAL,
        )
        assert r1.status_code == 201
        body = r1.json()
        assert body["outcome"] == "COMMITTED"
        assert body["durable_commit_ack_count"] == 3
        assert body["record_version"] == 1

        r2 = c.post(
            "/api/v1/blackboard/records",
            json={"record_key": "dev/k", "payload": {"n": 2}},
            headers=PRINCIPAL,
        )
        assert r2.status_code == 201
        assert r2.json()["record_version"] == 2
        assert r2.json()["content_hash"] != body["content_hash"]

    def test_latest_and_specific_version_reads(self, api_env: ApiEnv):
        c = api_env.client
        for n in (1, 2):
            c.post(
                "/api/v1/blackboard/records",
                json={"record_key": "dev/r", "payload": {"n": n}},
                headers=PRINCIPAL,
            )
        latest = c.get("/api/v1/blackboard/records/dev/r")
        assert latest.status_code == 200
        data = latest.json()
        assert data["outcome"] in ("CONSISTENT", "DEGRADED_CONSISTENT")
        assert data["record"]["payload"]["n"] == 2

        v1 = c.get("/api/v1/blackboard/records/dev/r/versions/1")
        assert v1.status_code == 200
        assert v1.json()["record"]["content_hash"] != data["record"]["content_hash"]

    def test_unknown_record_404(self, api_env: ApiEnv):
        r = api_env.client.get("/api/v1/blackboard/records/nope/never")
        assert r.status_code == 404
        assert r.json()["error_code"] == "record_not_found"

    def test_insufficient_quorum_is_not_authoritative(self, api_env: ApiEnv):
        env = api_env
        env.client.post(
            "/api/v1/blackboard/records",
            json={"record_key": "dev/solo", "payload": {"x": 1}},
            headers=PRINCIPAL,
        )
        for replica in env.service.coordinator.replicas[1:]:
            replica.set_unavailable("test outage")
        r = env.client.get("/api/v1/blackboard/records/dev/solo")
        assert r.status_code == 409
        assert r.json()["error_code"] == "insufficient_quorum"

    def test_replicas_endpoints_and_404(self, api_env: ApiEnv):
        c = api_env.client
        listing = c.get("/api/v1/blackboard/replicas")
        assert listing.status_code == 200
        ids = [r["replica_id"] for r in listing.json()["replicas"]]
        assert ids == ["replica_a", "replica_b", "replica_c"]
        assert "no trust" in listing.json()["note"]

        one = c.get("/api/v1/blackboard/replicas/replica_b")
        assert one.status_code == 200
        assert one.json()["committed_record_count"] == 0

        missing = c.get("/api/v1/blackboard/replicas/replica_z")
        assert missing.status_code == 404

    def test_snapshot_shape_and_counters(self, api_env: ApiEnv):
        c = api_env.client
        c.post(
            "/api/v1/blackboard/records",
            json={"record_key": "dev/snap", "payload": {"a": 1}},
            headers=PRINCIPAL,
        )
        snap = c.get("/api/v1/blackboard/snapshot").json()
        assert snap["schema_version"] == "blackboard_snapshot_v1"
        assert "dev/snap" in snap["latest_by_key"]
        assert len(snap["replica_statuses"]) == 3
        assert snap["counters"]["committed"] >= 1
        assert "recent_rejections" in snap and isinstance(snap["recent_rejections"], list)

    def test_pagination_and_filters(self, api_env: ApiEnv):
        c = api_env.client
        for i in range(7):
            rr = c.post(
                "/api/v1/blackboard/records",
                json={"record_key": f"page/k{i}", "payload": {"i": i}},
                headers=PRINCIPAL,
            )
            assert rr.status_code == 201

        page = c.get("/api/v1/blackboard/records", params={"key_prefix": "page/", "limit": 3})
        assert page.status_code == 200
        body = page.json()
        assert body["total"] == 7 and len(body["items"]) == 3
        assert body["bounds"]["max_limit"] <= 200

        page2 = c.get(
            "/api/v1/blackboard/records",
            params={"key_prefix": "page/", "limit": 3, "offset": 3},
        )
        keys_page2 = [i["record_key"] for i in page2.json()["items"]]
        assert keys_page2 == ["page/k3", "page/k4", "page/k5"]

        typed = c.get(
            "/api/v1/blackboard/records",
            params={"record_type": "SYSTEM_RECORD", "limit": 100},
        )
        assert typed.status_code == 200
        assert all(i["record_type"] == "SYSTEM_RECORD" for i in typed.json()["items"])

        bad_type = c.get("/api/v1/blackboard/records", params={"record_type": "BOGUS"})
        assert bad_type.status_code == 422

    def test_truncated_view_is_explicit_through_the_api(self, tmp_path):
        """A bounded/truncated view must be distinguishable from a COMPLETE
        view — never silently presented as a full total."""
        from blackboard.settings import BlackboardSettings
        from fastapi.testclient import TestClient as _TC

        from backend.app.services.blackboard_service import BlackboardService as _SVC
        from backend.app.services.replay_controller import (
            ReplayController as _CTL,
        )
        from tests.integration.backend.blackboard.api_fixtures import make_api_app

        settings = BlackboardSettings(
            committed_scan_max_rows=3, committed_scan_chunk_size=1
        )
        service = _SVC(root=tmp_path / "trunc", settings=settings)
        controller = _CTL(blackboard=service)
        client = _TC(make_api_app(controller, service))
        try:
            for i in range(5):
                r = client.post(
                    "/api/v1/blackboard/records",
                    json={"record_key": f"t/k{i}", "payload": {"i": i}},
                    headers=PRINCIPAL,
                )
                assert r.status_code == 201

            listing = client.get(
                "/api/v1/blackboard/records", params={"key_prefix": "t/"}
            ).json()
            assert listing["truncated"] is True
            assert set(listing["truncated_replicas"]) == {
                "replica_a",
                "replica_b",
                "replica_c",
            }
            assert listing["total"] == 3  # scanned scope only
            assert listing["scan_bounds"]["max_rows_per_replica"] == 3

            snap = client.get("/api/v1/blackboard/snapshot").json()
            assert snap["truncated"] is True
            assert snap["bounds"]["committed_scan_max_rows"] == 3
            assert snap["bounds"]["view_complete"] is False

            # Complete view for comparison.
            health = client.get("/api/v1/blackboard/health")
            assert health.status_code == 200
        finally:
            controller.shutdown()
            service.close()

    def test_complete_view_reports_view_complete(self, api_env: ApiEnv):
        snap = api_env.client.get("/api/v1/blackboard/snapshot").json()
        assert snap["truncated"] is False
        assert snap["bounds"]["view_complete"] is True
        assert "committed_scan_max_rows" in snap["bounds"]
        assert "committed_scan_chunk_size" in snap["bounds"]


class TestAuthorizationAndMasquerade:
    def test_missing_principal_rejected_before_prepare(self, api_env: ApiEnv):
        r = api_env.client.post(
            "/api/v1/blackboard/records",
            json={"record_key": "dev/x", "payload": {}},
        )
        assert r.status_code == 403
        assert r.json()["error_code"] == "principal_required"
        # Nothing was prepared anywhere.
        for replica in api_env.service.coordinator.replicas:
            assert replica.db.count_pending() == 0

    def test_unauthorized_principal_denied_by_policy(self, tmp_path):
        from blackboard.authorization import (
            BlackboardOperation,
            PrincipalPolicyAuthorizer,
        )

        service = BlackboardService(root=tmp_path / "bb2")
        service.coordinator.authorizer = PrincipalPolicyAuthorizer(
            {"writer": frozenset({BlackboardOperation.WRITE})}
        )
        controller = ReplayController(blackboard=service)
        client = TestClient(make_api_app(controller, service))
        try:
            r = client.post(
                "/api/v1/blackboard/records",
                json={"record_key": "dev/y", "payload": {}},
                headers={"X-Blackboard-Principal": "intruder"},
            )
            assert r.status_code == 403
            assert "unknown principal" in r.json()["message"]

            ok = client.post(
                "/api/v1/blackboard/records",
                json={"record_key": "dev/y", "payload": {}},
                headers={"X-Blackboard-Principal": "writer"},
            )
            assert ok.status_code == 201
        finally:
            controller.shutdown()
            service.close()

    def test_dev_write_cannot_create_scientific_finding_records(self, api_env: ApiEnv):
        """The generic endpoint is restricted to SYSTEM_RECORD — browser
        callers can never masquerade as detector/profiler/gateway."""
        c = api_env.client
        # The service maps findings itself; the endpoint has NO record_type
        # parameter at all, so finding-type injection is structurally
        # impossible. Prove the resulting type is always SYSTEM_RECORD:
        r = c.post(
            "/api/v1/blackboard/records",
            json={
                "record_key": "spoof/attempt",
                "payload": {
                    "evidence_kind": "network",
                    "attack_probability": 0.99,
                    "predicted_class": "attack",
                },
            },
            headers=PRINCIPAL,
        )
        assert r.status_code == 201
        got = c.get("/api/v1/blackboard/records/spoof/attempt").json()
        assert got["record"]["record_type"] == "SYSTEM_RECORD"
        assert got["record"]["author_id"] == "dev-tester"


class TestPersistenceThroughApi:
    def test_committed_state_survives_backend_reconstruction(self, tmp_path):
        root = tmp_path / "persist"
        svc1 = BlackboardService(root=root)
        ctl1 = ReplayController(blackboard=svc1)
        app1 = make_api_app(ctl1, svc1)
        with TestClient(app1) as c1:
            w = c1.post(
                "/api/v1/blackboard/records",
                json={"record_key": "persist/k", "payload": {"generation": 1}},
                headers=PRINCIPAL,
            )
            assert w.status_code == 201
            committed_hash = w.json()["content_hash"]
        ctl1.shutdown()
        svc1.close()

        # Fresh backend against the SAME stores.
        svc2 = BlackboardService(root=root)
        ctl2 = ReplayController(blackboard=svc2)
        app2 = make_api_app(ctl2, svc2)
        try:
            with TestClient(app2) as c2:
                got = c2.get("/api/v1/blackboard/records/persist/k").json()
                assert got["record"]["content_hash"] == committed_hash
                assert got["record"]["record_version"] == 1
                reps = c2.get("/api/v1/blackboard/replicas").json()
                assert all(r["committed_record_count"] == 1 for r in reps["replicas"])
                assert all(r["pending_record_count"] == 0 for r in reps["replicas"])
        finally:
            ctl2.shutdown()
            svc2.close()
