"""Directed communication records: direction, aggregation, endpoints, bounds."""

import pytest

from conftest import (
    ATTACKER0_IP,
    ATTACKER0_MAC,
    BROKER_IP,
    BROKER_MAC,
    EDGE_IP,
    EDGE_MAC,
    SOIL_IP,
    SOIL_MAC,
    arp_packet,
    eth_frame,
    ipv4_packet,
    tcp_segment,
    udp_datagram,
)
from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.communication import (
    COMMUNICATION_FIELD_TYPES,
    CapacityExceededError,
    CommunicationWindowManager,
    EndpointResolver,
)
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.frame_decoder import decode_frame
from datasets.datasense.versions import (
    COMMUNICATION_FEATURE_SCHEMA_VERSION,
    EXTRACTOR_VERSION,
)
from datasets.datasense.windowing import WindowGrid

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


def _manager(**kwargs):
    grid = WindowGrid(START, window_seconds=5.0)
    manager = CommunicationWindowManager(
        grid, "scenario-x", _inventory(), **kwargs
    )
    return grid, manager


def _feed(manager, ts_ns, frame):
    view = decode_frame(frame)
    return manager.add_packet(ts_ns, view, len(frame), len(frame))


def test_direction_and_aggregation_preserved():
    _, manager = _manager()
    a_to_b = eth_frame(
        BROKER_MAC, SOIL_MAC, 0x0800,
        ipv4_packet(SOIL_IP, BROKER_IP, 6, tcp_segment(40000, 1883, 0x18)),
    )
    b_to_a = eth_frame(
        SOIL_MAC, BROKER_MAC, 0x0800,
        ipv4_packet(BROKER_IP, SOIL_IP, 6, tcp_segment(1883, 40000, 0x10)),
    )
    rows = []
    rows += _feed(manager, START + 1 * NS, a_to_b)
    rows += _feed(manager, START + 2 * NS, a_to_b)
    rows += _feed(manager, START + 3 * NS, b_to_a)
    rows += manager.finish()

    edges = {(r["src_entity_id"], r["dst_entity_id"]): r for r in rows}
    assert set(edges) == {("soil-sensor", "mqtt-broker"), ("mqtt-broker", "soil-sensor")}

    forward = edges[("soil-sensor", "mqtt-broker")]
    reverse = edges[("mqtt-broker", "soil-sensor")]
    assert forward["packet_count"] == 2
    assert reverse["packet_count"] == 1
    assert forward["captured_byte_count"] == 2 * len(a_to_b)
    assert reverse["wire_byte_count"] == len(b_to_a)
    assert forward["first_timestamp_utc"] <= forward["last_timestamp_utc"]
    assert forward["protocols"] == ["tcp"]
    assert forward["protocol_packet_counts"] == [2]
    assert forward["dst_ports"] == [1883]
    assert reverse["src_ports"] == [1883]
    assert forward["src_resolution_status"] == "resolved_mac"
    assert forward["dst_resolution_status"] == "resolved_mac"
    assert forward["extractor_version"] == EXTRACTOR_VERSION
    assert forward["schema_version"] == COMMUNICATION_FEATURE_SCHEMA_VERSION


def test_multiple_peers_no_cartesian_inference():
    _, manager = _manager()
    soil_to_broker = eth_frame(
        BROKER_MAC, SOIL_MAC, 0x0800,
        ipv4_packet(SOIL_IP, BROKER_IP, 17, udp_datagram(5000, 1883, b"x")),
    )
    edge_to_soil = eth_frame(
        SOIL_MAC, EDGE_MAC, 0x0800,
        ipv4_packet(EDGE_IP, SOIL_IP, 17, udp_datagram(5000, 9999, b"y")),
    )
    _feed(manager, START + NS, soil_to_broker)
    _feed(manager, START + 2 * NS, edge_to_soil)
    rows = manager.finish()

    pairs = {(r["src_entity_id"], r["dst_entity_id"]) for r in rows}
    assert pairs == {
        ("soil-sensor", "mqtt-broker"),
        ("edge1", "soil-sensor"),
    }
    assert ("soil-sensor", "edge1") not in pairs
    assert ("mqtt-broker", "edge1") not in pairs


