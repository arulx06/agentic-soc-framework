"""Header-only frame decoding for captured Ethernet packets.

Decodes only header fields needed for feature extraction and never retains
payload bytes. Handles the audited framing variants:

  * Ethernet II (ethertype >= 1536)
  * IEEE 802.3 length-field frames with LLC or SNAP payloads (benign capture)
  * 802.1Q / 802.1ad VLAN tags
  * ARP, IPv4, IPv6, TCP (incl. MSS option), UDP, ICMP

All multi-byte network fields are big-endian per the respective protocols.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP = 0x0806
ETHERTYPE_VLAN = 0x8100
ETHERTYPE_QINQ = 0x88A8
ETHERTYPE_IPV6 = 0x86DD

IPPROTO_ICMP = 1
IPPROTO_TCP = 6
IPPROTO_UDP = 17
IPPROTO_ICMPV6 = 58

TCP_FLAG_FIN = 0x01
TCP_FLAG_SYN = 0x02
TCP_FLAG_RST = 0x04
TCP_FLAG_PSH = 0x08
TCP_FLAG_ACK = 0x10
TCP_FLAG_URG = 0x20

L3_TCP = "tcp"
L3_UDP = "udp"
L3_ICMP = "icmp"
L3_ICMPV6 = "icmpv6"
L3_ARP = "arp"
L3_OTHER = "other"

BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"


def format_mac(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def format_ipv4(raw: bytes) -> str:
    return ".".join(str(b) for b in raw)


@dataclass(slots=True)
class FrameView:
    src_mac: str
    dst_mac: str
    l2_header_len: int
    is_etherII: bool
    vlan_tags: int
    l3_proto: str
    ethertype: int | None
    src_ip: str | None = None
    dst_ip: str | None = None
    ttl: int | None = None
    ip_total_len: int | None = None
    ip_header_len: int | None = None
    ip_df: bool = False
    ip_mf: bool = False
    ip_frag_offset: int = 0
    sport: int | None = None
    dport: int | None = None
    tcp_flags: int | None = None
    tcp_window: int | None = None
    tcp_header_len: int | None = None
    udp_length: int | None = None
    icmp_type: int | None = None
    mss: int | None = None
    arp_sender_mac: str | None = None
    arp_sender_ip: str | None = None
    arp_target_mac: str | None = None
    arp_target_ip: str | None = None

    @property
    def header_length(self) -> int:
        total = self.l2_header_len + (self.ip_header_len or 0)
        if self.l3_proto == L3_TCP:
            total += self.tcp_header_len or 20
        elif self.l3_proto == L3_UDP:
            total += 8
        elif self.l3_proto in (L3_ICMP, L3_ICMPV6):
            total += 8
        return total

    @property
    def payload_length(self) -> int:
        ip_header = self.ip_header_len or 0
        if self.ip_total_len is None:
            return 0
        inner = self.ip_total_len - ip_header
        if self.l3_proto == L3_TCP:
            return max(0, inner - (self.tcp_header_len or 20))
        if self.l3_proto == L3_UDP:
            return max(0, min(inner - 8, (self.udp_length or inner + 8) - 8))
        if self.l3_proto in (L3_ICMP, L3_ICMPV6):
            return max(0, inner - 8)
        return max(0, inner)


def _decode_l4(view: FrameView, buf: bytes, offset: int) -> None:
    proto = view.l3_proto
    if proto == L3_TCP and len(buf) >= offset + 20:
        sport, dport = struct.unpack(">HH", buf[offset : offset + 4])
        window = struct.unpack(">H", buf[offset + 14 : offset + 16])[0]
        flags = buf[offset + 13]
        data_off = ((buf[offset + 12] >> 4) & 0xF) * 4
        view.sport = sport
        view.dport = dport
        view.tcp_flags = flags
        view.tcp_window = window
        view.tcp_header_len = data_off
        opt_end = min(offset + data_off, len(buf))
        pos = offset + 20
        while pos + 1 < opt_end:
            kind = buf[pos]
            if kind == 0:
                break
            if kind == 1:
                pos += 1
                continue
            if pos + 1 >= opt_end:
                break
            olen = buf[pos + 1]
            if olen < 2:
                break
            if kind == 2 and olen == 4 and pos + 4 <= opt_end:
                view.mss = struct.unpack(">H", buf[pos + 2 : pos + 4])[0]
            pos += olen
    elif proto == L3_UDP and len(buf) >= offset + 8:
        sport, dport, ulen = struct.unpack(">HHH", buf[offset : offset + 6])
        view.sport = sport
        view.dport = dport
        view.udp_length = ulen
    elif proto in (L3_ICMP, L3_ICMPV6) and len(buf) >= offset + 2:
        view.icmp_type = buf[offset]


def decode_frame(buf: bytes) -> FrameView | None:
    """Decode a captured Ethernet frame into header fields (no payload kept)."""
    if len(buf) < 14:
        return None
    dst_raw = buf[0:6]
    src_raw = buf[6:12]
    type_or_len = struct.unpack(">H", buf[12:14])[0]

    view = FrameView(
        src_mac=format_mac(src_raw),
        dst_mac=format_mac(dst_raw),
        l2_header_len=14,
        is_etherII=True,
        vlan_tags=0,
        l3_proto=L3_OTHER,
        ethertype=None,
    )

    etype = type_or_len
    offset = 14
    if type_or_len <= 1500:
        view.is_etherII = False
        if len(buf) < 18:
            view.ethertype = None
            return view
        dsap = buf[14]
        ssap = buf[15]
        control = buf[16]
        if (
            dsap == 0xAA
            and ssap == 0xAA
            and control == 0x03
            and len(buf) >= 22
        ):
            oui = buf[17:20]
            snap_etype = struct.unpack(">H", buf[20:22])[0]
            if oui == b"\x00\x00\x00":
                etype = snap_etype
                view.l2_header_len = 22
                offset = 22
            else:
                view.ethertype = None
                return view
        else:
            view.ethertype = None
            return view

    while etype in (ETHERTYPE_VLAN, ETHERTYPE_QINQ):
        view.vlan_tags += 1
        if len(buf) < offset + 4:
            return view
        etype = struct.unpack(">H", buf[offset + 2 : offset + 4])[0]
        offset += 4
        view.l2_header_len = offset

    view.ethertype = etype

    if etype == ETHERTYPE_ARP:
        view.l3_proto = L3_ARP
        if len(buf) >= offset + 28:
            sha = buf[offset + 8 : offset + 14]
            spa = buf[offset + 14 : offset + 18]
            tha = buf[offset + 18 : offset + 24]
            tpa = buf[offset + 24 : offset + 28]
            view.arp_sender_mac = format_mac(sha)
            view.arp_sender_ip = format_ipv4(spa)
            view.arp_target_mac = format_mac(tha)
            view.arp_target_ip = format_ipv4(tpa)
            view.src_ip = view.arp_sender_ip
            view.dst_ip = view.arp_target_ip
        return view

    if etype == ETHERTYPE_IPV4:
        if len(buf) < offset + 20:
            return view
        ip = buf[offset : offset + 20]
        version_ihl = ip[0]
        if version_ihl >> 4 != 4:
            return view
        ihl = (version_ihl & 0x0F) * 4
        total_len = struct.unpack(">H", ip[2:4])[0]
        flags_frag = struct.unpack(">H", ip[6:8])[0]
        ttl = ip[8]
        proto = ip[9]
        view.ip_header_len = ihl
        view.ip_total_len = total_len
        view.ttl = ttl
        view.ip_df = bool(flags_frag & 0x4000)
        view.ip_mf = bool(flags_frag & 0x2000)
        view.ip_frag_offset = flags_frag & 0x1FFF
        view.src_ip = format_ipv4(ip[12:16])
        view.dst_ip = format_ipv4(ip[16:20])
        view.l3_proto = {
            IPPROTO_TCP: L3_TCP,
            IPPROTO_UDP: L3_UDP,
            IPPROTO_ICMP: L3_ICMP,
        }.get(proto, L3_OTHER)
        l4_off = offset + ihl
        if view.ip_frag_offset == 0:
            _decode_l4(view, buf, l4_off)
        else:
            view.l3_proto = L3_OTHER
        return view

    if etype == ETHERTYPE_IPV6:
        if len(buf) < offset + 40:
            return view
        ip6 = buf[offset : offset + 40]
        payload_len = struct.unpack(">H", ip6[4:6])[0]
        next_hdr = ip6[6]
        hop_limit = ip6[7]
        view.ip_header_len = 40
        view.ip_total_len = 40 + payload_len
        view.ttl = hop_limit
        view.src_ip = ":".join(f"{ip6[i] << 8 | ip6[i+1]:x}" for i in range(8, 24, 2))
        view.dst_ip = ":".join(f"{ip6[i] << 8 | ip6[i+1]:x}" for i in range(24, 40, 2))
        view.l3_proto = {
            IPPROTO_TCP: L3_TCP,
            IPPROTO_UDP: L3_UDP,
            IPPROTO_ICMPV6: L3_ICMPV6,
        }.get(next_hdr, L3_OTHER)
        _decode_l4(view, buf, offset + 40)
        return view

    return view
