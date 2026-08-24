"""Lossless directed communication records derived from raw packets.

One record per actually observed directed (src -> dst) relationship within a
window. Edges are never inferred from Cartesian combinations of address
lists, broadcast traffic is preserved as broadcast (never expanded into
fabricated unicast edges), and no peer relationship is lost through capped
lists: every distinct observed pair becomes its own edge record.

Endpoints carry an explicit resolution status:

  resolved_mac   endpoint MAC maps to an inventory device
  resolved_ip    only the IP maps to an inventory device
  external       unresolved third-party address (kept representable)
  broadcast      L2 broadcast destination
  multicast      L3 multicast destination

Exact addresses remain graph/provenance data; they are not model features.
Aggregation is bounded-memory: one small accumulator per live
(window, src, dst) edge inside the watermark horizon, finalized incrementally.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from datasets.datasense.frame_decoder import BROADCAST_MAC, L3_ICMPV6
from datasets.datasense.network_features import LIST_METADATA_CAP
from datasets.datasense.ordering import WatermarkTracker
from datasets.datasense.devices import normalize_mac
from datasets.datasense.versions import (
    COMMUNICATION_FEATURE_SCHEMA_VERSION,
    DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
    DEFAULT_MAX_EVENT_LATENESS_SECONDS,
    EXTRACTOR_VERSION,
)
from datasets.datasense.windowing import (
    DISPOSITION_PRESTART_NEGATIVE,
    DISPOSITION_PRESTART_SNAPPED,
    WindowGrid,
    iso_utc_from_ns,
)

RESOLVED_MAC = "resolved_mac"
RESOLVED_IP = "resolved_ip"
EXTERNAL = "external"
BROADCAST = "broadcast"
MULTICAST = "multicast"

PORT_CAP = 32


class CapacityExceededError(RuntimeError):
    """Raised when live communication-edge accumulators exceed the configured
    active_window_capacity. The session fails explicitly; edges are never
    discarded, truncated or merged to fit."""

    def __init__(self, live_edges: int, capacity: int, window_id: int):
        self.live_edges = live_edges
        self.capacity = capacity
        self.window_id = window_id
        super().__init__(
            f"live communication-edge accumulators ({live_edges}) exceeded "
            f"active_window_capacity ({capacity}) while inserting an edge in "
            f"window {window_id}. Session aborted without data loss; increase "
            "the capacity or reduce max_event_lateness."
        )

COMMUNICATION_KEY_FIELDS: list[str] = [
    "scenario_id",
    "window_id",
    "window_start_utc",
    "window_end_utc",
]

COMMUNICATION_ENDPOINT_FIELDS: list[str] = [
    "src_entity_id",
    "dst_entity_id",
    "src_resolution_status",
    "dst_resolution_status",
    "src_mac",
    "dst_mac",
    "src_ip",
    "dst_ip",
]

COMMUNICATION_VOLUME_FIELDS: list[str] = [
    "packet_count",
    "captured_byte_count",
    "wire_byte_count",
    "first_timestamp_utc",
    "last_timestamp_utc",
    "protocols",
    "protocol_packet_counts",
    "src_ports",
    "dst_ports",
    "src_ports_truncated",
    "dst_ports_truncated",
    "broadcast_indicator",
    "multicast_indicator",
]

COMMUNICATION_PROVENANCE_FIELDS: list[str] = [
    "raw_source",
    "extractor_version",
    "schema_version",
]

COMMUNICATION_FIELD_TYPES: dict[str, tuple[type, bool]] = {}


def _build_communication_field_types() -> dict[str, tuple[type, bool]]:
    types: dict[str, tuple[type, bool]] = {}
    for f in (
        "scenario_id",
        "window_start_utc",
        "window_end_utc",
        "first_timestamp_utc",
        "last_timestamp_utc",
        *COMMUNICATION_ENDPOINT_FIELDS,
    ):
        types[f] = (str, True)
    types["window_id"] = (int, False)
    types["broadcast_indicator"] = (bool, False)
    types["multicast_indicator"] = (bool, False)
    types["src_ports_truncated"] = (bool, False)
    types["dst_ports_truncated"] = (bool, False)
    for f in ("packet_count", "captured_byte_count", "wire_byte_count"):
        types[f] = (int, False)
    types["protocols"] = (list, True)
    types["protocol_packet_counts"] = ("int_list", True)
    types["src_ports"] = ("int_list", True)
    types["dst_ports"] = ("int_list", True)
    for f in COMMUNICATION_PROVENANCE_FIELDS:
        types[f] = (str, False)
    return types


COMMUNICATION_FIELD_TYPES = _build_communication_field_types()


def _is_multicast_ipv4(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        first = int(ip.split(".")[0])
    except (ValueError, IndexError):
        return False
    return 224 <= first <= 239


@dataclass
class CommunicationEdgeAccumulator:
    window_id: int
    src_entity_id: str
    dst_entity_id: str
    src_resolution_status: str = EXTERNAL
    dst_resolution_status: str = EXTERNAL

    src_mac: str | None = None
    dst_mac: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None

    packet_count: int = 0
    captured_byte_count: int = 0
    wire_byte_count: int = 0
    first_ts_ns: int | None = None
    last_ts_ns: int | None = None

    protocol_counts: Counter = field(default_factory=Counter)
    src_ports: set = field(default_factory=set)
    dst_ports: set = field(default_factory=set)
    src_ports_truncated: bool = False
    dst_ports_truncated: bool = False
    broadcast_seen: bool = False
    multicast_seen: bool = False


class EndpointResolver:
    def __init__(self, inventory):
        self.inventory = inventory

    def resolve(self, mac: str | None, ip: str | None) -> tuple[str, str]:
        """Return (entity_id, resolution_status) for one packet endpoint."""
        norm = normalize_mac(mac)
        if norm == BROADCAST_MAC:
            return BROADCAST, BROADCAST
        if norm is not None:
            rec = self.inventory.by_mac.get(norm)
            if rec is not None:
                return rec.device_name, RESOLVED_MAC
        if ip:
            if _is_multicast_ipv4(ip):
                return MULTICAST, MULTICAST
            rec = self.inventory.by_ip.get(ip.strip())
            if rec is not None:
                return rec.device_name, RESOLVED_IP
        if norm is not None:
            return f"mac:{norm}", EXTERNAL
        if ip:
            return f"ip:{ip}", EXTERNAL
        return "unknown", EXTERNAL


class CommunicationWindowManager:
    """Accumulates directed edges on the shared grid with watermark-driven
    finalization identical to the other modalities."""

    def __init__(
        self,
        grid: WindowGrid,
        scenario_id: str,
        inventory,
        clock_tolerance_ns: int = DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
        max_event_lateness_ns: int = DEFAULT_MAX_EVENT_LATENESS_SECONDS * 1_000_000_000,
        active_window_capacity: int = 65_536,
    ):
        self.grid = grid
        self.scenario_id = scenario_id
        self.inventory = inventory
        self.resolver = EndpointResolver(inventory)
        self.clock_tolerance_ns = int(clock_tolerance_ns)
        self.max_event_lateness_ns = int(max_event_lateness_ns)
        self.active_window_capacity = max(1, active_window_capacity)
        self.edges: dict[tuple[int, str, str], CommunicationEdgeAccumulator] = {}
        self.tracker = WatermarkTracker(grid.window_ns, self.max_event_lateness_ns)
        self.diagnostics = {
            "packets_seen": 0,
            "packets_without_timestamp": 0,
            "edges_created": 0,
            "unresolved_endpoint_packets": 0,
            "prestart_snapped_events": 0,
            "prestart_snapped_max_displacement_ns": 0,
            "prestart_negative_events": 0,
            "late_events": 0,
            "max_observed_lateness_ns": 0,
            "capacity_peak_usage": 0,
            "capacity_exceeded_events": 0,
        }

    def add_packet(
        self, ts_ns: int | None, view, caplen: int, wirelen: int
    ) -> list[dict]:
        diag = self.diagnostics
        diag["packets_seen"] += 1
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
        self.tracker.ensure_acceptable(wid, "communication packet")
        self.tracker.observe(ts_ns, wid)
        diag["max_observed_lateness_ns"] = self.tracker.max_observed_lateness_ns

        src_entity, src_status = self.resolver.resolve(view.src_mac, view.src_ip)
        dst_entity, dst_status = self.resolver.resolve(view.dst_mac, view.dst_ip)
        if src_status == EXTERNAL and dst_status == EXTERNAL:
            diag["unresolved_endpoint_packets"] += 1

        key = (wid, src_entity, dst_entity)
        edge = self.edges.get(key)
        if edge is None:
            if len(self.edges) >= self.active_window_capacity:
                diag["capacity_exceeded_events"] = (
                    diag.get("capacity_exceeded_events", 0) + 1
                )
                raise CapacityExceededError(
                    live_edges=len(self.edges),
                    capacity=self.active_window_capacity,
                    window_id=wid,
                )
            edge = CommunicationEdgeAccumulator(
                wid,
                src_entity,
                dst_entity,
                src_resolution_status=src_status,
                dst_resolution_status=dst_status,
            )
            self.edges[key] = edge
            diag["edges_created"] += 1
            if len(self.edges) > diag["capacity_peak_usage"]:
                diag["capacity_peak_usage"] = len(self.edges)

        self._update(edge, view, caplen, wirelen, ts_ns)
        return self.finalize_due()

    def _update(
        self,
        edge: CommunicationEdgeAccumulator,
        view,
        caplen: int,
        wirelen: int,
        ts_ns: int,
    ) -> None:
        edge.packet_count += 1
        edge.captured_byte_count += caplen
        edge.wire_byte_count += wirelen
        if edge.first_ts_ns is None or ts_ns < edge.first_ts_ns:
            edge.first_ts_ns = ts_ns
        if edge.last_ts_ns is None or ts_ns > edge.last_ts_ns:
            edge.last_ts_ns = ts_ns

        if view.src_mac:
            edge.src_mac = view.src_mac
        if view.dst_mac:
            edge.dst_mac = view.dst_mac
        if view.src_ip:
            edge.src_ip = view.src_ip
        if view.dst_ip:
            edge.dst_ip = view.dst_ip

        proto = view.l3_proto
        if proto == L3_ICMPV6:
            proto = "icmpv6"
        edge.protocol_counts[proto] += 1

        if view.sport is not None:
            if len(edge.src_ports) < PORT_CAP or view.sport in edge.src_ports:
                edge.src_ports.add(int(view.sport))
            else:
                edge.src_ports_truncated = True
        if view.dport is not None:
            if len(edge.dst_ports) < PORT_CAP or view.dport in edge.dst_ports:
                edge.dst_ports.add(int(view.dport))
            else:
                edge.dst_ports_truncated = True

        if view.dst_mac == BROADCAST_MAC:
            edge.broadcast_seen = True
        if _is_multicast_ipv4(view.dst_ip):
            edge.multicast_seen = True

    def finalize_due(self) -> list[dict]:
        due = self.tracker.due_windows()
        if due is None:
            return []
        lo, hi = due
        keys = [k for k in self.edges if lo <= k[0] <= hi]
        return [self.finalize(self.edges.pop(k)) for k in sorted(keys)]

    def finish(self) -> list[dict]:
        rows = [self.finalize(self.edges[k]) for k in sorted(self.edges)]
        self.edges.clear()
        return rows

    def finalize(self, edge: CommunicationEdgeAccumulator) -> dict:
        start_ns, end_ns = self.grid.window_bounds(edge.window_id)
        protocols = sorted(edge.protocol_counts)
        row = {
            "scenario_id": self.scenario_id,
            "window_id": edge.window_id,
            "window_start_utc": iso_utc_from_ns(start_ns),
            "window_end_utc": iso_utc_from_ns(end_ns),
            "src_entity_id": edge.src_entity_id,
            "dst_entity_id": edge.dst_entity_id,
            "src_resolution_status": edge.src_resolution_status,
            "dst_resolution_status": edge.dst_resolution_status,
            "src_mac": edge.src_mac,
            "dst_mac": edge.dst_mac,
            "src_ip": edge.src_ip,
            "dst_ip": edge.dst_ip,
            "packet_count": edge.packet_count,
            "captured_byte_count": edge.captured_byte_count,
            "wire_byte_count": edge.wire_byte_count,
            "first_timestamp_utc": iso_utc_from_ns(edge.first_ts_ns),
            "last_timestamp_utc": iso_utc_from_ns(edge.last_ts_ns),
            "protocols": protocols,
            "protocol_packet_counts": [edge.protocol_counts[p] for p in protocols],
            "src_ports": sorted(edge.src_ports),
            "dst_ports": sorted(edge.dst_ports),
            "src_ports_truncated": edge.src_ports_truncated,
            "dst_ports_truncated": edge.dst_ports_truncated,
            "broadcast_indicator": edge.broadcast_seen,
            "multicast_indicator": edge.multicast_seen,
            "raw_source": "pcap",
            "extractor_version": EXTRACTOR_VERSION,
            "schema_version": COMMUNICATION_FEATURE_SCHEMA_VERSION,
        }
        return row
