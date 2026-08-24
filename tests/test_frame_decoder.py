import struct

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
    ieee8023_frame,
    ipv4_packet,
    mss_option,
    snap_frame,
    tcp_segment,
    udp_datagram,
    vlan_eth_frame,
)

from datasets.datasense.frame_decoder import decode_frame


def test_ethernet_ipv4_tcp_decode():
    seg = tcp_segment(52789, 1883, flags=0x12, options=mss_option(1460))
    frame = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800, ipv4_packet(SOIL_IP, BROKER_IP, 6, seg))
    view = decode_frame(frame)
    assert view.src_mac == SOIL_MAC
    assert view.dst_mac == BROKER_MAC
    assert view.l3_proto == "tcp"
    assert view.sport == 52789
    assert view.dport == 1883
    assert (view.tcp_flags or 0) & 0x02
    assert view.mss == 1460
    assert view.ip_total_len == 20 + len(seg)
    assert view.ttl == 64
    assert not view.ip_mf
    assert view.payload_length == len(seg) - 20 - 4


def test_udp_and_icmp_decode():
    udp_body = udp_datagram(53, 5353, b"\x01\x02")
    frame = eth_frame(EDGE_MAC, SOIL_MAC, 0x0800, ipv4_packet(SOIL_IP, EDGE_IP, 17, udp_body))
    view = decode_frame(frame)
    assert view.l3_proto == "udp"
    assert view.sport == 53 and view.dport == 5353

    icmp_body = struct.pack("!BBH", 8, 0, 0) + b"pingpayload"
    frame2 = eth_frame(SOIL_MAC, EDGE_MAC, 0x0800, ipv4_packet(EDGE_IP, SOIL_IP, 1, icmp_body))
    view2 = decode_frame(frame2)
    assert view2.l3_proto == "icmp"
    assert view2.icmp_type == 8


def test_arp_decode_participants():
    body = arp_packet(SOIL_MAC, SOIL_IP, "00:00:00:00:00:00", BROKER_IP)
    frame = eth_frame("ff:ff:ff:ff:ff:ff", SOIL_MAC, 0x0806, body)
    view = decode_frame(frame)
    assert view.l3_proto == "arp"
    assert view.arp_sender_ip == SOIL_IP
    assert view.arp_target_ip == BROKER_IP
    assert view.dst_mac == "ff:ff:ff:ff:ff:ff"


def test_vlan_tagged_frame():
    seg = tcp_segment(1234, 80, flags=0x10)
    inner = ipv4_packet(SOIL_IP, EDGE_IP, 6, seg)
    frame = vlan_eth_frame(EDGE_MAC, SOIL_MAC, vid=100, inner_etype=0x0800, body=inner)
    view = decode_frame(frame)
    assert view.vlan_tags == 1
    assert view.ethertype == 0x0800
    assert view.dport == 80
    assert view.header_length >= 18 + 20 + 20


def test_ieee8023_llc_snap_ipv4():
    seg = tcp_segment(4444, 5555, flags=0x04)
    ip = ipv4_packet(SOIL_IP, EDGE_IP, 6, seg)
    frame = snap_frame(EDGE_MAC, SOIL_MAC, 0x0800, ip)
    view = decode_frame(frame)
    assert view.is_etherII is False
    assert view.ethertype == 0x0800
    assert view.l3_proto == "tcp"
    assert view.tcp_flags == 0x04


def test_ieee8023_pure_llc_is_other():
    payload = b"\x42\x42" + b"\x00" * 10
    frame = ieee8023_frame(EDGE_MAC, SOIL_MAC, payload)
    view = decode_frame(frame)
    assert view.is_etherII is False
    assert view.ethertype is None
    assert view.l3_proto == "other"


def test_fragmented_ipv4_skips_l4():
    ip = ipv4_packet(
        SOIL_IP,
        BROKER_IP,
        17,
        udp_datagram(1000, 2000, b"data"),
        flags_frag=0x2001,
    )
    frame = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800, ip)
    view = decode_frame(frame)
    assert view.ip_mf is True
    assert view.ip_frag_offset == 1


def test_gso_oversized_frame_headers_still_parse():
    big_payload = b"\xee" * 60_000
    seg = tcp_segment(999, 1883, flags=0x18, payload=big_payload)
    ip = ipv4_packet(SOIL_IP, BROKER_IP, 6, seg)
    frame = eth_frame(BROKER_MAC, SOIL_MAC, 0x0800, ip)
    view = decode_frame(frame)
    assert view.l3_proto == "tcp"
    assert view.payload_length == len(big_payload)


def test_runt_frame_returns_none():
    assert decode_frame(b"\x00" * 8) is None
