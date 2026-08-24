"""Per-(device, window) network feature accumulation from raw packets.

One bounded accumulator is maintained per (device, window); packets are
processed one at a time and discarded after header decode, so memory stays
O(active devices x active windows) regardless of capture size.

Feature families (numeric/statistical only):

  packet counts, direction counts, inter-packet timing statistics,
  unique peer/port/protocol diversity, TCP flag counts, fragmentation,
  packet/IP/header/payload size statistics, TTL statistics,
  TCP window statistics and optional MSS observation.

Exact identities (IPs, MACs), scenario identity, targets and attacker
presence are retained separately as graph/provenance metadata and never
enter NETWORK_MODEL_FEATURES.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from datasets.datasense.frame_decoder import (
    BROADCAST_MAC,
    L3_ARP,
    L3_ICMP,
    L3_ICMPV6,
    L3_TCP,
    L3_UDP,
    FrameView,
)
from datasets.datasense.ordering import WatermarkTracker
from datasets.datasense.versions import (
    DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
    DEFAULT_MAX_EVENT_LATENESS_SECONDS,
)
from datasets.datasense.windowing import (
    DISPOSITION_PRESTART_NEGATIVE,
    DISPOSITION_PRESTART_SNAPPED,
    WindowGrid,
    iso_utc_from_ns,
)

NETWORK_FEATURE_SCHEMA_VERSION = "network_feature_schema_v1"

NETWORK_MODEL_FEATURES: list[str] = [
    "packets_all_count",
    "packets_src_count",
    "packets_dst_count",
    "time_delta_avg",
    "time_delta_max",
    "time_delta_min",
    "time_delta_std",
    "unique_ips_all_count",
    "unique_ips_src_count",
    "unique_ips_dst_count",
    "unique_peer_count",
    "ports_all_count",
    "ports_src_count",
    "ports_dst_count",
    "proto_tcp_count",
    "proto_udp_count",
    "proto_icmp_count",
    "proto_arp_count",
    "proto_other_count",
    "protocol_diversity",
    "tcp_syn_count",
    "tcp_ack_count",
    "tcp_fin_count",
    "tcp_rst_count",
    "tcp_psh_count",
    "tcp_urg_count",
    "fragmented_packet_count",
    "packet_size_avg",
    "packet_size_max",
    "packet_size_min",
    "packet_size_std",
    "wire_size_avg",
    "wire_size_max",
    "wire_size_min",
    "wire_size_std",
    "ip_length_avg",
    "ip_length_max",
    "ip_length_min",
    "ip_length_std",
    "header_length_avg",
    "header_length_max",
    "header_length_min",
    "header_length_std",
    "payload_length_avg",
    "payload_length_max",
    "payload_length_min",
    "payload_length_std",
    "ttl_avg",
    "ttl_max",
    "ttl_min",
    "ttl_std",
    "tcp_window_avg",
    "tcp_window_max",
    "tcp_window_min",
    "tcp_window_std",
    "mss_observed_min",
    "mss_observed_max",
]

NETWORK_GRAPH_METADATA_FIELDS: list[str] = [
    "observed_ips_all",
    "observed_ips_src",
    "observed_ips_dst",
    "observed_macs_all",
    "observed_ports_all",
    "observed_protocols_all",
    "attacker_contact_observed",
    "broadcast_mac_observed",
    "multicast_ip_observed",
]

KEY_FIELDS: list[str] = [
    "scenario_id",
    "device_id",
    "window_id",
    "window_start_utc",
    "window_end_utc",
]

MASK_FIELDS: list[str] = ["network_observed", "behavior_observed", "behavior_supported"]

LIST_METADATA_CAP = 64


class OnlineStats:
    """Welford running statistics (population std, numpy-style)."""

    __slots__ = ("n", "mean", "m2", "mn", "mx")

    def __init__(self) -> None:
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.mn: float | None = None
        self.mx: float | None = None

    def add(self, value: float) -> None:
        self.n += 1
        v = float(value)
        delta = v - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (v - self.mean)
        if self.mn is None or v < self.mn:
            self.mn = v
        if self.mx is None or v > self.mx:
            self.mx = v

    def as_tuple(self) -> tuple[float | None, float | None, float | None, float | None]:
        if self.n == 0:
            return None, None, None, None
        avg = self.mean
        mn = self.mn
        mx = self.mx
        if self.n >= 2:
            std = math.sqrt(self.m2 / (self.n - 1))
        else:
            std = 0.0
        return avg, mx, mn, std


@dataclass
class DeviceWindowAccumulator:
    device_name: str
    window_id: int

    packets_src: int = 0
    packets_dst: int = 0
    packets_involving: int = 0
    last_ts_ns: int | None = None
    time_deltas: OnlineStats = field(default_factory=OnlineStats)

    ips_src: set[str] = field(default_factory=set)
    ips_dst: set[str] = field(default_factory=set)
    peer_macs: set[str] = field(default_factory=set)
    ports_src: set[int] = field(default_factory=set)
    ports_dst: set[int] = field(default_factory=set)

    proto_counts: Counter = field(default_factory=Counter)
    tcp_flags: Counter = field(default_factory=Counter)
    fragmented_packets: int = 0

    packet_size: OnlineStats = field(default_factory=OnlineStats)
    wire_size: OnlineStats = field(default_factory=OnlineStats)
    ip_length: OnlineStats = field(default_factory=OnlineStats)
    header_length: OnlineStats = field(default_factory=OnlineStats)
    payload_length: OnlineStats = field(default_factory=OnlineStats)
    ttl_stats: OnlineStats = field(default_factory=OnlineStats)
    tcp_window_stats: OnlineStats = field(default_factory=OnlineStats)

    mss_values: set[int] = field(default_factory=set)

    observed_ips_all: set[str] = field(default_factory=set)
    observed_ips_src: set[str] = field(default_factory=set)
    observed_ips_dst: set[str] = field(default_factory=set)
    observed_macs_all: set[str] = field(default_factory=set)
    observed_ports_all: set[str] = field(default_factory=set)
    observed_protocols_all: set[str] = field(default_factory=set)
    attacker_contact: bool = False
    broadcast_seen: bool = False
    multicast_seen: bool = False


def _capped(values, cap: int = LIST_METADATA_CAP) -> list[str]:
    ordered = sorted(values)[:cap]
    return [str(v) for v in ordered]


class NetworkWindowManager:
    """Routes decoded packets into per-(device, window) accumulators on a
    shared WindowGrid and finalizes them into flat feature records.

    Finalization is watermark-driven (see ordering.WatermarkTracker):
    ``add_packet`` returns the rows of any windows that became final, so a
    valid packet can never be silently dropped after its window closed —
    that situation is an explicit hard failure instead.
    """

    def __init__(
        self,
        grid: WindowGrid,
        scenario_id: str,
        inventory,
        attacker_names: frozenset[str],
        clock_tolerance_ns: int = DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
        max_event_lateness_ns: int = DEFAULT_MAX_EVENT_LATENESS_SECONDS * 1_000_000_000,
        active_window_capacity: int = 65_536,
    ):
        self.grid = grid
        self.scenario_id = scenario_id
        self.inventory = inventory
        self.attacker_names = attacker_names
        self.clock_tolerance_ns = int(clock_tolerance_ns)
        self.max_event_lateness_ns = int(max_event_lateness_ns)
        self.active_window_capacity = max(1, active_window_capacity)
        self.windows: dict[tuple[int, str], DeviceWindowAccumulator] = {}
        self.tracker = WatermarkTracker(grid.window_ns, self.max_event_lateness_ns)
        self.diagnostics = {
            "packets_total": 0,
            "packets_without_timestamp": 0,
            "prestart_snapped_events": 0,
            "prestart_snapped_max_displacement_ns": 0,
            "prestart_negative_events": 0,
            "late_events": 0,
            "max_observed_lateness_ns": 0,
            "capacity_peak_usage": 0,
            "unresolved_endpoint_packets": 0,
            "undecodable_frames": 0,
        }

    def add_packet(
        self, ts_ns: int | None, view: FrameView, caplen: int, wirelen: int
    ) -> list[dict]:
        diag = self.diagnostics
        diag["packets_total"] += 1
        if ts_ns is None:
            diag["packets_without_timestamp"] += 1
            return []
        wid, disposition = self.grid.assign(ts_ns, self.clock_tolerance_ns)
        if disposition == DISPOSITION_PRESTART_SNAPPED:
            diag["prestart_snapped_events"] += 1
            displacement = self.grid.scenario_start_ns - ts_ns
            if displacement > diag["prestart_snapped_max_displacement_ns"]:
                diag["prestart_snapped_max_displacement_ns"] = displacement
        elif disposition == DISPOSITION_PRESTART_NEGATIVE:
            diag["prestart_negative_events"] += 1
        if (
            self.tracker.max_wid_seen is not None
            and wid < self.tracker.max_wid_seen
        ):
            diag["late_events"] += 1
        self.tracker.ensure_acceptable(wid, "network packet")
        self.tracker.observe(ts_ns, wid)
        diag["max_observed_lateness_ns"] = self.tracker.max_observed_lateness_ns

        src_dev = self._resolve(mac=view.src_mac)
        dst_dev = self._resolve(mac=view.dst_mac)
        if src_dev is None and dst_dev is None:
            src_dev = self._resolve(ip=view.src_ip)
            dst_dev = self._resolve(ip=view.dst_ip)
        participants = []
        if src_dev is None and dst_dev is None:
            diag["unresolved_endpoint_packets"] += 1
            return []
        if src_dev is not None and dst_dev is not None:
            if src_dev.device_name == dst_dev.device_name:
                participants.append((dst_dev, True, True))
            else:
                participants.append((src_dev, True, False))
                participants.append((dst_dev, False, True))
        elif src_dev is not None:
            participants.append((src_dev, True, False))
        else:
            participants.append((dst_dev, False, True))

        for dev, is_src, is_dst in participants:
            key = (wid, dev.device_name)
            acc = self.windows.get(key)
            if acc is None:
                acc = DeviceWindowAccumulator(dev.device_name, wid)
                self.windows[key] = acc
            self._update(acc, wid, dev, is_src, is_dst, view, caplen, wirelen, ts_ns)

        if len(self.windows) > diag["capacity_peak_usage"]:
            diag["capacity_peak_usage"] = len(self.windows)

        return self.finalize_due()

    def finalize_due(self) -> list[dict]:
        due = self.tracker.due_windows()
        if due is None:
            return []
        lo, hi = due
        keys = [k for k in self.windows if lo <= k[0] <= hi]
        return [self.finalize(self.windows.pop(k)) for k in sorted(keys)]

    def _resolve(self, mac: str | None = None, ip: str | None = None):
        return self.inventory.resolve(mac=mac, ip=ip)

    def _update(
        self,
        acc: DeviceWindowAccumulator,
        wid: int,
        device_rec,
        as_src: bool,
        as_dst: bool,
        view: FrameView,
        caplen: int,
        wirelen: int,
        ts_ns: int,
    ) -> None:
        inv = self.inventory
        if as_src:
            acc.packets_src += 1
        if as_dst:
            acc.packets_dst += 1
        acc.packets_involving += 1

        if acc.last_ts_ns is not None:
            acc.time_deltas.add((ts_ns - acc.last_ts_ns) / 1e9)
        acc.last_ts_ns = ts_ns

        for endpoint_ip in filter(None, (view.src_ip, view.dst_ip)):
            acc.observed_ips_all.add(endpoint_ip)
        for endpoint_mac in filter(None, (view.src_mac, view.dst_mac)):
            acc.observed_macs_all.add(endpoint_mac)
        if view.dst_mac == BROADCAST_MAC:
            acc.broadcast_seen = True
            acc.observed_macs_all.add(view.dst_mac)
        if view.dst_ip and view.dst_ip.endswith(".255"):
            acc.multicast_seen = True

        if as_src:
            acc.peer_macs.add(view.dst_mac)
        if as_dst:
            acc.peer_macs.add(view.src_mac)

        if view.src_ip:
            acc.ips_src.add(view.src_ip)
            acc.observed_ips_src.add(view.src_ip)
        if view.dst_ip:
            acc.ips_dst.add(view.dst_ip)
            acc.observed_ips_dst.add(view.dst_ip)

        if as_src and view.sport is not None:
            acc.ports_src.add(int(view.sport))
            acc.observed_ports_all.add(str(view.sport))
        if as_dst and view.dport is not None:
            acc.ports_dst.add(int(view.dport))
            acc.observed_ports_all.add(str(view.dport))

        acc.proto_counts[view.l3_proto] += 1
        acc.observed_protocols_all.add(view.l3_proto)

        if view.l3_proto == L3_TCP and view.tcp_flags is not None:
            flags = view.tcp_flags
            if flags & 0x02:
                acc.tcp_flags["syn"] += 1
            if flags & 0x10:
                acc.tcp_flags["ack"] += 1
            if flags & 0x01:
                acc.tcp_flags["fin"] += 1
            if flags & 0x04:
                acc.tcp_flags["rst"] += 1
            if flags & 0x08:
                acc.tcp_flags["psh"] += 1
            if flags & 0x20:
                acc.tcp_flags["urg"] += 1

        if view.ip_mf or view.ip_frag_offset > 0:
            acc.fragmented_packets += 1

        acc.packet_size.add(caplen)
        acc.wire_size.add(wirelen)
        if view.ip_total_len is not None:
            acc.ip_length.add(view.ip_total_len)
        acc.header_length.add(view.header_length)
        acc.payload_length.add(view.payload_length)
        if view.ttl is not None:
            acc.ttl_stats.add(view.ttl)
        if view.tcp_window is not None:
            acc.tcp_window_stats.add(view.tcp_window)
        if view.mss is not None:
            acc.mss_values.add(int(view.mss))

        peers = {view.src_ip, view.dst_ip} - {None}
        for name in self.attacker_names:
            rec = inv.by_name.get(name)
            if rec is None:
                continue
            if rec.ip in peers or rec.mac == view.src_mac or rec.mac == view.dst_mac:
                acc.attacker_contact = True

    def finish(self) -> list[dict]:
        rows = [self.finalize(self.windows[k]) for k in sorted(self.windows)]
        self.windows.clear()
        return rows

    def finalize(self, acc: DeviceWindowAccumulator) -> dict:
        start_ns, end_ns = self.grid.window_bounds(acc.window_id)
        row = {
            "scenario_id": self.scenario_id,
            "device_id": acc.device_name,
            "window_id": acc.window_id,
            "window_start_utc": iso_utc_from_ns(start_ns),
            "window_end_utc": iso_utc_from_ns(end_ns),
            "network_observed": True,
            "behavior_observed": False,
            "behavior_supported": self.inventory.behavior_profile_for(acc.device_name)
            != "unsupported",
        }
        td = acc.time_deltas.as_tuple()
        ps = acc.packet_size.as_tuple()
        ws = acc.wire_size.as_tuple()
        il = acc.ip_length.as_tuple()
        hl = acc.header_length.as_tuple()
        pl = acc.payload_length.as_tuple()
        tl = acc.ttl_stats.as_tuple()
        tw = acc.tcp_window_stats.as_tuple()

        proto_diversity = len(acc.proto_counts)
        features = {
            "packets_all_count": acc.packets_involving,
            "packets_src_count": acc.packets_src,
            "packets_dst_count": acc.packets_dst,
            "time_delta_avg": td[0],
            "time_delta_max": td[1],
            "time_delta_min": td[2],
            "time_delta_std": td[3],
            "unique_ips_all_count": len(acc.ips_src | acc.ips_dst),
            "unique_ips_src_count": len(acc.ips_src),
            "unique_ips_dst_count": len(acc.ips_dst),
            "unique_peer_count": len(acc.peer_macs),
            "ports_all_count": len(acc.ports_src | acc.ports_dst),
            "ports_src_count": len(acc.ports_src),
            "ports_dst_count": len(acc.ports_dst),
            "proto_tcp_count": acc.proto_counts.get(L3_TCP, 0),
            "proto_udp_count": acc.proto_counts.get(L3_UDP, 0),
            "proto_icmp_count": acc.proto_counts.get(L3_ICMP, 0) + acc.proto_counts.get(L3_ICMPV6, 0),
            "proto_arp_count": acc.proto_counts.get(L3_ARP, 0),
            "proto_other_count": acc.proto_counts.get("other", 0),
            "protocol_diversity": proto_diversity,
            "tcp_syn_count": acc.tcp_flags.get("syn", 0),
            "tcp_ack_count": acc.tcp_flags.get("ack", 0),
            "tcp_fin_count": acc.tcp_flags.get("fin", 0),
            "tcp_rst_count": acc.tcp_flags.get("rst", 0),
            "tcp_psh_count": acc.tcp_flags.get("psh", 0),
            "tcp_urg_count": acc.tcp_flags.get("urg", 0),
            "fragmented_packet_count": acc.fragmented_packets,
            "packet_size_avg": ps[0],
            "packet_size_max": ps[1],
            "packet_size_min": ps[2],
            "packet_size_std": ps[3],
            "wire_size_avg": ws[0],
            "wire_size_max": ws[1],
            "wire_size_min": ws[2],
            "wire_size_std": ws[3],
            "ip_length_avg": il[0],
            "ip_length_max": il[1],
            "ip_length_min": il[2],
            "ip_length_std": il[3],
            "header_length_avg": hl[0],
            "header_length_max": hl[1],
            "header_length_min": hl[2],
            "header_length_std": hl[3],
            "payload_length_avg": pl[0],
            "payload_length_max": pl[1],
            "payload_length_min": pl[2],
            "payload_length_std": pl[3],
            "ttl_avg": tl[0],
            "ttl_max": tl[1],
            "ttl_min": tl[2],
            "ttl_std": tl[3],
            "tcp_window_avg": tw[0],
            "tcp_window_max": tw[1],
            "tcp_window_min": tw[2],
            "tcp_window_std": tw[3],
            "mss_observed_min": min(acc.mss_values) if acc.mss_values else None,
            "mss_observed_max": max(acc.mss_values) if acc.mss_values else None,
        }
        graph_meta = {
            "observed_ips_all": _capped(acc.observed_ips_all),
            "observed_ips_src": _capped(acc.observed_ips_src),
            "observed_ips_dst": _capped(acc.observed_ips_dst),
            "observed_macs_all": _capped(acc.observed_macs_all),
            "observed_ports_all": _capped(acc.observed_ports_all),
            "observed_protocols_all": _capped(acc.observed_protocols_all),
            "attacker_contact_observed": acc.attacker_contact,
            "broadcast_mac_observed": acc.broadcast_seen,
            "multicast_ip_observed": acc.multicast_seen,
        }
        row.update(features)
        row.update(graph_meta)
        return row


def empty_network_row(scenario_id: str, device_name: str, window_id: int, grid: WindowGrid) -> dict:
    """Dense-fill row for a (device, window) with no evidence at all.

    Feature values are null (never zero) so that 'no evidence' is explicitly
    distinguishable from 'observed and quiet'.
    """
    start_ns, end_ns = grid.window_bounds(window_id)
    row = {
        "scenario_id": scenario_id,
        "device_id": device_name,
        "window_id": window_id,
        "window_start_utc": iso_utc_from_ns(start_ns),
        "window_end_utc": iso_utc_from_ns(end_ns),
        "network_observed": False,
        "behavior_observed": False,
        "behavior_supported": False,
    }
    for name in NETWORK_MODEL_FEATURES:
        row[name] = None
    for name in NETWORK_GRAPH_METADATA_FIELDS:
        row[name] = [] if name.startswith("observed_") else False
    return row
