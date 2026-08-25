"""Device ABM over the protected environment.

State model per node (static identity + dynamic evidence), event-driven
chronological updates, bounded in-memory history, optional incremental
disk output.

Evidence separation is structural:

  network_risk    only from accepted NetworkFinding(s)
  behavior_risk   only from accepted BehaviorFinding(s); None when
                  behavior_supported=False or unobserved (never 0)
  propagated_risk only from the deterministic propagation pass
  systemic_risk   provisional fusion = max(direct, propagated) where direct
                  = max(network_risk, behavior_risk or -inf). Missing
                  behaviour is IGNORED (not averaged as zero).

Attacker nodes carry state but are excluded from defended blast radius.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path

import networkx as nx

from config import DATASENSE_ABM_HISTORY_LIMIT, DATASENSE_SREP_PARAMS


@dataclass
class DeviceState:
    node_id: str
    role: str
    device_type: str
    ip: str
    mac: str
    is_protected_asset: bool
    is_attacker: bool
    behavior_supported: bool
    behavior_profile_type: str | None = None
    network_risk: float | None = None
    behavior_risk: float | None = None
    network_observed: bool = False
    behavior_observed: bool = False
    propagated_risk: float = 0.0
    systemic_risk: float = 0.0
    operational: bool = True
    compromised: bool = False
    last_network_update: str | None = None
    last_behavior_update: str | None = None
    last_network_window: int | None = None
    last_behavior_window: int | None = None


class DeviceABM:
    def __init__(
        self,
        inventory,
        topology: nx.DiGraph,
        history_limit: int | None = None,
        srep_params: dict | None = None,
        spill_path: Path | None = None,
    ):
        self.inventory = inventory
        self.topology = topology
        self.params = dict(srep_params or DATASENSE_SREP_PARAMS)
        self.history_limit = history_limit or DATASENSE_ABM_HISTORY_LIMIT
        self.states: dict[str, DeviceState] = {}
        for rec in inventory.records:
            profile_type = (
                inventory.behavior_profile_for(rec.device_name)
                if rec.role == "sensor"
                else None
            )
            supported = rec.role == "sensor"
            if not supported:
                profile_type = None
            self.states[rec.device_name] = DeviceState(
                node_id=rec.device_name,
                role=rec.role,
                device_type=rec.type,
                ip=rec.ip,
                mac=rec.mac,
                is_protected_asset=rec.role not in ("attacker", "cloud"),
                is_attacker=rec.role == "attacker",
                behavior_supported=supported,
                behavior_profile_type=profile_type,
            )
        self.history: deque = deque(maxlen=self.history_limit)
        self.spill_path = spill_path
        self._spill_fh = None
        self.current_window_id: int | None = None
        self.steps = 0

    # ------------------------------------------------------------- resolution
    def resolve(self, entity_id: str) -> DeviceState | None:
        return self.states.get(entity_id)

    # -------------------------------------------------------------- evidence
    def apply_network_evidence(self, finding) -> None:
        state = self.states[finding.entity_id]
        state.network_risk = float(finding.attack_probability)
        state.network_observed = True
        state.last_network_update = finding.timestamp_utc
        state.last_network_window = int(finding.window_id)
        if state.is_protected_asset and finding.attack_probability >= 0.5:
            state.compromised = True
        self.current_window_id = max(self.current_window_id or finding.window_id, finding.window_id)

    def apply_behavior_evidence(self, finding) -> None:
        state = self.states[finding.entity_id]
        if not state.behavior_supported:
            raise ValueError(
                f"behavior evidence for unsupported device {finding.entity_id}"
            )
        state.behavior_risk = float(finding.deviation_score)
        state.behavior_observed = True
        state.last_behavior_update = finding.timestamp_utc
        state.last_behavior_window = int(finding.window_id)
        self.current_window_id = max(self.current_window_id or finding.window_id, finding.window_id)

    # ----------------------------------------------------------- propagation
    def propagate(self) -> None:
        """Deterministic max-based propagation along topology edges.

        direct evidence is never overwritten; propagated stays separate;
        hop decay and a hard hop cap keep output bounded and cycle-safe."""
        w = float(self.params.get("propagation_weight", 0.5))
        decay = float(self.params.get("hop_decay", 0.5))
        max_hops = int(self.params.get("max_hops", 3))

        sources = []
        for node, st in self.states.items():
            if not st.is_protected_asset:
                continue
            direct = max(
                st.network_risk or 0.0,
                st.behavior_risk if st.behavior_risk is not None else 0.0,
            )
            if direct > 0.0:
                sources.append((node, direct))

        new_propagated: dict[str, float] = {}
        for src, risk in sources:
            visited = {src}
            frontier = [(src, risk, 0)]
            while frontier:
                node, r, hops = frontier.pop(0)
                if hops >= max_hops:
                    continue
                for neighbor in nx.all_neighbors(self.topology, node):
                    if neighbor in visited:
                        continue
                    nstate = self.states.get(neighbor)
                    if nstate is None or not nstate.is_protected_asset:
                        continue
                    pushed = r * w * (decay ** (hops + 1))
                    if pushed <= 1e-9:
                        continue
                    visited.add(neighbor)
                    if pushed > new_propagated.get(neighbor, 0.0):
                        new_propagated[neighbor] = pushed
                    frontier.append((neighbor, pushed, hops + 1))

        for node, st in self.states.items():
            st.propagated_risk = new_propagated.get(node, 0.0)
            direct = None
            candidates = [st.network_risk]
            if st.behavior_risk is not None:
                candidates.append(st.behavior_risk)
            present = [c for c in candidates if c is not None]
            direct = max(present) if present else None
            if direct is None:
                st.systemic_risk = st.propagated_risk
            else:
                st.systemic_risk = max(direct, st.propagated_risk)

    def defended_blast_radius(self) -> float:
        total = 0.0
        for st in self.states.values():
            if st.is_attacker or not st.is_protected_asset:
                continue
            total += st.systemic_risk * float(
                self.params.get("criticality", {}).get(st.role, self.params.get("default_criticality", 0.5))
            )
        return round(total, 6)

    # --------------------------------------------------------------- history
    def snapshot(self) -> dict:
        compact = {
            n: {
                "nr": s.network_risk,
                "br": s.behavior_risk,
                "pr": round(s.propagated_risk, 6),
                "sr": round(s.systemic_risk, 6),
                "comp": s.compromised,
            }
            for n, s in self.states.items()
        }
        return {
            "step": self.steps,
            "window_id": self.current_window_id,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "states": compact,
            "defended_blast_radius": self.defended_blast_radius(),
        }

    def record_step(self) -> dict:
        self.steps += 1
        snap = self.snapshot()
        self.history.append(snap)
        if self.spill_path is not None:
            if self._spill_fh is None:
                self.spill_path.parent.mkdir(parents=True, exist_ok=True)
                self._spill_fh = open(self.spill_path, "a", encoding="utf-8")
            self._spill_fh.write(json.dumps(snap) + "\n")
            self._spill_fh.flush()
        return snap

    def close(self) -> None:
        if self._spill_fh is not None:
            self._spill_fh.close()
            self._spill_fh = None

    def final_digest(self) -> dict:
        return {
            "steps": self.steps,
            "last_window_id": self.current_window_id,
            "defended_blast_radius": self.defended_blast_radius(),
            "compromised_protected": sorted(
                n for n, s in self.states.items() if s.compromised and s.is_protected_asset
            ),
            "state": {
                n: {
                    k: getattr(s, k)
                    for k in (
                        "network_risk",
                        "behavior_risk",
                        "propagated_risk",
                        "systemic_risk",
                        "behavior_supported",
                        "behavior_observed",
                        "network_observed",
                        "is_attacker",
                        "is_protected_asset",
                    )
                }
                for n, s in self.states.items()
            },
        }
