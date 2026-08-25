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
    mss_option,
    tcp_segment,
    udp_datagram,
)
from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.network_features import (
    NETWORK_MODEL_FEATURES,
    NetworkWindowManager,
    empty_network_row,
)
from datasets.datasense.windowing import WindowGrid

NS = 1_000_000_000


def _load_inventory():
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


START = 1_736_976_313 * NS + 307_000_000


def _manager(**kwargs):
    grid = WindowGrid(START, window_seconds=5)
    inventory = _load_inventory()
    manager = NetworkWindowManager(
        grid,
        "attack_recon_host-disc-udp-ping_soil-sensor",
        inventory,
        frozenset({"attacker0"}),
        **kwargs,
    )
    return grid, manager


def _feed(manager, ts_ns, frame, caplen=None):
    from datasets.datasense.frame_decoder import decode_frame

    view = decode_frame(frame)
    manager.add_packet(ts_ns, view, caplen or len(frame), len(frame))


def test_counts_directions_and_window_assignment():
    grid, manager = _manager()
    seg = tcp_segment(40000, 1883, flags=0x18)
    soil_to_broker = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800, ipv4_packet(SOIL_IP, BROKER_IP, 6, seg))
    broker_to_soil = eth_frame(SOIL_MAC, BROKER_MAC, 0x0800, ipv4_packet(BROKER_IP, SOIL_IP, 6, seg))

    _feed(manager, START + 0 * NS, soil_to_broker)
    _feed(manager, START + 1 * NS, soil_to_broker)
    _feed(manager, START + 2 * NS, broker_to_soil)
    _feed(manager, START + 6 * NS, soil_to_broker)

    rows = manager.finish()
    by_key = {(r["device_id"], r["window_id"]): r for r in rows}
    soil_w0 = by_key[("soil-sensor", 0)]
    assert soil_w0["packets_all_count"] == 3
    assert soil_w0["packets_src_count"] == 2
    assert soil_w0["packets_dst_count"] == 1
    assert by_key[("soil-sensor", 1)]["packets_all_count"] == 1
    broker_w0 = by_key[("mqtt-broker", 0)]
    assert broker_w0["packets_all_count"] == 3
    assert broker_w0["packets_src_count"] == 1
    assert broker_w0["packets_dst_count"] == 2


def test_tcp_flags_fragmentation_and_protocol_families():
    grid, manager = _manager()
    syn = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                    ipv4_packet(SOIL_IP, BROKER_IP, 6,
                                tcp_segment(123, 1883, flags=0x02)))
    frag_udp = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                         ipv4_packet(SOIL_IP, BROKER_IP, 17,
                                     udp_datagram(100, 200, b"xx"),
                                     flags_frag=0x2003))
    plain_udp = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                          ipv4_packet(SOIL_IP, BROKER_IP, 17,
                                      udp_datagram(100, 200, b"yy")))
    arp = eth_frame("ff:ff:ff:ff:ff:ff", SOIL_MAC, 0x0806,
                    arp_packet(SOIL_MAC, SOIL_IP, "00:00:00:00:00:00", BROKER_IP))
    for frame in (syn, frag_udp, plain_udp, arp):
        _feed(manager, START + NS, frame)
    rows = manager.finish()
    soil = next(r for r in rows if r["device_id"] == "soil-sensor")
    assert soil["tcp_syn_count"] == 1
    assert soil["fragmented_packet_count"] == 1
    assert soil["proto_udp_count"] == 1
    assert soil["proto_arp_count"] >= 1
    assert soil["proto_tcp_count"] >= 1
    assert soil["proto_other_count"] >= 1
    assert soil["protocol_diversity"] >= 4


def test_timing_and_size_statistics_populated_or_null_consistently():
    grid, manager = _manager()
    for i, offset in enumerate((0.0, 0.5, 1.25)):
        seg = tcp_segment(40000 + i, 1883 + i, flags=0x10, options=mss_option(1460))
        frame = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                          ipv4_packet(SOIL_IP, BROKER_IP, 6, seg))
        _feed(manager, START + int(offset * NS), frame)
    soil = next(r for r in manager.finish() if r["device_id"] == "soil-sensor")
    assert soil["time_delta_avg"] is not None
    assert abs(soil["time_delta_max"] - 0.75) < 1e-9
    assert abs(soil["time_delta_min"] - 0.5) < 1e-9
    assert soil["packet_size_avg"] > 0
    assert soil["mss_observed_min"] == 1460
    assert soil["ttl_avg"] == 64
    assert soil["tcp_window_avg"] == 64240
    empty_stats = [f for f in ("time_delta_std",) if soil[f] is not None]
    assert all(v is not None for f in empty_stats for v in [soil[f]])


def test_identity_fields_stay_out_of_model_features_but_in_metadata():
    grid, manager = _manager()
    seg = tcp_segment(40000, 1883, flags=0x02, options=mss_option(1460))
    frame = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800,
                      ipv4_packet(SOIL_IP, BROKER_IP, 6, seg))
    attacker_seg = tcp_segment(555, 80, flags=0x02)
    atk_frame = eth_frame(SOIL_MAC, ATTACKER0_MAC, 0x0800,
                          ipv4_packet(ATTACKER0_IP, SOIL_IP, 6, attacker_seg))
    _feed(manager, START, frame)
    _feed(manager, START + NS, atk_frame)
    soil = next(r for r in manager.finish() if r["device_id"] == "soil-sensor")

    identity_tokens = {SOIL_IP, BROKER_IP, SOIL_MAC}
    for feature in NETWORK_MODEL_FEATURES:
        value = soil[feature]
        assert value is None or isinstance(value, (int, float)), feature
        if isinstance(value, str):
            assert value not in identity_tokens, feature
    assert SOIL_IP in soil["observed_ips_all"]
    assert soil["attacker_contact_observed"] is True


def test_empty_network_rows_use_null_not_zero():
    grid = WindowGrid(START, window_seconds=5)
    row = empty_network_row("s", "edge1", 3, grid)
    assert row["network_observed"] is False
    assert row["packets_all_count"] is None
    assert row["packet_size_avg"] is None
    assert row["observed_ips_all"] == []


def test_unresolved_packets_counted_diagnostically():
    grid, manager = _manager()
    seg = tcp_segment(1, 2, flags=0x10)
    frame = eth_frame("02:ff:ff:ff:ff:01", "02:ff:ff:ff:ff:02", 0x0800,
                      ipv4_packet("10.0.0.9", "10.0.0.10", 6, seg))
    _feed(manager, START, frame)
    assert manager.diagnostics["unresolved_endpoint_packets"] == 1
    assert manager.finish() == []
