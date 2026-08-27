"""Narrow adaptation layer around the verified Stage-2 scientific core.

Builds a fully independent scientific runtime (fresh model instances, ABM,
graphs) for one replay, converts its outputs into Stage-3A contracts, and
exposes snapshot builders. No scientific logic lives here.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.finding_gateway import FindingGateway  # noqa: E402
from datasets.datasense.devices import DeviceInventory  # noqa: E402
from datasets.datasense.extraction import (  # noqa: E402
    iter_behavior_rows,
    iter_pcap_feature_rows,
)
from datasets.datasense.feature_store import FeatureStoreReader  # noqa: E402
from backend.app.config import (  # noqa: E402
    BEHAVIOR_MODEL_PATH,
    CLOCK_TOLERANCE_MS_DEFAULT,
    DEVICES_CSV,
    FEATURE_STORE_ROOT,
    MAX_LATENESS_SECONDS_DEFAULT,
    NETWORK_MODEL_PATH,
    RAW_ROOT,
    READ_CHUNK_BYTES_DEFAULT,
    ACTIVE_WINDOW_CAPACITY_DEFAULT,
)
from pipeline.behavior_profiler import BehaviorProfiler  # noqa: E402
from pipeline.network_detector import NetworkDetector  # noqa: E402
from simulation.abm import DeviceABM  # noqa: E402
from simulation.communication_graph import build_comm_graph  # noqa: E402
from simulation.replay import ReplayControl, ReplayRunner  # noqa: E402
from simulation.topology import build_topology  # noqa: E402


@dataclass
class ScientificRuntime:
    """One mutable scientific runtime owned by exactly one replay run."""

    runner: ReplayRunner
    control: ReplayControl
    abm: DeviceABM
    comm_graph: object
    inventory: DeviceInventory
    # Exposed so integration layers (Stage-4B Blackboard) can observe the
    # authoritative validation boundary without touching scientific logic.
    gateway: FindingGateway | None = None

    def close(self) -> None:
        try:
            self.runner.cleanup()
        finally:
            self.abm.close()
            self.comm_graph.close()


def load_models() -> tuple[NetworkDetector, BehaviorProfiler]:
    """Fresh instances from saved artifacts (never shared across runs)."""
    detector = NetworkDetector.load(NETWORK_MODEL_PATH)
    profiler = BehaviorProfiler.load(BEHAVIOR_MODEL_PATH)
    return detector, profiler


def build_runtime(
    *,
    replay_id: str,
    session_trace: str,
    scenario_id: str,
    source_mode: str,
    pacing_speed: str = "max",
    sleeper=None,
    start_paused: bool = False,
    finding_observers: tuple = (),
) -> ScientificRuntime:
    inventory = DeviceInventory.load(DEVICES_CSV)
    detector, profiler = load_models()
    abm = DeviceABM(inventory, build_topology(inventory))
    gateway = FindingGateway(abm)
    # Stage-4B: observers receive ACCEPTED findings only (post-validation,
    # post-ABM-apply). Rejected findings never reach an observer, and the
    # existing ABM path is untouched — no double processing is possible.
    for observer in finding_observers:
        gateway.subscribe(observer)
    comm = build_comm_graph(inventory=inventory)

    def store_streams():
        reader = FeatureStoreReader(FEATURE_STORE_ROOT)
        return (
            reader.iter_network_records(scenario_id),
            reader.iter_behavior_records(scenario_id),
            reader.iter_communication_records(scenario_id),
        )

    def direct_streams():
        collect = {}
        catalog_mod = _catalog_module()
        records, _diag = catalog_mod.build_catalog(RAW_ROOT, ATTACKS_CSV_PATH())
        session = next(r for r in records if r.scenario_id == scenario_id)
        fused = iter_pcap_feature_rows(
            session,
            inventory,
            window_seconds=5.0,
            clock_tolerance_ns=int(CLOCK_TOLERANCE_MS_DEFAULT * 1e6),
            max_event_lateness_ns=int(MAX_LATENESS_SECONDS_DEFAULT * 1e9),
            active_window_capacity=ACTIVE_WINDOW_CAPACITY_DEFAULT,
            read_chunk_bytes=READ_CHUNK_BYTES_DEFAULT,
            collect=collect,
        )
        behavior = iter_behavior_rows(
            session,
            inventory,
            window_seconds=5.0,
            clock_tolerance_ns=int(CLOCK_TOLERANCE_MS_DEFAULT * 1e6),
            max_event_lateness_ns=int(MAX_LATENESS_SECONDS_DEFAULT * 1e9),
            active_window_capacity=ACTIVE_WINDOW_CAPACITY_DEFAULT,
        )
        # Use single-pass fused_records path: fused contains interleaved
        # ("network", row) / ("communication", row) tagged rows. The runner
        # dispatches them in one pass. Splitting into two generators over the
        # same iterator would exhaust the communication stream.
        return fused, behavior

    def ATTACKS_CSV_PATH():
        from backend.app.config import ATTACKS_CSV

        return ATTACKS_CSV

    if source_mode == "feature_store":
        net_s, beh_s, comm_s = store_streams()
        runner = ReplayRunner(
            network_records=net_s,
            behavior_records=beh_s,
            communication_records=comm_s,
            detector=detector,
            profiler=profiler,
            gateway=gateway,
            abm=abm,
            comm_graph=comm,
            inventory=inventory,
            source_mode="feature_store",
            replay_speed=pacing_speed,
            session_trace=session_trace,
            sleeper=sleeper,
        )
    elif source_mode == "direct_raw":
        fused_s, beh_s = direct_streams()
        runner = ReplayRunner(
            fused_records=fused_s,
            behavior_records=beh_s,
            detector=detector,
            profiler=profiler,
            gateway=gateway,
            abm=abm,
            comm_graph=comm,
            inventory=inventory,
            source_mode="direct_raw",
            replay_speed=pacing_speed,
            session_trace=session_trace,
            sleeper=sleeper,
        )
    else:
        raise ValueError(f"unsupported source_mode {source_mode!r}")

    control = ReplayControl(start_paused=start_paused)
    return ScientificRuntime(
        runner=runner,
        control=control,
        abm=abm,
        comm_graph=comm,
        inventory=inventory,
        gateway=gateway,
    )


def _catalog_module():
    from datasets.datasense import catalog as catalog_mod

    return catalog_mod


# ---------------------------------------------------------------------------
# Snapshot builders (contract conversion only)
# ---------------------------------------------------------------------------


def device_state_contracts(runtime: ScientificRuntime, replay_id: str):
    from backend.app.contracts.device_state_v1 import DeviceStateV1
    from datasets.datasense.windowing import iso_utc_from_ns

    inv = runtime.inventory
    out = []
    ts = (
        iso_utc_from_ns(runtime.runner.last_ts_hint_ns)
        if hasattr(runtime.runner, "last_ts_hint_ns") and runtime.runner.last_ts_hint_ns
        else None
    )
    for name, st in sorted(runtime.abm.states.items()):
        rec = inv.by_name.get(name)
        out.append(
            DeviceStateV1(
                replay_id=replay_id,
                entity_id=name,
                logical_timestamp=st.last_network_update or st.last_behavior_update or ts,
                window_id=runtime.abm.current_window_id,
                network_observed=st.network_observed,
                behavior_observed=st.behavior_observed,
                behavior_supported=st.behavior_supported,
                network_risk=st.network_risk,
                behavior_risk=st.behavior_risk,
                propagated_risk=st.propagated_risk,
                systemic_risk=st.systemic_risk,
                is_attacker=st.is_attacker,
                is_protected_asset=st.is_protected_asset,
                operational_state=st.operational,
                compromise_state=st.compromised,
                provenance={"role": st.role},
            )
        )
    return out


def device_risk_graph_contract(runtime: ScientificRuntime, replay_id: str):
    from backend.app.contracts.graph_snapshot_v1 import (
        DeviceRiskEdgeV1,
        DeviceRiskGraphSnapshotV1,
        DeviceRiskNodeV1,
    )

    topo = runtime.abm.topology
    nodes = []
    for name, st in sorted(runtime.abm.states.items()):
        nd = topo.nodes.get(name, {})
        nodes.append(
            DeviceRiskNodeV1(
                entity_id=name,
                role=st.role,
                device_type=st.device_type,
                network_observed=st.network_observed,
                behavior_observed=st.behavior_observed,
                behavior_supported=st.behavior_supported,
                network_risk=st.network_risk,
                behavior_risk=st.behavior_risk,
                propagated_risk=st.propagated_risk,
                systemic_risk=st.systemic_risk,
                is_attacker=st.is_attacker,
                is_protected_asset=st.is_protected_asset,
            )
        )
    edges = [
        DeviceRiskEdgeV1(
            src_entity_id=u,
            dst_entity_id=v,
            relationship=d.get("relation"),
            direction="directed",
            evidence_type=d.get("provenance"),
        )
        for u, v, d in topo.edges(data=True)
    ]
    return DeviceRiskGraphSnapshotV1(
        replay_id=replay_id,
        window_id=runtime.abm.current_window_id,
        nodes=nodes,
        edges=edges,
        provenance={"source_component": "backend.app.adapters.stage2_replay_adapter"},
    )


def communication_graph_contract(runtime: ScientificRuntime, replay_id: str):
    from backend.app.contracts.graph_snapshot_v1 import (
        CommunicationEdgeV1,
        CommunicationGraphSnapshotV1,
    )

    g = runtime.comm_graph.g
    nodes = list(g.nodes)
    edges = []
    for u, v, d in g.edges(data=True):
        delta = runtime.comm_graph.get_window_delta(u, v)
        edges.append(
            CommunicationEdgeV1(
                src_entity_id=u,
                dst_entity_id=v,
                packet_count_total=d.get("packet_count_total", 0),
                captured_byte_total=d.get("captured_byte_total", 0),
                protocols_ever=list(d.get("protocols_ever", [])),
                first_window_id=d.get("first_window_id"),
                last_window_id=d.get("last_window_id"),
                first_timestamp_utc=d.get("first_timestamp_utc"),
                last_timestamp_utc=d.get("last_timestamp_utc"),
                broadcast_ever=d.get("broadcast_ever", False),
                multicast_ever=d.get("multicast_ever", False),
                packet_count_delta=delta["packet_count_delta"],
                captured_byte_delta=delta["captured_byte_delta"],
                protocols_in_window=delta["protocols_in_window"],
            )
        )
    return CommunicationGraphSnapshotV1(
        replay_id=replay_id,
        window_id=runtime.comm_graph.current_window_id
        if runtime.comm_graph.current_window_id is not None
        else runtime.abm.current_window_id,
        nodes=nodes,
        edges=edges,
        provenance={"source_component": "backend.app.adapters.stage2_replay_adapter"},
    )


def srep_contract(runtime: ScientificRuntime, replay_id: str):
    from backend.app.contracts.srep_snapshot_v1 import SrepSnapshotV1
    from srep.device_srep import SREPEngine

    report = SREPEngine(runtime.abm, runtime.comm_graph.g).run()
    return SrepSnapshotV1(
        replay_id=replay_id,
        mode="DEVICE_ONLY",
        mode_note=report.get("mode_note"),
        window_id=report.get("last_window_id"),
        steps_replayed=report.get("steps_replayed"),
        defended_blast_radius=report.get("defended_blast_radius"),
        compromised_protected_assets=report.get("compromised_protected_assets", []),
        top_risky_protected_nodes=report.get("top_risky_protected_nodes", []),
        device_risk_nodes=[
            n for n in report.get("device_risk_nodes", [])
        ],
        simulation_defined_parameters=dict(report.get("simulation_defined_parameters", {})),
        provenance={
            "source_component": "backend.app.adapters.stage2_replay_adapter",
            "parameter_disclaimer": report.get("parameter_disclaimer"),
        },
    ), report
