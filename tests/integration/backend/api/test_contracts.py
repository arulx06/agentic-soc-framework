"""Contract validation tests (§21.1)."""

import pytest
from pydantic import ValidationError

from backend.app.contracts.common import (
    ApiErrorV1,
    find_ground_truth_violations,
)
from backend.app.contracts.device_state_v1 import DeviceStateV1
from backend.app.contracts.events_v1 import EventEnvelopeV1, ReplayEventType
from backend.app.contracts.graph_snapshot_v1 import (
    CommunicationGraphSnapshotV1,
    DeviceRiskGraphSnapshotV1,
)
from backend.app.contracts.replay_v1 import PacingSpeed, ReplayStatusV1, ReplayState
from backend.app.contracts.saved_snapshot_v1 import SavedReplaySnapshotV1
from backend.app.contracts.srep_snapshot_v1 import SrepSnapshotV1


def _envelope(**overrides):
    base = dict(
        replay_id="r1",
        event_id="r1-0",
        sequence_number=0,
        event_type=ReplayEventType.WINDOW_STARTED,
        source_component="test",
    )
    base.update(overrides)
    return EventEnvelopeV1(**base)


def test_event_envelope_valid():
    env = _envelope(window_id=3, payload={"k": "v"})
    assert env.schema_version == "simulation_event_v1"
    assert env.event_type == ReplayEventType.WINDOW_STARTED


def test_event_envelope_negative_sequence_rejected():
    with pytest.raises(ValidationError):
        _envelope(sequence_number=-1)


def test_unsupported_schema_version_rejected():
    class Strict(EventEnvelopeV1):
        pass

    with pytest.raises(ValidationError):
        EventEnvelopeV1(
            schema_version="simulation_event_v9",
            replay_id="r",
            event_id="e",
            sequence_number=0,
            event_type=ReplayEventType.REPLAY_CREATED,
            source_component="t",
        )


def test_device_state_null_vs_zero_survives_roundtrip():
    st = DeviceStateV1(
        replay_id="r", entity_id="router",
        behavior_supported=False, behavior_observed=False, behavior_risk=None,
    )
    dumped = st.model_dump()
    assert dumped["behavior_risk"] is None
    reloaded = DeviceStateV1.model_validate(dumped)
    assert reloaded.behavior_risk is None
    assert reloaded.model_dump()["behavior_risk"] is None

    zero = DeviceStateV1.model_validate({**dumped, "behavior_supported": True, "behavior_risk": 0.0})
    assert zero.behavior_risk == 0.0


def test_graph_and_srep_contract_validation():
    g = DeviceRiskGraphSnapshotV1(replay_id="r")
    assert g.graph_kind == "device_risk_graph"
    c = CommunicationGraphSnapshotV1(replay_id="r")
    assert c.graph_kind == "communication_graph"
    with pytest.raises(ValidationError):
        DeviceRiskGraphSnapshotV1(replay_id="r", graph_kind="communication_graph")

    s = SrepSnapshotV1(replay_id="r", mode="DEVICE_ONLY")
    with pytest.raises(ValidationError):
        SrepSnapshotV1(replay_id="r", mode="DUAL_GRAPH")


def test_saved_snapshot_requires_status_dict():
    snap = SavedReplaySnapshotV1(
        snapshot_id="s1", replay_id="r", session_trace="trace",
        replay_status={"state": "COMPLETED"},
    )
    assert snap.schema_version == "saved_replay_snapshot_v1"
    with pytest.raises(ValidationError):
        SavedReplaySnapshotV1(snapshot_id="s2", replay_id="r", session_trace="t")


def test_replay_status_defaults():
    st = ReplayStatusV1(replay_id="r", session_trace="t", state=ReplayState.CREATED,
                        source_mode="feature_store", pacing=PacingSpeed.MAX)
    assert st.sequence_number == 0 and st.error is None


def test_api_error_model():
    e = ApiErrorV1(error_code="x", message="m")
    assert e.schema_version == "api_error_v1"


def test_find_ground_truth_nested_paths():
    doc = {
        "ok": 1,
        "nested": [
            {"label_full": "attack_x", "fine": [{"target": "soil-sensor"}]},
            {"deep": {"ground_truth": [1, 2]}},
        ],
    }
    paths = find_ground_truth_violations(doc)
    assert len(paths) == 3
    assert any("label_full" in p for p in paths)


def test_benign_word_not_rejected_but_exact_keys_are():
    doc = {"attack_probability": 0.9, "attacker_count": 1, "targeteer": 2}
    assert find_ground_truth_violations(doc) == []
    doc2 = {"attack": "x"}
    assert find_ground_truth_violations(doc2)
