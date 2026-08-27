from __future__ import annotations

from .conftest import request_body


HEADERS = {"X-Orchestration-Principal": "development-researcher"}


def test_post_returns_versioned_decision_without_executing_route(api_env):
    client, _controller, _service = api_env
    response = client.post(
        "/api/v1/orchestration/requests", json=request_body(), headers=HEADERS
    )
    assert response.status_code == 201
    body = response.json()
    assert body["schema_version"] == "orchestration_decision_v1"
    assert body["outcome"] == "DECIDED"
    assert body["selected_route_id"] == "route_alpha"
    assert body["provenance"]["caller_identity_assumption"] == (
        "application_audit_identity_not_http_authentication"
    )
    assert "execution" not in body
    assert "enforcement_action" not in body


def test_principal_is_required_before_request_or_event_mutation(api_env):
    client, controller, service = api_env
    response = client.post("/api/v1/orchestration/requests", json=request_body())
    assert response.status_code == 403
    assert response.json()["error_code"] == "principal_required"
    assert service.list_decisions(
        outcome=None, request_id=None, limit=10, offset=0, max_limit=200
    ).total_retained == 0
    assert len(controller.broker) == 0


def test_invalid_version_and_nested_ground_truth_are_rejected_without_events(api_env):
    client, controller, service = api_env
    wrong_version = request_body()
    wrong_version["schema_version"] = "orchestration_request_v2"
    assert client.post(
        "/api/v1/orchestration/requests", json=wrong_version, headers=HEADERS
    ).status_code == 422
    leaking = request_body()
    leaking["provenance"] = {"nested": [{"scenario_id": "evaluation-secret"}]}
    response = client.post(
        "/api/v1/orchestration/requests", json=leaking, headers=HEADERS
    )
    assert response.status_code == 422
    assert "ground-truth leakage" in response.json()["message"]
    assert len(controller.broker) == 0
    assert len(service._decisions) == 0


def test_health_replica_detail_and_unknown_replica(api_env):
    client, _controller, _service = api_env
    health = client.get("/api/v1/orchestration/health").json()
    assert health["orchestrators_total"] == 3
    assert health["required_quorum"] == 2
    assert health["decision_history_persistent"] is False
    replicas = client.get("/api/v1/orchestration/replicas").json()["replicas"]
    assert [item["orchestrator_id"] for item in replicas] == [
        "orchestrator_a", "orchestrator_b", "orchestrator_c"
    ]
    assert client.get("/api/v1/orchestration/replicas/orchestrator_a").status_code == 200
    assert client.get("/api/v1/orchestration/replicas/replica_a").status_code == 404


def test_decision_listing_filters_paginates_and_is_explicitly_incomplete(api_env):
    client, _controller, _service = api_env
    for index in range(3):
        response = client.post(
            "/api/v1/orchestration/requests",
            json=request_body(f"api-request-{index}", f"api-round-{index}"),
            headers=HEADERS,
        )
        assert response.status_code == 201
    listing = client.get(
        "/api/v1/orchestration/decisions?outcome=DECIDED&limit=1&offset=1"
    ).json()
    assert listing["schema_version"] == "orchestration_decision_listing_v1"
    assert listing["total_retained"] == 3
    assert len(listing["decisions"]) == 1
    assert listing["history_complete"] is False
    decision_id = listing["decisions"][0]["decision_id"]
    assert client.get(f"/api/v1/orchestration/decisions/{decision_id}").status_code == 200
    assert client.get("/api/v1/orchestration/decisions/unknown").status_code == 404


def test_list_limit_is_bounded_by_transport_contract(api_env):
    client, _controller, _service = api_env
    response = client.get("/api/v1/orchestration/decisions?limit=201")
    assert response.status_code == 422


def test_duplicate_round_is_rejected_before_a_second_request_event(api_env):
    client, controller, _service = api_env
    assert client.post(
        "/api/v1/orchestration/requests", json=request_body(), headers=HEADERS
    ).status_code == 201
    before = len(controller.broker)
    duplicate = client.post(
        "/api/v1/orchestration/requests", json=request_body(), headers=HEADERS
    )
    assert duplicate.status_code == 409
    assert len(controller.broker) == before
