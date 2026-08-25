"""Pre-start timestamp policy: tolerance snap vs negative windows.

The policy is identical for network and telemetry: events before the
authoritative scenario start by at most ``clock_tolerance_ns`` snap into
window 0 (counted, with max displacement); earlier events keep a
deterministic negative window id. Nothing is unconditionally clamped.
"""

import pytest

from conftest import (
    BROKER_IP,
    BROKER_MAC,
    SOIL_IP,
    SOIL_MAC,
    eth_frame,
    ipv4_packet,
    mqtt_record,
    tcp_segment,
)
from conftest import DEFAULT_DEVICES_ROWS

import json as _json

from datasets.datasense.behavior_features import BehaviorWindowManager
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.frame_decoder import decode_frame
from datasets.datasense.ndjson_reader import parse_telemetry_line
from datasets.datasense.network_features import NetworkWindowManager
from datasets.datasense.windowing import WindowGrid
from datasets.datasense.versions import DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS

NS = 1_000_000_000
START = 1_736_976_313 * NS + 307_000_000
TOL = 500_000_000


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


def _net_manager():
    return NetworkWindowManager(
        WindowGrid(START, 5.0),
        "s",
        _inventory(),
        frozenset({"attacker0"}),
        clock_tolerance_ns=TOL,
        max_event_lateness_ns=60 * NS,
    )


def _tcp_frame():
    seg = tcp_segment(40000, 1883, 0x18)
    body = ipv4_packet(SOIL_IP, BROKER_IP, 6, seg)
    return eth_frame(BROKER_MAC, SOIL_MAC, 0x0800, body)


def test_event_exactly_at_start_is_normal_window_zero():
    manager = _net_manager()
    rows = manager.add_packet(START, decode_frame(_tcp_frame()), 60, 60) + manager.finish()
    soil_w0 = next(r for r in rows if r["device_id"] == "soil-sensor")
    assert soil_w0["network_observed"] is True
    diag = manager.diagnostics
    assert diag["prestart_snapped_events"] == 0
    assert diag["prestart_negative_events"] == 0


def test_default_tolerance_is_audit_grounded_10ms():
    from datasets.datasense.versions import DEFAULT_MAX_EVENT_LATENESS_SECONDS

    assert DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS == 10_000_000
    start = 1_700_000_000 * NS
    grid = WindowGrid(start, window_seconds=5)
    wid, disp = grid.assign(start - 5_000_000)
    assert (wid, disp) == (0, "prestart_snapped")
    wid2, disp2 = grid.assign(start - 50_000_000)
    assert (wid2, disp2) == (-1, "prestart_negative")
    assert DEFAULT_MAX_EVENT_LATENESS_SECONDS == 60.0


def test_event_slightly_inside_tolerance_snaps_with_displacement_recorded():
    manager = _net_manager()
    rows = manager.add_packet(START - 300_000_000, decode_frame(_tcp_frame()), 60, 60) + manager.finish()
    soil_rows = [r for r in rows if r["device_id"] == "soil-sensor"]
    assert len(soil_rows) == 1
    assert soil_rows[0]["window_id"] == 0
    assert soil_rows[0]["network_observed"] is True
    diag = manager.diagnostics
    assert diag["prestart_snapped_events"] == 1
    assert diag["prestart_snapped_max_displacement_ns"] == 300_000_000
    assert diag["prestart_negative_events"] == 0


def test_event_earlier_than_tolerance_gets_negative_window():
    manager = _net_manager()
    rows = manager.add_packet(START - 2 * TOL, decode_frame(_tcp_frame()), 60, 60) + manager.finish()
    soil_rows = [r for r in rows if r["device_id"] == "soil-sensor"]
    assert len(soil_rows) == 1
    wid = soil_rows[0]["window_id"]
    assert wid < 0
    start_ns, end_ns = WindowGrid(START, 5.0).window_bounds(wid)
    assert end_ns <= START
    assert manager.diagnostics["prestart_negative_events"] == 1
    assert manager.diagnostics["prestart_snapped_events"] == 0


def test_exact_five_second_boundary_positive_windows():
    manager = _net_manager()
    for offset in (5 * NS, 10 * NS):
        manager.add_packet(START + offset, decode_frame(_tcp_frame()), 60, 60)
    rows = manager.finish()
    wids = sorted(r["window_id"] for r in rows if r["device_id"] == "soil-sensor")
    assert 1 in wids and 2 in wids
    assert manager.diagnostics["prestart_negative_events"] == 0


def _event(ts_iso):
    return parse_telemetry_line(_json.dumps(mqtt_record(ts_iso)))


def test_telemetry_uses_identical_prestart_policy():
    manager = BehaviorWindowManager(
        WindowGrid(START, 5.0),
        "s",
        _inventory(),
        clock_tolerance_ns=TOL,
        max_event_lateness_ns=60 * NS,
    )
    from datetime import datetime, timedelta, timezone

    def iso(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    base = datetime.fromisoformat("2025-01-15T21:25:13.307+00:00")
    snapped = list(manager.add_event(_event(iso(base - timedelta(milliseconds=200)))))
    neg = list(manager.add_event(_event(iso(base - timedelta(seconds=3)))))
    rest = manager.finish()
    all_rows = snapped + neg + rest
    soil = {r["window_id"]: r for r in all_rows if r["device_id"] == "soil-sensor"}
    assert 0 in soil and any(w < 0 for w in soil)
    diag = manager.diagnostics
    assert diag["prestart_snapped_events"] == 1
    assert diag["prestart_negative_events"] == 1