def test_broadcast_kept_as_broadcast_edge_not_unicast():
    _, manager = _manager()
    who_has = eth_frame(
        "ff:ff:ff:ff:ff:ff", SOIL_MAC, 0x0806,
        arp_packet(SOIL_MAC, SOIL_IP, "00:00:00:00:00:00", EDGE_IP),
    )
    rows = _feed(manager, START + NS, who_has) + manager.finish()
    assert any(
        r["dst_entity_id"] == "broadcast"
        and r["broadcast_indicator"] is True
        and r["dst_resolution_status"] == "broadcast"
        and r["packet_count"] == 1
        and r["src_entity_id"] == "soil-sensor"
        for r in rows
    )


def test_unresolved_external_endpoint_representable():
    _, manager = _manager()
    external = eth_frame(
        "02:aa:bb:cc:dd:01", SOIL_MAC, 0x0800,
        ipv4_packet(SOIL_IP, "203.0.113.9", 6, tcp_segment(1234, 443, 0x02)),
    )
    rows = _feed(manager, START + NS, external) + manager.finish()
    edge = next(r for r in rows if r["src_entity_id"] == "soil-sensor")
    assert edge["dst_entity_id"] == "mac:02:aa:bb:cc:dd:01"
    assert edge["dst_resolution_status"] == "external"
    assert edge["dst_ip"] == "203.0.113.9"


def test_ip_resolved_status_when_only_ip_matches():
    resolver = EndpointResolver(_inventory())
    entity, status = resolver.resolve(mac=None, ip=EDGE_IP)
    assert (entity, status) == ("edge1", "resolved_ip")
    entity2, status2 = resolver.resolve(mac=BROKER_MAC, ip="10.9.9.9")
    assert (entity2, status2) == ("mqtt-broker", "resolved_mac")


def test_port_truncation_flag():
    grid = WindowGrid(START, window_seconds=5.0)
    manager = CommunicationWindowManager(grid, "scenario-x", _inventory())
    seen_dst_ports = set()
    for i in range(50):
        dport = 20000 + i
        frame = eth_frame(
            BROKER_MAC, SOIL_MAC, 0x0800,
            ipv4_packet(SOIL_IP, BROKER_IP, 6,
                        tcp_segment(40000 + i, dport, 0x02)),
        )
        seen_dst_ports.add(dport)
        manager.add_packet(START + i * 1000, decode_frame(frame), len(frame), len(frame))
    rows = manager.finish()
    edge = next(r for r in rows if r["src_entity_id"] == "soil-sensor")
    assert edge["dst_ports_truncated"] is True
    assert len(edge["dst_ports"]) <= 32
    assert set(edge["dst_ports"]) < seen_dst_ports


def test_protocol_summary_is_deterministic():
    _, manager = _manager()
    frames = [
        eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                  ipv4_packet(SOIL_IP, BROKER_IP, 17, udp_datagram(1, 2, b"a"))),
        eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                  ipv4_packet(SOIL_IP, BROKER_IP, 17, udp_datagram(1, 2, b"b"))),
        eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                  ipv4_packet(SOIL_IP, BROKER_IP, 6, tcp_segment(3, 4, 0x10))),
    ]
    for i, f in enumerate(frames):
        _feed(manager, START + i * 1000, f)
    row = manager.finish()[0]
    assert row["protocols"] == ["tcp", "udp"]
    assert row["protocol_packet_counts"] == [1, 2]


