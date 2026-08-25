from conftest import (
    SOIL_IP,
    SOIL_MAC,
    mqtt_record,
)
from conftest import DEFAULT_DEVICES_ROWS

import json as _json

from datasets.datasense.behavior_features import (
    BEHAVIOR_COMMON_FEATURES,
    BehaviorWindowManager,
    empty_behavior_row,
)
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.ndjson_reader import parse_telemetry_line
from datasets.datasense.windowing import WindowGrid

NS = 1_000_000_000
START = 1_736_976_313 * NS + 307_000_000


def _event(*args, **kwargs) -> object:
    return parse_telemetry_line(_json.dumps(mqtt_record(*args, **kwargs)))


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


def _manager():
    grid = WindowGrid(START, window_seconds=5)
    manager = BehaviorWindowManager(
        grid, "attack_recon_host-disc-udp-ping_soil-sensor", _inventory()
    )
    return grid, manager


def test_continuous_sensor_value_statistics_and_transitions():
    _, manager = _manager()
    values = [280.0, 281.5, 279.0, 280.0]
    for i, value in enumerate(values):
        manager.add_event(
            _event(
                f"2025-01-15T21:25:13.{100 + i:03d}Z",
                ip=SOIL_IP,
                mac=SOIL_MAC.upper(),
                value=value,
                message_id=i,
            )
        )
    rows = manager.finish()
    soil = next(r for r in rows if r["device_id"] == "soil-sensor")
    assert soil["behavior_observed"] is True
    assert soil["behavior_supported"] is True
    assert soil["messages_count"] == 4
    assert abs(soil["value_avg"] - sum(values) / 4) < 1e-9
    assert soil["value_min"] == 279.0
    assert soil["value_max"] == 281.5
    assert soil["value_last"] == 280.0
    assert soil["value_change_transitions_count"] == 3
    assert soil["constant_value_stream"] is False
    assert soil["burst_max_messages_per_second"] == 4
    assert soil["inter_message_delta_avg"] is not None
    assert soil["observed_topics"] == ["iiot/soil"]
    assert soil["telemetry_source_mac"] == SOIL_MAC


def test_degenerate_constant_stream_flagged():
    water_ip, water_mac = "192.168.1.11", "08:b6:1f:84:66:78"
    _, manager = _manager()
    for i in range(3):
        manager.add_event(
            _event(
                f"2025-01-15T21:25:14.{200 + i:03d}Z",
                device_name="ard-w-01",
                application="Water",
                ip=water_ip,
                mac=water_mac,
                topic="iiot/water",
                value=1023.0,
                message_id=i,
            )
        )
    water = next(r for r in manager.finish() if r["device_id"] == "water-sensor")
    assert water["constant_value_stream"] is True
    assert water["value_std"] == 0.0
    assert water["messages_count"] == 3
    assert water["value_change_transitions_count"] == 0


def test_sparse_event_profile_features(tmp_path):
    motion_ip, motion_mac = "192.168.1.21", "08:b6:1f:82:1c:3c"
    _, manager = _manager()
    manager.add_event(
        _event(
            "2025-01-15T21:25:15.000Z",
            device_name="ard-x-01",
            application="Motion",
            ip=motion_ip,
            mac=motion_mac,
            topic="iiot/motion",
            value=1.0,
            message_type="numeric",
        )
    )
    manager.add_event(
        _event(
            "2025-01-15T21:25:16.500Z",
            device_name="ard-x-01",
            application="Motion",
            ip=motion_ip,
            mac=motion_mac,
            topic="iiot/motion",
            value=0.0,
            message_type="numeric",
        )
    )
    motion = next(r for r in manager.finish() if r["device_id"] == "motion-sensor")
    assert motion["event_present"] is True
    assert motion["binary_state_flip_count"] >= 1
    assert motion["last_event_offset_seconds"] is not None
    assert motion["messages_count"] == 2
    assert motion["value_avg"] is None


def test_unsupported_device_telemetry_ignored_not_fabricated():
    _, manager = _manager()
    manager.add_event(
        _event(
            "2025-01-15T21:25:13.500Z",
            ip="192.168.1.195",
            mac="dc:a6:32:dc:27:d4",
            topic="edge/telemetry",
            value=1.0,
        )
    )
    assert manager.diagnostics["messages_ignored_unsupported"] == 1
    assert manager.finish() == []


def test_cross_window_gap_uses_shared_grid():
    _, manager = _manager()
    manager.add_event(
        _event("2025-01-15T21:25:14.000Z", ip=SOIL_IP, mac=SOIL_MAC, message_id=0)
    )
    manager.add_event(
        _event("2025-01-15T21:25:19.500Z", ip=SOIL_IP, mac=SOIL_MAC, message_id=1)
    )
    rows = manager.finish()
    by_wid = {r["window_id"]: r for r in rows}
    w1 = by_wid[1]
    assert w1["seconds_since_previous_event"] is not None
    assert abs(w1["seconds_since_previous_event"] - 5.5) < 1e-9
    assert w1["inter_message_delta_avg"] is None


def test_empty_behavior_rows_explicitly_unobserved():
    grid = WindowGrid(START, window_seconds=5)
    row = empty_behavior_row("s", "soil-sensor", 2, grid, behavior_supported=True)
    assert row["behavior_observed"] is False
    assert row["behavior_supported"] is True
    assert row["messages_count"] is None
    assert row["value_avg"] is None
    assert row["event_present"] is None
