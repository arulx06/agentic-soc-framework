import pytest

from conftest import (
    DEFAULT_DEVICES_ROWS,
    write_min_ndjson,
    write_min_pcapng,
)

from datasets.datasense.catalog import build_session_record
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.extraction import ExtractionEngine
from datasets.datasense.feature_store import FeatureStoreReader
from datasets.datasense.profiles import LOW_PROFILE, STANDARD_PROFILE, resolve_profile
from datasets.datasense.versions import REQUIRED_VERSIONS

NS = 1_000_000_000


def _inventory():
    rows = [
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
    return DeviceInventory(rows)


def _session(tmp_path):
    pcap = write_min_pcapng(tmp_path / "s.pcapng")
    ndjson = write_min_ndjson(tmp_path / "s.json")
    return build_session_record(
        "attack_recon_host-disc-udp-ping_soil-sensor",
        {"pcap": str(pcap), "json": str(ndjson)},
        [
            dict(
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
            )
        ],
    )


def _engine(store, settings=None, window_seconds=5.0, force=False):
    return ExtractionEngine(
        store_root=store,
        inventory=_inventory(),
        settings=settings or resolve_profile("low"),
        window_seconds=window_seconds,
        force_regenerate=force,
    )


def _canonical_rows(reader, scenario):
    net = sorted(
        reader.iter_network_records(scenario),
        key=lambda r: (r["window_id"], r["device_id"]),
    )
    beh = sorted(
        reader.iter_behavior_records(scenario),
        key=lambda r: (r["window_id"], r["device_id"]),
    )
    return net, beh


def test_extract_then_resume_skips(tmp_path):
    store = tmp_path / "store"
    session = _session(tmp_path)
    engine = _engine(store)
    state1 = engine.run_session(session)
    assert state1["status"] == "completed"
    assert state1["network_record_count"] > 0
    assert state1["behavior_record_count"] > 0
    assert state1["versions"] == REQUIRED_VERSIONS

    manifest_lines = (store / "manifest" / "manifest.jsonl").read_text().strip().splitlines()
    completed_events = [json.loads(l) for l in manifest_lines if '"completed"' in l]
    engine2 = _engine(store)
    state2 = engine2.run_session(session)
    assert state2["status"] == "completed"
    manifest_lines_after = (store / "manifest" / "manifest.jsonl").read_text().strip().splitlines()
    completed_after = [json.loads(l) for l in manifest_lines_after if '"completed"' in l]
    assert len(completed_after) == len(completed_events)


def test_failed_session_reruns(tmp_path):
    store = tmp_path / "store"
    session = _session(tmp_path)

    class ExplodingPcapPath(str):
        pass

    broken = build_session_record(
        session.scenario_id,
        {"pcap": str(tmp_path / "missing.pcap"), "json": session.raw_json_path},
        [
            dict(
                filename=session.scenario_id,
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
        ],
    )
    engine = _engine(store)
    with pytest.raises(FileNotFoundError):
        engine.run_session(broken)
    reader = FeatureStoreReader(store)
    failed_state = reader.load_state(session.scenario_id)
    assert failed_state["status"] == "failed"

    state = _engine(store).run_session(_session(tmp_path))
    assert state["status"] == "completed"


import json  # noqa: E402


def test_resource_profiles_produce_identical_scientific_output(tmp_path):
    session = _session(tmp_path)
    store_low = tmp_path / "low"
    store_std = tmp_path / "std"
    store_auto = tmp_path / "auto"

    low_settings = LOW_PROFILE.with_overrides(profile_name="test-low")
    std_settings = STANDARD_PROFILE.with_overrides(profile_name="test-standard")
    assert low_settings.read_chunk_bytes != std_settings.read_chunk_bytes

    _engine(store_low, low_settings).run_session(session)
    _engine(store_std, std_settings).run_session(session)
    _engine(store_auto, resolve_profile("auto")).run_session(session)

    reader_low = FeatureStoreReader(store_low)
    reader_std = FeatureStoreReader(store_std)
    reader_auto = FeatureStoreReader(store_auto)

    def canonical(reader):
        out = []
        for modality in ("network", "behavior", "communication"):
            rows = sorted(
                reader.iter_records(session.scenario_id, modality),
                key=lambda r: (
                    r["window_id"],
                    r.get("device_id") or "",
                    r.get("src_entity_id") or "",
                    r.get("dst_entity_id") or "",
                ),
            )
            out.append(
                [
                    {k: v for k, v in row.items() if k != "extractor_version"}
                    for row in rows
                ]
            )
        return out

    base = canonical(reader_std)
    assert canonical(reader_low) == base
    assert canonical(reader_auto) == base


def test_direct_raw_matches_store_output(tmp_path):
    from datasets.datasense.extraction import (
        iter_behavior_rows,
        iter_communication_rows,
        iter_network_rows,
    )

    store = tmp_path / "store"
    session = _session(tmp_path)
    _engine(store).run_session(session)

    collect_net = {}
    direct_net = sorted(
        iter_network_rows(
            session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024, 1 << 20,
            collect=collect_net,
        ),
        key=lambda r: (r["window_id"], r["device_id"]),
    )
    collect_beh = {}
    direct_beh = sorted(
        iter_behavior_rows(
            session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024,
            collect=collect_beh,
        ),
        key=lambda r: (r["window_id"], r["device_id"]),
    )
    collect_comm = {}
    direct_comm = sorted(
        iter_communication_rows(
            session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024, 1 << 20,
            collect=collect_comm,
        ),
        key=lambda r: (
            r["window_id"], r["src_entity_id"], r["dst_entity_id"]
        ),
    )

    reader = FeatureStoreReader(store)

    def stored(modality, keys):
        return sorted(
            reader.iter_records(session.scenario_id, modality),
            key=lambda r: keys(r),
        )

    assert len(direct_net) == len(stored("network", lambda r: (r["window_id"], r["device_id"]))) > 0
    assert len(direct_beh) == len(stored("behavior", lambda r: (r["window_id"], r["device_id"]))) > 0
    assert len(direct_comm) == len(stored("communication", lambda r: (r["window_id"], r["src_entity_id"], r["dst_entity_id"]))) > 0

    for a, b in zip(direct_net, stored("network", lambda r: (r["window_id"], r["device_id"]))):
        assert a == b
    for a, b in zip(direct_beh, stored("behavior", lambda r: (r["window_id"], r["device_id"]))):
        assert a == b
    for a, b in zip(direct_comm, stored("communication", lambda r: (r["window_id"], r["src_entity_id"], r["dst_entity_id"]))):
        assert a == b


def test_valid_event_accounting_reported(tmp_path):
    store = tmp_path / "store"
    session = _session(tmp_path)
    engine = ExtractionEngine(
        store_root=store,
        inventory=_inventory(),
        settings=resolve_profile("low"),
        window_seconds=5.0,
    )
    state = engine.run_session(session)
    accounting = state["diagnostics"]["behavior"]["valid_event_accounting"]
    assert accounting["parsed_events"] > 0
    assert accounting["contributing_events"] == accounting["parsed_events"]
    assert (
        accounting["contributing_events"]
        == state["diagnostics"]["behavior"]["manager_diagnostics"][
            "events_applied_to_accumulators"
        ]
    )
    assert accounting["duplicate_contributions_structural"] == 0
    assert accounting["malformed_lines"] == 0