def test_schema_fields_complete():
    expected = {
        "scenario_id", "window_id", "window_start_utc", "window_end_utc",
        "src_entity_id", "dst_entity_id",
        "src_resolution_status", "dst_resolution_status",
        "src_mac", "dst_mac", "src_ip", "dst_ip",
        "packet_count", "captured_byte_count", "wire_byte_count",
        "first_timestamp_utc", "last_timestamp_utc",
        "protocols", "protocol_packet_counts",
        "src_ports", "dst_ports",
        "src_ports_truncated", "dst_ports_truncated",
        "broadcast_indicator", "multicast_indicator",
        "raw_source", "extractor_version", "schema_version",
    }
    assert set(COMMUNICATION_FIELD_TYPES) == expected


def test_multicast_destination_flagged():
    _, manager = _manager()
    frame = eth_frame(
        "01:00:5e:00:00:01", SOIL_MAC, 0x0800,
        ipv4_packet(SOIL_IP, "224.0.0.1", 17, udp_datagram(1, 2, b"m")),
    )
    rows = _feed(manager, START + NS, frame) + manager.finish()
    mrow = next(r for r in rows if r["multicast_indicator"])
    assert mrow["dst_entity_id"] == "multicast"


def test_capacity_enforced_third_live_edge_fails_explicitly():
    grid = WindowGrid(START, window_seconds=5.0)
    manager = CommunicationWindowManager(
        grid, "scenario-x", _inventory(), active_window_capacity=2
    )
    frames = [
        eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                  ipv4_packet(SOIL_IP, BROKER_IP, 6, tcp_segment(40000, 1883, 0x18))),
        eth_frame(SOIL_MAC, EDGE_MAC, 0x0800,
                  ipv4_packet(EDGE_IP, SOIL_IP, 6, tcp_segment(5000, 9999, 0x10))),
    ]
    for i, f in enumerate(frames):
        manager.add_packet(START + i * 1000, decode_frame(f), len(f), len(f))
    assert len(manager.edges) == 2

    third = eth_frame(BROKER_MAC, ATTACKER0_MAC, 0x0800,
                      ipv4_packet(ATTACKER0_IP, BROKER_IP, 6,
                                  tcp_segment(7777, 80, 0x02)))
    with pytest.raises(CapacityExceededError) as exc_info:
        manager.add_packet(START + 3 * 1000, decode_frame(third), len(third), len(third))
    assert exc_info.value.live_edges == 2
    assert exc_info.value.capacity == 2
    assert len(manager.edges) == 2
    assert set(manager.edges) == {
        (0, "soil-sensor", "mqtt-broker"),
        (0, "edge1", "soil-sensor"),
    }
    assert manager.diagnostics["capacity_exceeded_events"] == 1


def test_capacity_freed_after_watermark_finalization():
    grid = WindowGrid(START, window_seconds=5.0)
    manager = CommunicationWindowManager(
        grid,
        "scenario-x",
        _inventory(),
        active_window_capacity=2,
        max_event_lateness_ns=0,
    )

    def pair_frame(sport):
        return eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                         ipv4_packet(SOIL_IP, BROKER_IP, 6,
                                     tcp_segment(sport, 1883, 0x18)))

    def other_frame(dport):
        return eth_frame(SOIL_MAC, EDGE_MAC, 0x0800,
                         ipv4_packet(EDGE_IP, SOIL_IP, 17,
                                     udp_datagram(5000, dport, b"x")))

    manager.add_packet(START, decode_frame(pair_frame(40000)), 60, 60)
    rows = manager.add_packet(START + 60 * 10**9 + NS, decode_frame(other_frame(1111)), 60, 60)
    assert rows, "watermark must finalize the old window and free capacity"
    third = eth_frame(SOIL_MAC, EDGE_MAC, 0x0800,
                      ipv4_packet(EDGE_IP, SOIL_IP, 17,
                                  udp_datagram(5001, 2222, b"y")))
    manager.add_packet(START + 60 * 10**9 + 2 * NS, decode_frame(third), 60, 60)
    assert len(manager.edges) <= 2
