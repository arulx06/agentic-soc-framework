"""Gateway tests: routing, validation, provenance, label firewall."""

import pytest

from conftest import DEFAULT_DEVICES_ROWS

from agents.finding_gateway import FindingGateway
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from pipeline.findings import (
    BehaviorFinding,
    NetworkFinding,
    opaque_session_trace,
)
from simulation.abm import DeviceABM
from simulation.topology import build_topology


def _inventory():
    return DeviceInventory(
        [
            DeviceRecord(
                device_name=r["device_name"],
                mac=r["mac"].lower(),
                ip=r["ip"],
                role=r["role"],
                type=r["type"],
                main_topic=r["main_topic"],
            )
            for r in DEFAULT_DEVICES_ROWS
        ]
    )


@pytest.fixture
def stack():
    inv = _inventory()
    abm = DeviceABM(inv, build_topology(inv))
    gw = FindingGateway(abm)
    return inv, abm, gw


def _net_finding(entity="soil-sensor", proba=0.9, prov=None):
    provenance = {
        "session_trace": opaque_session_trace("attack_recon_host-disc-udp-ping_soil-sensor"),
        "source_mode": "feature_store",
        "model_id": "network_detector_v1",
    }
    if prov:
        provenance.update(prov)
    return NetworkFinding(
        entity_id=entity,
        window_id=0,
        timestamp_utc="2025-01-15T21:25:13.307Z",
        attack_probability=proba,
        predicted_class="attack" if proba >= 0.5 else "benign",
        confidence=abs(proba - 0.5) * 2,
        source_model="network_detector_v1@network_feature_schema_v1",
        provenance=provenance,
    )


def _beh_finding(entity="soil-sensor"):
    return BehaviorFinding(
        entity_id=entity,
        window_id=1,
        timestamp_utc="2025-01-15T21:25:18.307Z",
        deviation_score=0.8,
        profile_type="continuous",
        confidence=0.7,
        explanation="cadence deviation",
        source_model="behavior_profiler_v1@behavior_feature_schema_v1",
        provenance={"source_mode": "direct_raw"},
    )


def test_network_finding_updates_only_network_evidence(stack):
    _, abm, gw = stack
    assert gw.submit(_net_finding()) is True
    st = abm.states["soil-sensor"]
    assert st.network_risk == 0.9
    assert st.network_observed is True
    assert st.behavior_risk is None
    assert st.behavior_observed is False


def test_behavior_finding_updates_only_behavior_evidence(stack):
    _, abm, gw = stack
    assert gw.submit(_beh_finding()) is True
    st = abm.states["soil-sensor"]
    assert st.behavior_risk == 0.8
    assert st.behavior_observed is True
    assert st.network_risk is None


def test_unknown_entity_rejected_cleanly(stack):
    _, abm, gw = stack
    assert gw.submit(_net_finding(entity="ghost-device")) is False
    assert gw.stats.rejected_unknown_entity == 1
    assert "ghost-device" not in abm.states


def test_invalid_timestamp_rejected(stack):
    _, _, gw = stack
    with pytest.raises(ValueError):
        NetworkFinding(
            entity_id="soil-sensor",
            window_id=0,
            timestamp_utc="not-a-timestamp",
            attack_probability=0.4,
            predicted_class="benign",
            confidence=0.6,
            source_model="x",
        )
    with pytest.raises(ValueError):
        NetworkFinding(
            entity_id="soil-sensor",
            window_id=0,
            timestamp_utc="2025-01-15T21:25:13.307",
            attack_probability=0.4,
            predicted_class="benign",
            confidence=0.6,
            source_model="x",
        )
    assert gw.stats.rejected_timestamp == 0


def test_provenance_preserved_on_acceptance(stack):
    _, abm, gw = stack
    prov_marked = {
        "session_trace": opaque_session_trace("s"),
        "source_mode": "direct_raw",
        "artifact_path": "p",
    }
    gw.submit(_net_finding(prov=prov_marked))
    entry = gw._accepted_log[-1]
    for key, value in prov_marked.items():
        assert entry["provenance"][key] == value
    assert entry["source_model"].startswith("network_detector_v1")


def test_labels_cannot_enter_through_finding_api(stack):
    _, _, gw = stack
    with pytest.raises(ValueError):
        _net_finding(prov={"label": "attack"})
    with pytest.raises(ValueError):
        _net_finding(prov={"attack_target": "soil-sensor"})
    with pytest.raises(ValueError):
        _net_finding(prov={"device_mac": "f0:08:d1:ce:cf:0c"})
    raw_dict = {
        "entity_id": "soil-sensor",
        "label_full": "attack_recon_x_soil-sensor",
        "attack_probability": 1.0,
    }
    assert gw.submit(raw_dict) is False
    assert gw.stats.rejected_schema >= 1


def test_unsupported_device_cannot_receive_behavior_evidence(stack):
    _, abm, _ = stack
    unsupported = BehaviorFinding(
        entity_id="router",
        window_id=0,
        timestamp_utc="2025-01-15T21:25:13.307Z",
        deviation_score=0.5,
        profile_type="continuous",
        confidence=0.5,
        explanation="x",
        source_model="behavior_profiler_v1",
    )
    with pytest.raises(ValueError):
        abm.apply_behavior_evidence(unsupported)


def test_subscriber_hook_receives_accepted_findings_only(stack):
    _, _, gw = stack
    seen = []
    gw.subscribe(seen.append)
    gw.submit(_net_finding())
    gw.submit(_net_finding(entity="ghost-device"))
    assert len(seen) == 1
