from __future__ import annotations

from backend.app.config import ORCHESTRATION_OPS_RUN_ID
from backend.app.contracts.events_v1 import EventEnvelopeV1, ReplayEventType
from backend.app.services.replay_controller import _Run

from .conftest import request_body


HEADERS = {"X-Orchestration-Principal": "development-researcher"}


def orchestration_events(controller):
    return [
        event for event in controller.broker._ring
        if event.replay_id == ORCHESTRATION_OPS_RUN_ID
    ]


def test_real_event_trace_has_causal_chronology_and_strict_sequence(api_env):
    client, controller, _service = api_env
    assert client.post(
        "/api/v1/orchestration/requests", json=request_body(), headers=HEADERS
    ).status_code == 201
    events = orchestration_events(controller)
    types = [event.event_type for event in events]
    assert types[0] is ReplayEventType.ORCHESTRATION_REQUEST_RECEIVED
    assert types[-2:] == [
        ReplayEventType.ORCHESTRATION_QUORUM_REACHED,
        ReplayEventType.ORCHESTRATION_DECISION,
    ]
    proposal_indexes = [i for i, item in enumerate(types) if item is ReplayEventType.ORCHESTRATOR_PROPOSAL]
    vote_indexes = [i for i, item in enumerate(types) if item is ReplayEventType.ORCHESTRATOR_VOTE]
    assert proposal_indexes and vote_indexes
    assert max(proposal_indexes) < min(vote_indexes)
    sequences = [event.sequence_number for event in events]
    assert sequences == list(range(len(events)))
    assert all(EventEnvelopeV1.model_validate(event.model_dump()) for event in events)
    assert controller._runs == {}


def test_orchestration_ops_is_publicly_websocket_subscribable_without_fake_replay(api_env):
    client, controller, _service = api_env
    client.post("/api/v1/orchestration/requests", json=request_body(), headers=HEADERS)
    expected = orchestration_events(controller)
    assert controller.event_stream_exists("orchestration-ops") is True
    assert "orchestration-ops" not in controller._runs
    with client.websocket_connect("/api/v1/replays/orchestration-ops/events") as socket:
        received = [socket.receive_json() for _ in expected]
    assert [item["event_id"] for item in received] == [item.event_id for item in expected]
    assert all(item["replay_id"] == "orchestration-ops" for item in received)


def test_operational_and_scientific_replay_sequences_are_isolated(api_env):
    client, controller, _service = api_env
    run = _Run(
        replay_id="scientific-replay-1",
        scenario_id="internal-only",
        session_trace="opaque-trace",
        source_mode="processed",
    )
    controller._runs[run.replay_id] = run
    replay_event = controller._publish(run, ReplayEventType.REPLAY_CREATED, payload={})
    assert replay_event.sequence_number == 0
    assert run.sequence == 1
    client.post("/api/v1/orchestration/requests", json=request_body(), headers=HEADERS)
    events = orchestration_events(controller)
    assert events[0].sequence_number == 0
    assert run.sequence == 1
    next_replay = controller._publish(run, ReplayEventType.REPLAY_STARTED, payload={})
    assert next_replay.sequence_number == 1
    assert all(event.replay_id != run.replay_id for event in events)


def test_event_payloads_expose_hashes_not_hmac_secrets(api_env):
    client, controller, _service = api_env
    client.post("/api/v1/orchestration/requests", json=request_body(), headers=HEADERS)
    serialized = str([event.model_dump(mode="json") for event in orchestration_events(controller)])
    assert "message_hash" in serialized
    assert "authentication_verified" in serialized
    for secret_byte in ("61" * 32, "62" * 32, "63" * 32):
        assert secret_byte not in serialized
