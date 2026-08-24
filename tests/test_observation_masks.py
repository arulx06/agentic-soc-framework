from conftest import BROKER_IP, BROKER_MAC, SOIL_IP, SOIL_MAC, eth_frame, ipv4_packet, tcp_segment
from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.extraction import iter_behavior_rows, iter_network_rows
from datasets.datasense.windowing import WindowGrid

NS = 1_000_000_000
START = 1_736_976_313 * NS + 307_000_000


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


class _Session:
    scenario_id = "attack_recon_host-disc-udp-ping_soil-sensor"
    targets = ["soil-sensor"]
    session_start_ns = START
    raw_pcap_path = None
    raw_json_path = None

    def __init__(self):
        self.is_attack = True
        self.attack_category = "recon"


def _write_pcap(tmp_path, offsets_seconds):
    import struct

    path = tmp_path / "cap.pcapng"
    frames = []
    for offset in offsets_seconds:
        seg = tcp_segment(40000, 1883, flags=0x18)
        body = ipv4_packet(SOIL_IP, BROKER_IP, 6, seg)
        frame = (
            bytes.fromhex(BROKER_MAC.replace(":", ""))
            + bytes.fromhex(SOIL_MAC.replace(":", ""))
            + struct.pack(">H", 0x0800)
            + body
        )
        frames.append((START + int(offset * NS), frame))

    def build():
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
            for ts_ns, frame in frames:
                hi, lo = divmod(ts_ns, 1 << 32)
                padded = (len(frame) + 3) & ~3
                epb_len = 12 + 20 + padded + 4
                fh.write(struct.pack("<II", 6, epb_len))
                fh.write(struct.pack("<IIIII", 0, hi, lo, len(frame), len(frame)))
                fh.write(frame)
                fh.write(b"\x00" * (padded - len(frame)))
                fh.write(struct.pack("<I", epb_len))

    build()
    return path


def test_dense_fill_marks_unobserved_cells(tmp_path):
    session = _Session()
    session.raw_pcap_path = _write_pcap(tmp_path, [0.5, 11.25])
    collect = {}
    rows = list(
        iter_network_rows(
            session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024, 1 << 20,
            collect=collect,
        )
    )
    by_key = {(r["device_id"], r["window_id"]): r for r in rows}

    soil_w0 = by_key[("soil-sensor", 0)]
    broker_w1 = by_key[("mqtt-broker", 1)]
    soil_w2 = by_key[("soil-sensor", 2)]

    assert soil_w0["network_observed"] is True and soil_w0["packets_all_count"] == 1
    assert broker_w1["network_observed"] is False
    assert broker_w1["packets_all_count"] is None
    assert soil_w1_unobserved if False else True
    soil_w1 = by_key[("soil-sensor", 1)]
    assert soil_w1["network_observed"] is False
    assert soil_w1["packets_all_count"] is None
    max_wid = collect["network_max_window_id"]
    assert max_wid == 2


def test_observed_zero_distinct_from_missing(tmp_path):
    session = _Session()
    session.raw_pcap_path = _write_pcap(tmp_path, [0.5])
    rows = list(
        iter_network_rows(session, _inventory(), 5.0, 10**9, 60 * 10**9, 1024, 1 << 20)
    )
    soil_w0 = next(r for r in rows if r["device_id"] == "soil-sensor" and r["window_id"] == 0)
    motion_w0 = next(r for r in rows if r["device_id"] == "motion-sensor" and r["window_id"] == 0)
    assert soil_w0["network_observed"] is True and soil_w0["packets_all_count"] > 0
    assert motion_w0["network_observed"] is False and motion_w0["packets_all_count"] is None
