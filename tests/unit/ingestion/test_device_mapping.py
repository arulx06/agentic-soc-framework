from conftest import DEFAULT_DEVICES_ROWS, write_devices_csv

from datasets.datasense.devices import (
    BEHAVIOR_PROFILE_CONTINUOUS,
    BEHAVIOR_PROFILE_DEGENERATE,
    BEHAVIOR_PROFILE_SPARSE,
    BEHAVIOR_PROFILE_UNSUPPORTED,
    DeviceInventory,
    normalize_mac,
)


def _inventory(tmp_path, rows=None):
    path = write_devices_csv(tmp_path / "devices.csv", rows)
    return DeviceInventory.load(path)


def test_normalize_mac_case_and_separator_insensitive():
    assert normalize_mac("F0:08:D1:CE:CF:0C") == "f0:08:d1:ce:cf:0c"
    assert normalize_mac("F0-08-D1-CE-CF-0C") == "f0:08:d1:ce:cf:0c"


def test_resolve_by_mac_case_insensitive(tmp_path):
    inv = _inventory(tmp_path)
    hit = inv.resolve(mac="F0:08:D1:CE:CF:0C")
    assert hit is not None and hit.device_name == "soil-sensor"
    hit2 = inv.resolve(mac="DC-A6-32-DC-28-46")
    assert hit2 is not None and hit2.device_name == "mqtt-broker"


def test_resolve_by_ip(tmp_path):
    inv = _inventory(tmp_path)
    hit = inv.resolve(ip="192.168.1.195")
    assert hit.device_name == "edge1"


def test_unresolved_returns_none(tmp_path):
    inv = _inventory(tmp_path)
    assert inv.resolve(mac="aa:bb:cc:dd:ee:ff") is None
    assert inv.resolve(ip="10.9.9.9") is None


def test_behavior_profiles_match_sensor_semantics(tmp_path):
    inv = _inventory(tmp_path)
    expected_continuous = {
        "soil-sensor": BEHAVIOR_PROFILE_CONTINUOUS,
        "water-sensor": BEHAVIOR_PROFILE_DEGENERATE,
        "motion-sensor": BEHAVIOR_PROFILE_SPARSE,
        "mqtt-broker": BEHAVIOR_PROFILE_UNSUPPORTED,
        "edge1": BEHAVIOR_PROFILE_UNSUPPORTED,
        "attacker0": BEHAVIOR_PROFILE_UNSUPPORTED,
        "router": BEHAVIOR_PROFILE_UNSUPPORTED,
    }
    for name, profile in expected_continuous.items():
        assert inv.behavior_profile_for(name) == profile, name


def test_unknown_device_is_unsupported(tmp_path):
    inv = _inventory(tmp_path)
    assert inv.behavior_profile_for("not-in-inventory") == BEHAVIOR_PROFILE_UNSUPPORTED


def test_all_14_sensors_covered(tmp_path):
    rows = list(DEFAULT_DEVICES_ROWS)
    extra_sensors = [
        ("08:b6:1f:82:12:30", "192.168.1.10", "weather-sensor"),
        ("08:b6:1f:81:d2:cc", "192.168.1.13", "steam-sensor"),
        ("08:b6:1f:83:25:98", "192.168.1.14", "gas-sensor"),
        ("f0:08:d1:ce:cf:c8", "192.168.1.15", "sound-sensor"),
        ("08:b6:1f:82:27:d0", "192.168.1.16", "vibration-sensor"),
        ("08:b6:1f:82:ee:c4", "192.168.1.17", "ultrasonic-sensor"),
        ("8c:aa:b5:8a:a9:b4", "192.168.1.18", "light-sensor"),
        ("08:b6:1f:82:ee:44", "192.168.1.19", "accelerometer-sensor"),
        ("08:b6:1f:82:ef:30", "192.168.1.20", "proximity-collision-sensor"),
        ("08:b6:1f:82:2b:1c", "192.168.1.22", "rfid-sensor"),
        ("08:b6:1f:82:ee:cc", "192.168.1.23", "flame-sensor"),
    ]
    for mac, ip, name in extra_sensors:
        rows.append(dict(mac=mac, ip=ip, device_name=name, role="sensor", type="sensor", main_topic=""))
    inv = _inventory(tmp_path, rows)
    sensors = set(inv.sensor_names)
    assert len(sensors) == 14
    profiles = {name: inv.behavior_profile_for(name) for name in sensors}
    continuous = [n for n, p in profiles.items() if p == BEHAVIOR_PROFILE_CONTINUOUS]
    sparse = [n for n, p in profiles.items() if p == BEHAVIOR_PROFILE_SPARSE]
    degenerate = [n for n, p in profiles.items() if p == BEHAVIOR_PROFILE_DEGENERATE]
    assert len(continuous) == 9
    assert sorted(sparse) == ["flame-sensor", "motion-sensor", "proximity-collision-sensor", "rfid-sensor"]
    assert degenerate == ["water-sensor"]
