"""Dynamic communication graph (G_communication) — aggregate, bounded form.

Built ONLY from raw-derived communication records. One aggregate edge per
observed directed pair carries:

  packet_count_total / captured_byte_total   running sums
  first/last_window_id + first/last timestamp UTC
  protocols_ever (capped sorted list)
  broadcast/multicast ever-seen flags

Per-window edge history is NOT kept in memory; when ``history_spill`` is
provided every applied record is streamed to disk as JSONL instead.

G_commulation is separate from G_topology: observed traffic is evidence,
never structural dependency and never risk propagation by itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

EXTERNAL_PREFIXES = ("mac:", "ip:")
PROTOCOL_CAP = 32


class CommunicationGraph:
    def __init__(self, inventory, history_spill: Path | None = None):
        self.inventory = inventory
        self.g = nx.DiGraph()
        self.history_spill = Path(history_spill) if history_spill else None
        self._fh = None
        self.records_applied = 0
        # Bounded current-window delta state (per directed pair for active window)
        self.current_window_id: int | None = None
        self._window_deltas: dict[tuple[str, str], dict] = {}

    # ------------------------------------------------------------- nodes
    def _ensure_node(self, entity_id: str) -> None:
        if entity_id in self.g:
            return
        rec = self.inventory.by_name.get(entity_id)
        if rec is not None:
            self.g.add_node(
                entity_id,
                is_protected_asset=rec.role not in ("attacker", "cloud"),
                is_attacker=rec.role == "attacker",
                role=rec.role,
            )
        elif entity_id in ("broadcast", "multicast") or entity_id.startswith(
            EXTERNAL_PREFIXES
        ):
            kind = entity_id if entity_id in ("broadcast", "multicast") else "external"
            self.g.add_node(
                entity_id, is_protected_asset=False, is_attacker=False, role=kind
            )
        else:
            self.g.add_node(
                entity_id, is_protected_asset=False, is_attacker=False, role="unknown"
            )

    # -------------------------------------------------------------- apply
    def apply(self, record: dict) -> None:
        src, dst = record["src_entity_id"], record["dst_entity_id"]
        wid = int(record["window_id"])
        # Bounded per-window delta handling: reset when window advances
        if self.current_window_id != wid:
            self.current_window_id = wid
            self._window_deltas.clear()
        self._ensure_node(src)
        self._ensure_node(dst)

        if not self.g.has_edge(src, dst):
            self.g.add_edge(
                src,
                dst,
                packet_count_total=0,
                captured_byte_total=0,
                first_window_id=wid,
                last_window_id=wid,
                first_timestamp_utc=record.get("window_start_utc"),
                last_timestamp_utc=record.get("window_start_utc"),
                protocols_ever=[],
                broadcast_ever=False,
                multicast_ever=False,
            )
        data = self.g.edges[src, dst]
        data["packet_count_total"] += int(record["packet_count"])
        data["captured_byte_total"] += int(record.get("captured_byte_count", 0))
        if wid < data["first_window_id"]:
            data["first_window_id"] = wid
            data["first_timestamp_utc"] = record.get("window_start_utc")
        if wid > data["last_window_id"]:
            data["last_window_id"] = wid
            data["last_timestamp_utc"] = record.get("window_start_utc")

        for proto in record.get("protocols") or []:
            if proto not in data["protocols_ever"]:
                if len(data["protocols_ever"]) < PROTOCOL_CAP:
                    data["protocols_ever"].append(proto)
                    data["protocols_ever"].sort()
        if record.get("broadcast_indicator"):
            data["broadcast_ever"] = True
        if record.get("multicast_indicator"):
            data["multicast_ever"] = True

        # Current-window delta aggregation (bounded: one entry per active pair)
        key = (src, dst)
        delta = self._window_deltas.get(key)
        if delta is None:
            delta = {
                "packet_count_delta": 0,
                "captured_byte_delta": 0,
                "protocols_in_window": set(),
            }
            self._window_deltas[key] = delta
        delta["packet_count_delta"] += int(record["packet_count"])
        delta["captured_byte_delta"] += int(record.get("captured_byte_count", 0))
        for proto in record.get("protocols") or []:
            delta["protocols_in_window"].add(proto)

        self.records_applied += 1
        if self.history_spill is not None:
            if self._fh is None:
                self.history_spill.parent.mkdir(parents=True, exist_ok=True)
                self._fh = open(self.history_spill, "a", encoding="utf-8")
            self._fh.write(json.dumps(record, default=str) + "\n")

    def apply_many(self, records) -> int:
        n = 0
        for r in records:
            self.apply(r)
            n += 1
        return n

    def get_window_delta(self, src: str, dst: str) -> dict:
        """Return current-window delta for edge, or zeroed if no traffic this window."""
        d = self._window_deltas.get((src, dst))
        if d is None:
            return {
                "packet_count_delta": 0,
                "captured_byte_delta": 0,
                "protocols_in_window": [],
            }
        return {
            "packet_count_delta": d["packet_count_delta"],
            "captured_byte_delta": d["captured_byte_delta"],
            "protocols_in_window": sorted(d["protocols_in_window"]),
        }

    def begin_window(self, window_id: int) -> None:
        """Set current window and clear deltas if window advanced (bounded)."""
        if self.current_window_id != window_id:
            self.current_window_id = window_id
            self._window_deltas.clear()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def build_comm_graph(inventory=None, history_spill: Path | None = None) -> CommunicationGraph:
    return CommunicationGraph(inventory=inventory, history_spill=history_spill)


def observed_pairs(graph: CommunicationGraph):
    return list(graph.g.edges())
