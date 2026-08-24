"""Label-invariance: attack/target ground truth must not affect extraction.

Ground truth may exist ONLY in the isolated catalog metadata. Changing
category/name/target/data-type metadata while holding the raw bytes and
scenario identity fixed must produce byte-identical scientific records
(network, behaviour, communication) across independent extractions.
"""

import pytest

from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.catalog import build_session_record
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.extraction import ExtractionEngine
from datasets.datasense.feature_store import FeatureStoreReader
from datasets.datasense.profiles import resolve_profile
from tests_extraction_helpers import SCENARIO_ID


def _inventory():
    return DeviceInventory(
        [
            DeviceRecord(
                device_name=row["device_name"],
                mac=row["mac"].lower(),
                ip=row["ip"],
                role=row["role"],
                type=row["type"],
                main_topic=row["main_topic"],
            )
            for row in DEFAULT_DEVICES_ROWS
        ]
    )


def _inv_row(**overrides):
    base = dict(
        filename=SCENARIO_ID,
        data_type="attack",
        category="recon",
        attack_name="host-disc-udp-ping",
        attack_target="soil-sensor",
        doc_count=10,
        start="2025-01-15T21:25:13.307Z",
        end="2025-01-15T21:26:15.119Z",
        start_timestamp=0.0,
        end_timestamp=0.0,
    )
    base.update(overrides)
    return base


def _session(tmp_path, inv_rows):
    from conftest import write_min_ndjson, write_min_pcapng

    pcap = write_min_pcapng(tmp_path / f"s_{abs(hash(tuple(sorted(inv_rows[0].items()))))}.pcapng")
    ndjson = write_min_ndjson(tmp_path / "s.json")
    return build_session_record(
        SCENARIO_ID,
        {"pcap": str(pcap), "json": str(ndjson)},
        inv_rows,
    )


GROUND_TRUTH_KEYS = (
    "is_attack",
    "attack_category",
    "attack_name",
    "targets",
    "whole_network_target",
    "label",
    "label_full",
    "data_type",
)


@pytest.fixture
def extracted_pair(tmp_path):
    store_a = tmp_path / "store_a"
    store_b = tmp_path / "store_b"

    session_a = _session(tmp_path, [_inv_row()])
    session_b = _session(
        tmp_path,
        [
            _inv_row(
                data_type="benign",
                category="benign",
                attack_name="benign",
                attack_target="whole-network",
                doc_count=999999,
            )
        ],
    )
    assert session_b.is_attack is False
    assert session_b.whole_network_target is True
    assert session_b.targets == ["whole-network"]

    engine_a = ExtractionEngine(store_a, _inventory(), resolve_profile("low"))
    engine_b = ExtractionEngine(store_b, _inventory(), resolve_profile("low"))
    state_a = engine_a.run_session(session_a)
    state_b = engine_b.run_session(session_b)
    assert state_a["status"] == state_b["status"] == "completed"
    return store_a, store_b


def _normalized(rows, drop_fields=("extractor_version",)):
    out = []
    for row in sorted(rows, key=lambda r: (r["window_id"], r.get("device_id") or "", r.get("src_entity_id") or "")):
        clean = {k: v for k, v in row.items() if k not in drop_fields}
        out.append(clean)
    return out


def test_labels_do_not_change_any_scientific_record(extracted_pair):
    store_a, store_b = extracted_pair
    reader_a = FeatureStoreReader(store_a)
    reader_b = FeatureStoreReader(store_b)

    for modality in ("network", "behavior", "communication"):
        rows_a = _normalized(list(reader_a.iter_records(SCENARIO_ID, modality)))
        rows_b = _normalized(list(reader_b.iter_records(SCENARIO_ID, modality)))
        assert rows_a == rows_b, modality


def test_default_runtime_records_are_label_free(extracted_pair):
    store_a, _ = extracted_pair
    reader = FeatureStoreReader(store_a)
    for modality in ("network", "behavior", "communication"):
        for row in reader.iter_records(SCENARIO_ID, modality):
            for key in GROUND_TRUTH_KEYS:
                assert key not in row, (modality, key)


def test_direct_raw_streams_are_label_free(tmp_path):
    from conftest import write_min_ndjson, write_min_pcapng
    from datasets.datasense.extraction import (
        iter_behavior_rows,
        iter_pcap_feature_rows,
    )

    pcap = write_min_pcapng(tmp_path / "x.pcapng")
    ndjson = write_min_ndjson(tmp_path / "x.json")
    session = _session(tmp_path, [_inv_row(attack_target="edge1", attack_name="port-scan", category="recon")])
    session.raw_pcap_path = str(pcap)
    session.raw_json_path = str(ndjson)

    for tag, row in iter_pcap_feature_rows(
        session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024, 1 << 20
    ):
        for key in GROUND_TRUTH_KEYS:
            assert key not in row, (tag, key)
    for row in iter_behavior_rows(
        session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024
    ):
        for key in GROUND_TRUTH_KEYS:
            assert key not in row
