"""Initial integrated SREP over the actual Device Risk Graph.

Reuses the srep package; the old workflow stubs remain untouched.

Mode honesty: SREP runs in DEVICE_ONLY mode unless a genuine Agent Trust
Graph is supplied through ``agent_trust_graph`` (a NetworkX graph carrying
per-edge/per-node trust attributes). No such graph exists in this task and
none is fabricated, so reports explicitly state DEVICE_ONLY — which must not
be read as full dual-graph systemic risk.

Propagation weights, hop decay, hop cap, criticality and fusion policy are
SIMULATION-DEFINED PARAMETERS loaded from configuration; DataSense does not
measure propagation coefficients.
"""

from __future__ import annotations

import time

MODE_DEVICE_ONLY = "DEVICE_ONLY"
MODE_DUAL_GRAPH = "DUAL_GRAPH"


class TrustGraphUnsupportedError(NotImplementedError):
    """Raised when an agent-trust graph is supplied although genuine trust
    validation/fusion is not implemented. We refuse rather than silently
    claiming DUAL_GRAPH semantics."""


class SREPEngine:
    def __init__(self, abm, comm_graph=None, params: dict | None = None):
        self.abm = abm
        # Accept either a raw NetworkX graph or the CommunicationGraph wrapper.
        self.comm_graph = getattr(comm_graph, "g", comm_graph)
        self.params = dict(params or abm.params)

    def run(self, agent_trust_graph=None) -> dict:
        if agent_trust_graph is not None:
            raise TrustGraphUnsupportedError(
                "An agent-trust graph was supplied, but genuine trust "
                "validation and fusion are not implemented; refusing to "
                "report DUAL_GRAPH without using trust information. Re-run "
                "without the argument for DEVICE_ONLY analysis."
            )
        mode = MODE_DEVICE_ONLY
        mode_note = (
            "No Agent Trust Graph is implemented or supplied; report is "
            "DEVICE_ONLY and must not be interpreted as full dual-graph "
            "systemic risk."
        )

        nodes = []
        for name, st in self.abm.states.items():
            crit = float(
                self.params.get("criticality", {}).get(
                    st.role, self.params.get("default_criticality", 0.5)
                )
            )
            contribution = (
                round(st.systemic_risk * crit, 6) if st.is_protected_asset else 0.0
            )
            nodes.append(
                {
                    "node_id": name,
                    "role": st.role,
                    "is_protected_asset": st.is_protected_asset,
                    "is_attacker": st.is_attacker,
                    "network_risk": st.network_risk,
                    "behavior_risk": st.behavior_risk,
                    "propagated_risk": round(st.propagated_risk, 6),
                    "systemic_risk": round(st.systemic_risk, 6),
                    "criticality": crit,
                    "defended_contribution": contribution,
                    "compromised": st.compromised,
                }
            )

        defended = [n for n in nodes if n["is_protected_asset"]]
        defended.sort(key=lambda n: (-n["systemic_risk"], n["node_id"]))
        top_nodes = defended[:10]

        comm_summary = {
            "observed_edges": self.comm_graph.number_of_edges() if self.comm_graph is not None else 0,
            "observed_nodes": self.comm_graph.number_of_nodes() if self.comm_graph is not None else 0,
        }

        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "mode": mode,
            "mode_note": mode_note,
            "simulation_defined_parameters": {
                k: v for k, v in self.params.items()
            },
            "parameter_disclaimer": (
                "SIMULATION-DEFINED PARAMETERS: DataSense does not measure "
                "propagation coefficients; weights/decay/criticality are "
                "project choices kept in configuration."
            ),
            "defended_blast_radius": self.abm.defended_blast_radius(),
            "compromised_protected_assets": sorted(
                n["node_id"] for n in nodes if n["compromised"] and n["is_protected_asset"]
            ),
            "top_risky_protected_nodes": top_nodes,
            "communication_summary": comm_summary,
            "device_risk_nodes": nodes,
            "last_window_id": self.abm.current_window_id,
            "steps_replayed": self.abm.steps,
        }
