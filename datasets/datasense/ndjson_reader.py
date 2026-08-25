"""Bounded-memory streaming reader for raw MQTT/JSON telemetry (NDJSON).

The DataSense telemetry files are newline-delimited JSON objects with the
audited schema:

    general: device_name, application, ip, mac, full_id
    @timestamp: ISO-8601 UTC (millisecond resolution)
    mqtt: retained, qos, message_value, topic, message_id, message_type, duplicate

Files are processed strictly line by line; each parsed object is reduced to a
compact ``MqttEvent`` and immediately discarded, so memory is independent of
file size. Telemetry exists only for the 14 sensors; no synthetic telemetry
is ever created for other devices.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from datasets.datasense.windowing import epoch_ns_from_iso


@dataclass(slots=True)
class MqttEvent:
    ts_ns: int
    internal_device_name: str | None
    application: str | None
    ip: str | None
    mac: str | None
    full_id: str | None
    topic: str | None
    message_type: str | None
    message_value: object
    qos: int | None
    retained: bool | None
    duplicate: bool | None
    message_id: int | None
    line_number: int


@dataclass
class NdjsonStats:
    lines_read: int = 0
    events_parsed: int = 0
    blank_lines: int = 0
    malformed_lines: int = 0
    missing_timestamp_lines: int = 0
    malformed_samples: list[str] | None = None


def parse_telemetry_line(line: str) -> MqttEvent | None:
    """Parse one NDJSON telemetry record into an MqttEvent (or None)."""
    obj = json.loads(line)
    ts_raw = obj.get("@timestamp")
    if ts_raw is None:
        return None
    ts_ns = epoch_ns_from_iso(str(ts_raw))
    general = obj.get("general") or {}
    mqtt = obj.get("mqtt") or {}
    message_id = mqtt.get("message_id")
    if isinstance(message_id, str):
        try:
            message_id = int(message_id)
        except ValueError:
            pass
    qos = mqtt.get("qos")
    if isinstance(qos, str):
        try:
            qos = float(qos)
            qos = int(qos) if qos.is_integer() else qos
        except ValueError:
            pass
    return MqttEvent(
        ts_ns=ts_ns,
        internal_device_name=_clean(general.get("device_name")),
        application=_clean(general.get("application")),
        ip=_clean(general.get("ip")),
        mac=_clean(general.get("mac")),
        full_id=_clean(general.get("full_id")),
        topic=_clean(mqtt.get("topic")),
        message_type=_clean(mqtt.get("message_type")),
        message_value=mqtt.get("message_value"),
        qos=qos,
        retained=mqtt.get("retained"),
        duplicate=mqtt.get("duplicate"),
        message_id=message_id,
        line_number=0,
    )


def _clean(value):
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def iter_mqtt_events(path: Path) -> "MqttEventStream":
    """Stream MqttEvents from an NDJSON file one line at a time."""
    return MqttEventStream(path)


class MqttEventStream:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.stats = NdjsonStats()
        self._events = None

    def __iter__(self):
        if self._events is None:
            self._events = self.events()
        return self._events

    def events(self):
        """Generator over parsed events; safe against malformed lines."""
        stats = self.stats
        stats.malformed_samples = []
        with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
            for line_number, line in enumerate(fh, start=1):
                stats.lines_read += 1
                stripped = line.strip()
                if not stripped:
                    stats.blank_lines += 1
                    continue
                try:
                    event = parse_telemetry_line(stripped)
                except (json.JSONDecodeError, ValueError, TypeError):
                    stats.malformed_lines += 1
                    if len(stats.malformed_samples) < 10:
                        stats.malformed_samples.append(stripped[:200])
                    continue
                if event is None:
                    stats.missing_timestamp_lines += 1
                    continue
                event.line_number = line_number
                stats.events_parsed += 1
                yield event
