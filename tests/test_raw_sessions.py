"""Integration tests against the real DataSense raw release.

These run ONLY when the audited small recon fixture is available locally;
they are bounded (single ~689 KB PCAPNG + ~470 KB NDJSON session) and skip
with a clear reason otherwise. The known vendor-parity counts from the raw
audit (docs/datasense_raw_audit.md section 8) serve as regression checks.
"""

from pathlib import Path

import pytest

from datasets.datasense.catalog import build_catalog
from datasets.datasense.devices import DeviceInventory
from datasets.datasense.feature_store import FeatureStoreReader

REPO = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO / "data/raw/datasense/dataset/raw_files"
ATTACKS_CSV = REPO / "data/raw/datasense/docs/site/attacks.csv"
DEVICES_CSV = REPO / "data/raw/datasense/docs/site/devices.csv"
VENDOR_CSV_5S = (
    REPO / "data/raw/datasense/dataset/processed_files/all_attack_benign_samples/attack_data/attack_samples_5sec.csv"
)

FIXTURE_SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"
AUDIT_PACKET_COUNTS = [506, 151, 70, 74, 69, 76, 77, 77, 68, 45, 65, 75]
AUDIT_SOIL_MESSAGES_PER_WINDOW = 5


def _fixture_available() -> bool:
    if not (RAW_ROOT.is_dir() and ATTACKS_CSV.is_file() and DEVICES_CSV.is_file()):
        return False
    records, _ = build_catalog(RAW_ROOT, ATTACKS_CSV)
    return any(r.scenario_id == FIXTURE_SESSION for r in records)


pytestmark = pytest.mark.skipif(
    not _fixture_available(),
    reason="DataSense raw dataset not present locally; bounded fixture unavailable",
)


@pytest.fixture(scope="module")
def extracted_fixture(tmp_path_factory):
    from datasets.datasense.extraction import ExtractionEngine
    from datasets.datasense.profiles import resolve_profile

    store_root = tmp_path_factory.mktemp("raw_store") / "datasense"
    records, _ = build_catalog(RAW_ROOT, ATTACKS_CSV)
    session = next(r for r in records if r.scenario_id == FIXTURE_SESSION)
    engine = ExtractionEngine(
        store_root=store_root,
        inventory=DeviceInventory.load(DEVICES_CSV),
        settings=resolve_profile("low"),
        window_seconds=5.0,
    )
    state = engine.run_session(session)
    assert state["status"] == "completed"
    return store_root, session, state


def test_fixture_packet_parity_with_audit_counts(extracted_fixture):
    store_root, session, state = extracted_fixture
    reader = FeatureStoreReader(store_root)
    soil_rows = [
        row
        for row in reader.iter_network_records(FIXTURE_SESSION)
        if row["device_id"] == "soil-sensor" and row["network_observed"]
    ]
    soil_rows.sort(key=lambda r: r["window_id"])
    counts = [row["packets_all_count"] for row in soil_rows]
    assert counts[: len(AUDIT_PACKET_COUNTS)] == AUDIT_PACKET_COUNTS
    assert all(c == 0 or c > 0 for c in counts)


def test_fixture_message_parity_with_audit(extracted_fixture):
    store_root, session, state = extracted_fixture
    reader = FeatureStoreReader(store_root)
    rows = [
        row
        for row in reader.iter_behavior_records(FIXTURE_SESSION)
        if row["device_id"] == "soil-sensor" and row["behavior_observed"]
    ]
    rows.sort(key=lambda r: r["window_id"])
    counts = [row["messages_count"] for row in rows]
    assert sum(counts) == 62
    assert counts[:12] == [AUDIT_SOIL_MESSAGES_PER_WINDOW] * 12
    if len(counts) > 12:
        assert sum(counts[12:]) == 2


def test_fixture_masks_and_schema_versions(extracted_fixture):
    store_root, session, state = extracted_fixture
    reader = FeatureStoreReader(store_root)
    net_rows = list(reader.iter_network_records(FIXTURE_SESSION))
    beh_rows = list(reader.iter_behavior_records(FIXTURE_SESSION))
    for row in net_rows:
        if not row["network_observed"]:
            assert row["packets_all_count"] is None
    supported = {r["device_id"]: r["behavior_supported"] for r in beh_rows}
    assert supported.get("soil-sensor") is True
    non_sensor = [d for d, s in supported.items() if s is False]
    assert all(d not in DeviceInventory.load(DEVICES_CSV).sensor_names for d in non_sensor)


def test_vendor_csv_parity_if_available(extracted_fixture):
    if not VENDOR_CSV_5S.is_file():
        pytest.skip("vendor processed_files not present; validation utility is optional")
    import csv as _csv

    from datasets.datasense.windowing import epoch_ns_from_iso

    store_root, session, state = extracted_fixture
    reader = FeatureStoreReader(store_root)
    ours = {
        row["window_id"]: row["packets_all_count"]
        for row in reader.iter_network_records(FIXTURE_SESSION)
        if row["device_id"] == "soil-sensor" and row["network_observed"]
    }
    matched = {}
    with open(VENDOR_CSV_5S, "r", encoding="utf-8", newline="") as fh:
        for vrow in _csv.DictReader(fh):
            if vrow["label_full"] != FIXTURE_SESSION or vrow["device_name"] != "soil-sensor":
                continue
            epoch_ns = epoch_ns_from_iso(vrow["timestamp_start"])
            wid = (epoch_ns - session.session_start_ns) // (5 * 1_000_000_000)
            matched[wid] = int(float(vrow["network_packets_all_count"]))
    assert len(matched) == 12
    for wid, vendor_count in matched.items():
        assert ours[wid] == vendor_count
