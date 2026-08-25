"""Shared synthetic-session extraction helper used by store/leakage tests."""

from __future__ import annotations

from conftest import write_min_ndjson, write_min_pcapng

from datasets.datasense.catalog import build_session_record

SCENARIO_ID = "attack_recon_host-disc-udp-ping_soil-sensor"


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
