"""Device inventory loading and endpoint-to-device identity resolution.

Identity resolution maps raw packet/telemetry endpoints (MAC or IP) onto the
authoritative DataSense inventory names from ``devices.csv``. MAC comparison
is case-insensitive and separator-insensitive.

Behavioural profile categories are assigned explicitly per sensor semantics:
continuous/high-rate, sparse/event-driven, degenerate/special-case and
unsupported. Devices without MQTT telemetry (everything except the 14
sensors) are ``unsupported`` and must never receive fabricated behaviour.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

BEHAVIOR_PROFILE_CONTINUOUS = "continuous"
BEHAVIOR_PROFILE_SPARSE = "sparse"
BEHAVIOR_PROFILE_DEGENERATE = "degenerate"
BEHAVIOR_PROFILE_UNSUPPORTED = "unsupported"

BEHAVIOR_PROFILE_CATEGORIES = (
    BEHAVIOR_PROFILE_CONTINUOUS,
    BEHAVIOR_PROFILE_SPARSE,
    BEHAVIOR_PROFILE_DEGENERATE,
    BEHAVIOR_PROFILE_UNSUPPORTED,
)

CONTINUOUS_SENSORS = (
    "weather-sensor",
    "sound-sensor",
    "vibration-sensor",
    "light-sensor",
    "gas-sensor",
    "steam-sensor",
    "soil-sensor",
    "ultrasonic-sensor",
    "accelerometer-sensor",
)

SPARSE_SENSORS = (
    "motion-sensor",
    "rfid-sensor",
    "flame-sensor",
    "proximity-collision-sensor",
)

DEGENERATE_SENSORS = ("water-sensor",)

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"


def normalize_mac(mac: str | None) -> str | None:
    if not mac:
        return None
    return mac.strip().lower().replace("-", ":")


@dataclass(frozen=True)
class DeviceRecord:
    device_name: str
    mac: str
    ip: str
    role: str
    type: str
    main_topic: str


class DeviceInventory:
    """Authoritative device table with lookup indexes for identity resolution."""

    def __init__(self, records: list[DeviceRecord]):
        self.records = records
        self.by_name: dict[str, DeviceRecord] = {}
        self.by_mac: dict[str, DeviceRecord] = {}
        self.by_ip: dict[str, DeviceRecord] = {}
        for rec in records:
            self.by_name[rec.device_name] = rec
            self.by_mac.setdefault(rec.mac.lower(), rec)
            self.by_ip.setdefault(rec.ip, rec)

    @classmethod
    def load(cls, devices_csv: Path) -> "DeviceInventory":
        records = []
        with open(devices_csv, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                records.append(
                    DeviceRecord(
                        device_name=row["device_name"].strip(),
                        mac=normalize_mac(row["mac"]) or "",
                        ip=row["ip"].strip(),
                        role=row["role"].strip(),
                        type=row["type"].strip(),
                        main_topic=(row.get("main_topic") or "").strip(),
                    )
                )
        return cls(records)

    def resolve(self, *, mac: str | None = None, ip: str | None = None) -> DeviceRecord | None:
        norm = normalize_mac(mac)
        if norm is not None:
            hit = self.by_mac.get(norm)
            if hit is not None:
                return hit
        if ip:
            hit = self.by_ip.get(ip.strip())
            if hit is not None:
                return hit
        return None

    def behavior_profile_for(self, device_name: str) -> str:
        rec = self.by_name.get(device_name)
        if rec is None or rec.role != "sensor":
            return BEHAVIOR_PROFILE_UNSUPPORTED
        if device_name in DEGENERATE_SENSORS:
            return BEHAVIOR_PROFILE_DEGENERATE
        if device_name in SPARSE_SENSORS:
            return BEHAVIOR_PROFILE_SPARSE
        if device_name in CONTINUOUS_SENSORS:
            return BEHAVIOR_PROFILE_CONTINUOUS
        return BEHAVIOR_PROFILE_UNSUPPORTED

    @property
    def sensor_names(self) -> list[str]:
        return [r.device_name for r in self.records if r.role == "sensor"]
