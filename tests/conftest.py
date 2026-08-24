"""Shared fixtures: synthetic bounded PCAP/PCAPNG/NDJSON builders.

These let parser, windowing and feature tests run without the ~250 GB local
dataset. Real-data integration tests live in test_raw_sessions.py and skip
clearly when the dataset is absent.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

NS = 1_000_000_000


def mac_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def eth_frame(dst: str, src: str, etype: int, body: bytes) -> bytes:
    return mac_bytes(dst) + mac_bytes(src) + struct.pack(">H", etype) + body


def ieee8023_frame(dst: str, src: str, payload: bytes) -> bytes:
    return mac_bytes(dst) + mac_bytes(src) + struct.pack(">H", len(payload)) + payload


def snap_frame(dst: str, src: str, inner_etype: int, ip_body: bytes) -> bytes:
    length = 8 + len(ip_body)
    llc_snap = b"\xaa\xaa\x03\x00\x00\x00" + struct.pack(">H", inner_etype)
    return (
        mac_bytes(dst)
        + mac_bytes(src)
        + struct.pack(">H", length)
        + llc_snap
        + ip_body
    )


def vlan_eth_frame(dst: str, src: str, vid: int, inner_etype: int, body: bytes) -> bytes:
    tci = struct.pack(">H", vid)
    return (
        mac_bytes(dst)
        + mac_bytes(src)
        + struct.pack(">H", 0x8100)
        + tci
        + struct.pack(">H", inner_etype)
        + body
    )


def ipv4_packet(
    src_ip: str,
    dst_ip: str,
    proto: int,
    l4_body: bytes,
    ttl: int = 64,
    total_len: int | None = None,
    flags_frag: int = 0x4000,
) -> bytes:
    ihl_words = 5
    if total_len is None:
        total_len = ihl_words * 4 + len(l4_body)
    header = struct.pack(
        ">BBHHHBBH4s4s",
        (4 << 4) | ihl_words,
        0x00,
        total_len,
        0x1234,
        flags_frag,
        ttl,
        proto,
        0x0000,
        bytes(int(x) for x in src_ip.split(".")),
        bytes(int(x) for x in dst_ip.split(".")),
    )
    return header + l4_body


def tcp_segment(
    sport: int,
    dport: int,
    flags: int,
    window: int = 64240,
    options: bytes = b"",
    payload: bytes = b"",
) -> bytes:
    data_offset_words = 5 + (len(options) + 3) // 4
    header = struct.pack(
        ">HHIIBBHHH",
        sport,
        dport,
        1000,
        2000,
        (data_offset_words << 4),
        flags,
        window,
        0xFFFF,
        0x0000,
    )
    padded_options = options + bytes((4 - len(options) % 4) % 4)
    return header + padded_options + payload


def udp_datagram(sport: int, dport: int, payload: bytes) -> bytes:
    return struct.pack(">HHHH", sport, dport, 8 + len(payload), 0x0000) + payload


def arp_packet(sender_mac: str, sender_ip: str, target_mac: str, target_ip: str) -> bytes:
    return struct.pack(">HHBBH", 1, 0x0800, 6, 4, 1) + mac_bytes(sender_mac) + bytes(
        int(x) for x in sender_ip.split(".")
    ) + mac_bytes(target_mac) + bytes(int(x) for x in target_ip.split("."))


def mss_option(mss: int) -> bytes:
    return struct.pack(">BBH", 2, 4, mss)


SOIL_MAC = "f0:08:d1:ce:cf:0c"
BROKER_MAC = "dc:a6:32:dc:28:46"
EDGE_MAC = "dc:a6:32:dc:27:d4"
ATTACKER0_MAC = "e4:5f:01:55:90:c1"

SOIL_IP = "192.168.1.12"
BROKER_IP = "192.168.1.193"
EDGE_IP = "192.168.1.195"
ATTACKER0_IP = "192.168.1.100"


class PcapBuilder:
    def __init__(self, nanoseconds: bool = False, endian: str = "<"):
        self.records: list[tuple[int, bytes, int]] = []
        self.nanoseconds = nanoseconds
        self.endian = endian

    def add(self, ts_ns: int, frame: bytes, wirelen: int | None = None):
        self.records.append((ts_ns, frame, wirelen if wirelen is not None else len(frame)))

    def build(self, path: Path) -> Path:
        magic = {
            ("<", False): b"\xd4\xc3\xb2\xa1",
            (">", False): b"\xa1\xb2\xc3\xd4",
            ("<", True): b"\x4d\x3c\xb2\xa1",
            (">", True): b"\xa1\xb2\x3c\x4d",
        }[(self.endian, self.nanoseconds)]
        e = self.endian
        with open(path, "wb") as fh:
            fh.write(magic)
            fh.write(struct.pack(e + "HHiIII", 2, 4, 0, 0, 1500, 1))
            for ts_ns, frame, wirelen in self.records:
                frac_div = 1 if self.nanoseconds else 1000
                sec, frac = divmod(ts_ns, NS)
                frac //= frac_div
                fh.write(struct.pack(e + "IIII", sec, frac, len(frame), wirelen))
                fh.write(frame)
        return path


class PcapngBuilder:
    def __init__(self, tsresol_byte: int = 9):
        assert tsresol_byte == 9 or tsresol_byte == 6
        self.tsresol = tsresol_byte
        self.records: list[tuple[int, bytes, int]] = []

    def add(self, ts_ns: int, frame: bytes, wirelen: int | None = None):
        self.records.append((ts_ns, frame, wirelen if wirelen is not None else len(frame)))

    def build(self, path: Path) -> Path:
        with open(path, "wb") as fh:
            shb_body = struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1)
            shb_len = 12 + len(shb_body)
            fh.write(struct.pack("<II", 0x0A0D0D0A, shb_len))
            fh.write(shb_body)
            fh.write(struct.pack("<I", shb_len))

            idb_body = struct.pack("<HHI", 1, 0, 0)
            idb_body += struct.pack("<HH", 9, 1) + bytes([self.tsresol]) + b"\x00" * 3
            idb_body += struct.pack("<HH", 0, 0)
            idb_len = 12 + len(idb_body)
            fh.write(struct.pack("<II", 0x00000001, idb_len))
            fh.write(idb_body)
            fh.write(struct.pack("<I", idb_len))

            for ts_ns, frame, wirelen in self.records:
                if self.tsresol == 9:
                    ticks = ts_ns
                    hi, lo = divmod(ticks, 1 << 32)
                else:
                    ticks = ts_ns // 1000
                    hi, lo = divmod(ticks, 1 << 32)
                padded = (len(frame) + 3) & ~3
                epb_len = 12 + 20 + padded + 4
                fh.write(struct.pack("<II", 0x00000006, epb_len))
                fh.write(struct.pack("<IIIII", 0, hi, lo, len(frame), wirelen))
                fh.write(frame)
                fh.write(b"\x00" * (padded - len(frame)))
                fh.write(struct.pack("<I", epb_len))
        return path


DEFAULT_DEVICES_ROWS = [
    dict(mac="28:87:ba:bd:c6:6c", ip="192.168.1.1", device_name="router", role="router", type="network", main_topic=""),
    dict(mac=BROKER_MAC, ip=BROKER_IP, device_name="mqtt-broker", role="mqtt-broker", type="raspberry-pie", main_topic=""),
    dict(mac=EDGE_MAC, ip=EDGE_IP, device_name="edge1", role="edge", type="raspberry-pie", main_topic=""),
    dict(mac=SOIL_MAC, ip=SOIL_IP, device_name="soil-sensor", role="sensor", type="sensor", main_topic="iiot/soil"),
    dict(mac="08:b6:1f:82:1c:3c", ip="192.168.1.21", device_name="motion-sensor", role="sensor", type="sensor", main_topic="iiot/motion"),
    dict(mac="08:b6:1f:84:66:78", ip="192.168.1.11", device_name="water-sensor", role="sensor", type="sensor", main_topic="iiot/water"),
    dict(mac=ATTACKER0_MAC, ip=ATTACKER0_IP, device_name="attacker0", role="attacker", type="raspberry-pie", main_topic=""),
]


def write_devices_csv(path: Path, rows=None) -> Path:
    import csv

    rows = rows or DEFAULT_DEVICES_ROWS
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["mac", "ip", "device_name", "role", "type", "main_topic"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_attacks_csv(path: Path, rows: list[dict]) -> Path:
    import csv

    fields = ["filename", "data_type", "category", "attack_name", "attack_target", "doc_count", "start", "end", "start_timestamp", "end_timestamp"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_ndjson(path: Path, records: list[dict]) -> Path:
    import json

    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return path


def mqtt_record(
    ts_iso: str,
    device_name: str = "ard-w-02",
    application: str = "Soil",
    ip: str = SOIL_IP,
    mac: str = SOIL_MAC,
    topic: str = "iiot/soil",
    value=280.0,
    message_type: str = "numeric",
    qos: int = 0,
    retained: bool = False,
    duplicate: bool = False,
    message_id: int = 0,
) -> dict:
    return {
        "general": {
            "device_name": device_name,
            "application": application,
            "ip": ip,
            "mac": mac,
            "full_id": f"{mac}_{ip}_iiot/soil",
        },
        "@timestamp": ts_iso,
        "mqtt": {
            "retained": retained,
            "qos": qos,
            "message_value": value,
            "topic": topic,
            "message_id": message_id,
            "message_type": message_type,
            "duplicate": duplicate,
        },
    }


@pytest.fixture
def tmp_store(tmp_path):
    return tmp_path / "store"


def write_min_pcapng(path: Path, offsets_seconds=(0.5, 6.25), start_ns=1_736_976_313 * NS + 307_000_000) -> Path:
    """Minimal valid PCAPNG with one soil->broker TCP packet per offset."""
    import struct

    seg = struct.pack(">HHIIBBHHH", 40000, 1883, 1, 2, 0x50, 0x18, 64240, 0xFFFF, 0)
    ip = struct.pack(
        ">BBHHHBBH4s4s",
        0x45,
        0,
        20 + len(seg),
        1,
        0x4000,
        64,
        6,
        0,
        bytes(int(x) for x in "192.168.1.12".split(".")),
        bytes(int(x) for x in "192.168.1.193".split(".")),
    )
    frame = (
        mac_bytes("dc:a6:32:dc:28:46")
        + mac_bytes(SOIL_MAC)
        + struct.pack(">H", 0x0800)
        + ip
        + seg
    )
    with open(path, "wb") as fh:
        shb_body = struct.pack("<IHHq", 0x1A2B3C4D, 1, 0, -1)
        fh.write(struct.pack("<II", 0x0A0D0D0A, 12 + len(shb_body)))
        fh.write(shb_body)
        fh.write(struct.pack("<I", 12 + len(shb_body)))
        idb_body = struct.pack("<HHI", 1, 0, 0)
        idb_body += struct.pack("<HH", 9, 1) + bytes([9]) + b"\x00" * 3
        idb_body += struct.pack("<HH", 0, 0)
        fh.write(struct.pack("<II", 0x00000001, 12 + len(idb_body)))
        fh.write(idb_body)
        fh.write(struct.pack("<I", 12 + len(idb_body)))
        for offset in offsets_seconds:
            ts_ns = start_ns + int(offset * NS)
            hi, lo = divmod(ts_ns, 1 << 32)
            padded = (len(frame) + 3) & ~3
            epb_len = 12 + 20 + padded + 4
            fh.write(struct.pack("<II", 6, epb_len))
            fh.write(struct.pack("<IIIII", 0, hi, lo, len(frame), len(frame)))
            fh.write(frame)
            fh.write(b"\x00" * (padded - len(frame)))
            fh.write(struct.pack("<I", epb_len))
    return path


def write_min_ndjson(path: Path, start_iso="2025-01-15T21:25:13.807Z") -> Path:
    import json

    records = []
    for i, offset_ms in enumerate((0, 1000)):
        ts = epoch_shift(start_iso, offset_ms)
        records.append(
            {
                "general": {
                    "device_name": "ard-w-02",
                    "application": "Soil",
                    "ip": "192.168.1.12",
                    "mac": SOIL_MAC.upper(),
                    "full_id": f"{SOIL_MAC}_192.168.1.12_iiot/soil",
                },
                "@timestamp": ts,
                "mqtt": {
                    "retained": False,
                    "qos": 0,
                    "message_value": 280.0 + i,
                    "topic": "iiot/soil",
                    "message_id": i,
                    "message_type": "numeric",
                    "duplicate": False,
                },
            }
        )
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
    return path


def epoch_shift(iso: str, delta_ms: int) -> str:
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    dt = dt + timedelta(milliseconds=delta_ms)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


SCENARIO_ID = "attack_recon_host-disc-udp-ping_soil-sensor"


@pytest.fixture
def tmp_extracted_store(tmp_path):
    from datasets.datasense.catalog import build_session_record
    from datasets.datasense.devices import DeviceInventory, DeviceRecord
    from datasets.datasense.extraction import ExtractionEngine
    from datasets.datasense.profiles import resolve_profile

    store = tmp_path / "store"
    pcap = write_min_pcapng(tmp_path / "s.pcapng")
    ndjson = write_min_ndjson(tmp_path / "s.json")
    inventory = DeviceInventory(
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
    session = build_session_record(
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
    engine = ExtractionEngine(
        store_root=store,
        inventory=inventory,
        settings=resolve_profile("low"),
        window_seconds=5.0,
    )
    state = engine.run_session(session)
    assert state["status"] == "completed"
    return store, SCENARIO_ID
