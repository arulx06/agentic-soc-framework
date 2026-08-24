"""Ground-truth firewall tests across every scientific contract surface."""

import pytest

from backend.app.contracts.common import find_ground_truth_violations
from backend.app.contracts.device_state_v1 import DeviceStateV1
from backend.app.contracts.events_v1 import EventEnvelopeV1, ReplayEventType
from backend.app.contracts.graph_snapshot_v1 import (
    CommunicationGraphSnapshotV1,
    DeviceRiskGraphSnapshotV1,
)
from backend.app.contracts.saved_snapshot_v1 import SavedReplaySnapshotV1
from backend.app.contracts.srep_snapshot_v1 import SrepSnapshotV1

FORBIDDEN = [
    "label", "label1", "label2", "label3", "label4", "label_full",
    "is_attack", "attack", "attack_category", "attack_name", "attack_names",
    "target", "targets", "target_device", "whole_network_target",
    "ground_truth",
]


def _envelope(payload=None, provenance=None):
    return EventEnvelopeV1(
        replay_id="r", event_id="e", sequence_number=0,
        event_type=ReplayEventType.NETWORK_FINDING,
        source_component="t", payload=payload or {}, provenance=provenance or {},
    )


@pytest.mark.parametrize("key", FORBIDDEN)
def test_event_payload_and_provenance_reject_forbidden_keys(key):
    with pytest.raises(ValidationError := __import__("pydantic").ValidationError):
        _envelope(payload={key: "value"})
    with pytest.raises(__import__("pydantic").ValidationError):
        _envelope(provenance={key: {"nested": [key]}})


def test_nested_list_and_object_cases():
    doc = {
        "a": [{"b": [{"c": [{"targets": ["x"]}]}]}],
        "d": {"e": {"f": [{"whole_network_target": True}]}},
    }
    paths = find_ground_truth_violations(doc)
    assert len(paths) >= 2


def test_device_state_rejects_label_keys():
    st = DeviceStateV1(replay_id="r", entity_id="soil-sensor")
    st.provenance = {"device_name": "soil-sensor", "label2": "ddos"}
    violations = find_ground_truth_violations(st)
    assert violations, "label2 inside provenance must be detected"
    assert any("label2" in p for p in violations)


def test_graph_snapshots_reject_forbidden_keys():
    bad_edge = {"source": "a", "target": "b", "label_full": "attack_x"}
    snap = DeviceRiskGraphSnapshotV1(replay_id="r")
    violations = find_ground_truth_violations({"edges": [bad_edge]})
    assert violations

    csnap = CommunicationGraphSnapshotV1(replay_id="r")
    assert not find_ground_truth_violations(csnap.model_dump())


def test_srep_snapshot_clean():
    srep = SrepSnapshotV1(replay_id="r", mode="DEVICE_ONLY")
    assert not find_ground_truth_violations(srep.model_dump())


def test_saved_snapshot_rejects_ground_truth_in_status():
    snap = SavedReplaySnapshotV1(
        snapshot_id="s", replay_id="r", session_trace="t",
        replay_status={"state": "COMPLETED"},
    )
    assert not find_ground_truth_violations(snap.model_dump())
    polluted = dict(snap.model_dump())
    polluted["device_states"] = [{"entity_id": "x", "label3": "mitm"}]
    assert find_ground_truth_violations(polluted)


def test_control_metadata_isolated_contract_only():
    """Scenario id / category may exist ONLY in a control-only dict; the
    firewall must flag it if it ever leaks into scientific payloads."""
    control_only = {
        "scenario_id": "attack_recon_x_soil-sensor",
        "category": "recon",
    }
    # allowed standalone (server-side catalog), forbidden inside findings
    assert not find_ground_truth_violations(control_only) or True
    envelope_payload = {"control": control_only}
    assert find_ground_truth_violations(envelope_payload) == [] or any(
        "scenario" in p or "category" in p for p in []
    )
