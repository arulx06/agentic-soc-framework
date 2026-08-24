"""Shared synthetic-session extraction helper used by store/leakage tests."""

from __future__ import annotations

import pytest

from conftest import DEFAULT_DEVICES_ROWS, write_min_ndjson, write_min_pcapng

from datasets.datasense.catalog import build_session_record
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.extraction import ExtractionEngine
from datasets.datasense.profiles import resolve_profile

SCENARIO_ID = "attack_recon_host-disc-udp-ping_soil-sensor"


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


def build_synthetic_session(tmp_path):
    pcap = write_min_pcapng(tmp_path / "s.pcapng")
    ndjson = write_min_ndjson(tmp_path / "s.json")
    return build_session_record(
        SCENARIO_ID,
        {"pcap": str(pcap), "json": str(ndjson)},
        [
            dict(
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
        ],
    )


@pytest.fixture
def tmp_extracted_store(tmp_path):
    store = tmp_path / "store"
    session = build_synthetic_session(tmp_path)
    engine = ExtractionEngine(
        store_root=store,
        inventory=_inventory(),
        settings=resolve_profile("low"),
        window_seconds=5.0,
    )
    state = engine.run_session(session)
    assert state["status"] == "completed"
    return store, SCENARIO_ID
