"""Out-of-order telemetry: every valid event contributes exactly once.

Strategy under test (ordering.WatermarkTracker): a maximum-lateness
watermark finalizes old windows incrementally; any valid event older than
the finalized floor fails the session explicitly. No silent loss.
"""

import json as _json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import (
    SOIL_IP,
    SOIL_MAC,
    DEFAULT_DEVICES_ROWS,
    mqtt_record,
)

from datasets.datasense.behavior_features import BehaviorWindowManager
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.ndjson_reader import parse_telemetry_line
from datasets.datasense.windowing import EventOlderThanWatermarkError, WindowGrid

NS = 1_000_000_000
START = 1_736_976_313 * NS + 307_000_000


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


def _event(ts: datetime, value: float, message_id: int):
    def iso(dt):
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    return parse_telemetry_line(
        _json.dumps(
            mqtt_record(
                iso(ts), ip=SOIL_IP, mac=SOIL_MAC, value=value, message_id=message_id
            )
        )
    )


BASE = datetime.fromisoformat("2025-01-15T21:25:13.307+00:00").astimezone(timezone.utc)


def test_out_of_order_event_lands_in_correct_window():
    manager = BehaviorWindowManager(
        WindowGrid(START, 5.0),
        "s",
        _inventory(),
        clock_tolerance_ns=10**9,
        max_event_lateness_ns=60 * NS,
    )
    t_w0 = BASE + timedelta(milliseconds=500)
    t_w1 = BASE + timedelta(seconds=6)
    t_w2 = BASE + timedelta(seconds=11)
    emitted = []
    emitted += manager.add_event(_event(t_w1, 2.0, 1))
    emitted += manager.add_event(_event(t_w2, 3.0, 2))
    emitted += manager.add_event(_event(t_w0, 1.0, 0))
    emitted += manager.finish()

    soil = {r["window_id"]: r for r in emitted if r["device_id"] == "soil-sensor"}
    assert soil[0]["messages_count"] == 1
    assert soil[1]["messages_count"] == 1
    assert soil[2]["messages_count"] == 1
    diag = manager.diagnostics
    assert diag["late_events"] >= 1
    assert soil[0]["value_last"] == 1.0
    assert soil[2]["seconds_since_previous_event"] is not None


def test_out_of_order_across_windows_matches_sorted_input_exactly():
    events = [
        _event(BASE + timedelta(milliseconds=100 + i * 700), float(i), i)
        for i in range(20)
    ]
    reordered = [events[i] for i in (5, 6, 0, 8, 1, 2, 10, 3, 4, 7, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19)]

    def extract(seq):
        manager = BehaviorWindowManager(
            WindowGrid(START, 5.0),
            "s",
            _inventory(),
            clock_tolerance_ns=10**9,
            max_event_lateness_ns=60 * NS,
        )
        rows = []
        for ev in seq:
            rows += manager.add_event(ev)
        rows += manager.finish()
        return sorted(
            (r for r in rows if r["device_id"] == "soil-sensor"),
            key=lambda r: r["window_id"],
        )

    by_order = extract(reordered)
    by_sorted = extract(sorted(events, key=lambda e: e.ts_ns))
    assert by_order == by_sorted
    assert sum(r["messages_count"] for r in by_order) == 20


def test_valid_event_older_than_watermark_fails_explicitly():
    manager = BehaviorWindowManager(
        WindowGrid(START, 5.0),
        "s",
        _inventory(),
        clock_tolerance_ns=10**9,
        max_event_lateness_ns=5 * NS,
    )
    far_future = _event(BASE + timedelta(seconds=120), 9.0, 99)
    manager.add_event(far_future)
    stale = _event(BASE + timedelta(milliseconds=100), 1.0, 0)
    with pytest.raises(EventOlderThanWatermarkError):
        manager.add_event(stale)


def test_event_accounting_no_duplicates(tmp_path=None):
    manager = BehaviorWindowManager(
        WindowGrid(START, 5.0),
        "s",
        _inventory(),
        clock_tolerance_ns=10**9,
        max_event_lateness_ns=60 * NS,
    )
    total_valid = 25
    for i in range(total_valid):
        ts = BASE + timedelta(milliseconds=200 + i * 900)
        manager.add_event(_event(ts, float(i % 5), i))
    rows = manager.finish()
    soil_rows = [r for r in rows if r["device_id"] == "soil-sensor"]
    contributed = sum(r["messages_count"] for r in soil_rows)
    assert contributed == total_valid
    diag = manager.diagnostics
    assert diag["events_applied_to_accumulators"] == total_valid
    assert sum(r["messages_count"] for r in rows) == total_valid
    assert diag["messages_valid_total"] == total_valid
    assert diag["unresolved_telemetry_sources"] == 0
    assert diag["messages_ignored_unsupported"] == 0


def test_stream_level_exactly_once_application(tmp_path):
    """Every parsed line is applied to exactly one accumulator exactly once,
    even when lines are out of order; applied count equals parsed count."""
    from conftest import write_ndjson
    from datasets.datasense.ndjson_reader import iter_mqtt_events

    records = []
    order = [7, 8, 0, 10, 1, 2, 12, 3, 4, 9, 5, 6, 11]
    for i in range(13):
        ts = BASE + timedelta(milliseconds=300 + i * 800)
        rec = mqtt_record(
            ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z",
            ip=SOIL_IP,
            mac=SOIL_MAC,
            value=float(i),
            message_id=i,
        )
        records.append(rec)
    shuffled = [records[i] for i in order]
    path = write_ndjson(tmp_path / "ooo.json", shuffled)

    manager = BehaviorWindowManager(
        WindowGrid(START, 5.0),
        "s",
        _inventory(),
        clock_tolerance_ns=10**9,
        max_event_lateness_ns=60 * NS,
    )
    rows = []
    stream = iter_mqtt_events(path)
    for event in stream:
        rows += manager.add_event(event)
    rows += manager.finish()

    stats = stream.stats
    diag = manager.diagnostics
    assert stats.events_parsed == 13
    assert diag["events_applied_to_accumulators"] == stats.events_parsed
    total_in_rows = sum(r["messages_count"] for r in rows)
    assert total_in_rows == 13
    line_numbers = sorted(e.line_number for e in iter_mqtt_events(path))
    assert line_numbers == list(range(1, 14))
