import json

import pytest

from conftest import (
    mqtt_record,
)
from conftest import write_min_ndjson, write_min_pcapng

from datasets.datasense.catalog import build_session_record
from datasets.datasense.feature_store import (
    ExtractionStateStore,
    FeatureStoreReader,
    FeatureStoreWriter,
    IncompatibleSchemaError,
    decide_resume,
    cleanup_partial_output,
)
from datasets.datasense.versions import REQUIRED_VERSIONS

NS = 1_000_000_000
START = 1_736_976_313 * NS + 307_000_000


def _session(tmp_path):
    pcap = write_min_pcapng(tmp_path / "s.pcapng")
    ndjson = write_min_ndjson(tmp_path / "s.json")
    return build_session_record(
        "attack_recon_host-disc-udp-ping_soil-sensor",
        {"pcap": str(pcap), "json": str(ndjson)},
        [dict(
            filename="attack_recon_host-disc-udp-ping_soil-sensor",
            data_type="attack",
            category="recon",
            attack_name="host-disc-udp-ping",
            attack_target="soil-sensor",
            doc_count=10,
            start="2025-01-15T21:25:13.307Z",
            end="2025-01-15T21:26:15.119Z",
            start_timestamp=0.0,
            end_timestamp=0.0,
        )],
    )


def _rows_from_writer(store, scenario, modality):
    reader = FeatureStoreReader(store)
    it = (
        reader.iter_network_records(scenario, validate=False)
        if modality == "network"
        else reader.iter_behavior_records(scenario, validate=False)
    )
    return list(it)


def test_writer_roundtrip_parquet(tmp_store):
    from datasets.datasense.network_features import empty_network_row
    from datasets.datasense.windowing import WindowGrid

    grid = WindowGrid(1_736_976_313 * 10**9 + 307_000_000, window_seconds=5.0)
    with FeatureStoreWriter(tmp_store, "s", "network", buffer_rows=2) as writer:
        rows = []
        for w in range(5):
            row = empty_network_row("s", "soil-sensor", w, grid)
            if w > 0:
                row.update(
                    network_observed=True,
                    packets_all_count=w,
                    packets_src_count=w,
                    time_delta_avg=0.5 * w,
                )
            rows.append(row)
        writer.write_rows(rows)
    stored = _rows_from_writer(tmp_store, "s", "network")
    assert len(stored) == 5
    assert stored[0]["packets_all_count"] is None
    assert stored[1]["time_delta_avg"] == pytest.approx(0.5)
    assert stored[3]["packets_all_count"] == 3


def test_atomic_finalization_no_tmp_leftover(tmp_store):
    from datasets.datasense.behavior_features import empty_behavior_row
    from datasets.datasense.windowing import WindowGrid

    grid = WindowGrid(1_736_976_313 * 10**9 + 307_000_000, window_seconds=5.0)
    with FeatureStoreWriter(tmp_store, "s2", "behavior") as writer:
        writer.write_rows([empty_behavior_row("s2", "soil-sensor", 0, grid, True)])
    assert (tmp_store / "behavior" / "s2").is_dir()
    assert not any(p.name.startswith(".tmp-") for p in (tmp_store / "behavior").iterdir())


def test_decide_resume_lifecycle(tmp_store):
    from datasets.datasense.feature_store import ManifestStore

    states = ExtractionStateStore(tmp_store)
    manifest = ManifestStore(tmp_store)
    reader = FeatureStoreReader(tmp_store)

    action, reason = decide_resume(reader, "sess", 5.0)
    assert action == "run"

    states.save_atomic(
        "sess",
        {"status": "in_progress", "versions": dict(REQUIRED_VERSIONS), "window_seconds": 5.0},
    )
    action, reason = decide_resume(reader, "sess", 5.0)
    assert action == "run"
    assert "in_progress" in reason

    (tmp_store / "network" / "sess").mkdir(parents=True)
    (tmp_store / "behavior" / "sess").mkdir(parents=True)
    (tmp_store / "communication" / "sess").mkdir(parents=True)
    states.save_atomic(
        "sess",
        {"status": "completed", "versions": dict(REQUIRED_VERSIONS), "window_seconds": 5.0},
    )
    action, reason = decide_resume(reader, "sess", 5.0)
    assert action == "skip"


def test_version_mismatch_refused_then_regenerated(tmp_store):
    states = ExtractionStateStore(tmp_store)
    reader = FeatureStoreReader(tmp_store)
    for modality in ("network", "behavior", "communication"):
        (tmp_store / modality / "sess").mkdir(parents=True)
    bad_versions = dict(REQUIRED_VERSIONS)
    bad_versions["network_schema"] = "network_feature_schema_v0"
    states.save_atomic(
        "sess", {"status": "completed", "versions": bad_versions, "window_seconds": 5.0}
    )
    with pytest.raises(IncompatibleSchemaError):
        decide_resume(reader, "sess", 5.0)
    action, reason = decide_resume(reader, "sess", 5.0, force_regenerate=True)
    assert action == "regenerate"
    cleanup_partial_output(tmp_store, "sess")
    assert not (tmp_store / "network" / "sess").exists()


def test_window_size_mismatch_detected(tmp_store):
    states = ExtractionStateStore(tmp_store)
    reader = FeatureStoreReader(tmp_store)
    for modality in ("network", "behavior", "communication"):
        (tmp_store / modality / "sess").mkdir(parents=True)
    states.save_atomic(
        "sess",
        {"status": "completed", "versions": dict(REQUIRED_VERSIONS), "window_seconds": 10.0},
    )
    with pytest.raises(IncompatibleSchemaError):
        decide_resume(reader, "sess", 5.0)


def test_reader_validates_state_and_versions(tmp_store):
    reader = FeatureStoreReader(tmp_store)
    with pytest.raises(FileNotFoundError):
        reader.check_compatible("missing-session")
