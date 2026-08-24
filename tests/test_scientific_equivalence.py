"""Scientific-projection equivalence between direct-raw and feature-store
replay using the SAVED smoke artifacts and the bounded audited fixture.

Fails if ANY device risk, replay-state or SREP scientific field differs.
Ordering diagnostics are compared separately as operational data.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "data/processed/datasense"
SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"
NETWORK_MODEL = REPO / "models/saved_models/network_detector_v1_smoke.joblib"
BEHAVIOR_MODEL = REPO / "models/saved_models/behavior_profiler_v1_smoke.joblib"

pytestmark = pytest.mark.skipif(
    not (
        (STORE / "network" / SESSION).is_dir()
        and NETWORK_MODEL.is_file()
        and BEHAVIOR_MODEL.is_file()
    ),
    reason="saved smoke artifacts / cached fixture partition unavailable",
)


def _inventory():
    from datasets.datasense.devices import DeviceInventory

    return DeviceInventory.load(REPO / "data/raw/datasense/docs/site/devices.csv")


def _load_models():
    from pipeline.behavior_profiler import BehaviorProfiler
    from pipeline.network_detector import NetworkDetector

    return (
        NetworkDetector.load(NETWORK_MODEL),
        BehaviorProfiler.load(BEHAVIOR_MODEL),
    )


def _stack(inv):
    import networkx  # noqa: F401

    from agents.finding_gateway import FindingGateway
    from simulation.abm import DeviceABM
    from simulation.communication_graph import build_comm_graph
    from simulation.topology import build_topology

    abm = DeviceABM(inv, build_topology(inv))
    return abm, FindingGateway(abm), build_comm_graph(inventory=inv)


def _catalog_session():
    from datasets.datasense.catalog import build_catalog

    catalog, _ = build_catalog(
        REPO / "data/raw/datasense/dataset/raw_files",
        REPO / "data/raw/datasense/docs/site/attacks.csv",
    )
    return next(r for r in catalog if r.scenario_id == SESSION)


def test_direct_vs_store_scientific_projection(tmp_path):
    from datasets.datasense.extraction import iter_behavior_rows, iter_pcap_feature_rows
    from datasets.datasense.feature_store import FeatureStoreReader
    from simulation.comparison import (
        assert_scientific_equivalence,
        ordering_projection,
    )
    from simulation.replay import ReplayRunner
    from srep.device_srep import SREPEngine

    session = _catalog_session()
    inv = _inventory()

    # INDEPENDENT model instances per mode: the Behavioural Profiler carries
    # stateful runtime gap/absence tracking, so sharing one instance across
    # replays would leak runtime state between modes.
    store_detector, store_profiler = _load_models()
    direct_detector, direct_profiler = _load_models()
    assert store_profiler is not direct_profiler
    assert store_detector is not direct_detector

    abm_s = gw_s = comm_s = runner_store = None
    abm_d = gw_d = comm_d = runner_direct = None
    try:
        # ---- feature-store mode
        abm_s, gw_s, comm_s = _stack(inv)
        reader = FeatureStoreReader(STORE)
        runner_store = ReplayRunner(
            reader.iter_network_records(SESSION),
            reader.iter_behavior_records(SESSION),
            reader.iter_communication_records(SESSION),
            detector=store_detector,
            profiler=store_profiler,
            gateway=gw_s,
            abm=abm_s,
            comm_graph=comm_s,
            inventory=inv,
            source_mode="feature_store",
        )
        summary_store = runner_store.run()
        srep_store = SREPEngine(abm_s, comm_s.g).run()

        # ---- direct-raw mode (independent stack + independent models)
        collect = {}
        fused = iter_pcap_feature_rows(
            session,
            inv,
            window_seconds=5.0,
            clock_tolerance_ns=10_000_000,
            max_event_lateness_ns=60 * 10**9,
            active_window_capacity=65536,
            read_chunk_bytes=1 << 20,
            collect=None,
        )
        behavior = iter_behavior_rows(
            session,
            inv,
            window_seconds=5.0,
            clock_tolerance_ns=10_000_000,
            max_event_lateness_ns=60 * 10**9,
            active_window_capacity=65536,
        )
        abm_d, gw_d, comm_d = _stack(inv)
        runner_direct = ReplayRunner(
            fused_records=fused,
            behavior_records=behavior,
            detector=direct_detector,
            profiler=direct_profiler,
            gateway=gw_d,
            abm=abm_d,
            comm_graph=comm_d,
            inventory=inv,
            source_mode="direct_raw",
        )
        summary_direct = runner_direct.run()
        srep_direct = SREPEngine(abm_d, comm_d.g).run()

        # observation-mask guarantee on eligible rows
        assert summary_direct["findings_emitted"]["network"] == 475
        assert summary_store["findings_emitted"]["network"] == 475

        # strict scientific projection equality (risks, state, SREP included)
        a = {"replay": summary_store, "srep": srep_store}
        b = {"replay": summary_direct, "srep": srep_direct}
        assert_scientific_equivalence(a, b)

        # ordering diagnostics compared SEPARATELY as operational differences
        od_store = ordering_projection(summary_store["ordering_diagnostics"])
        od_direct = ordering_projection(summary_direct["ordering_diagnostics"])
        for tag in ("network", "behavior", "communication"):
            assert tag in od_store and tag in od_direct
        for tag in ("network", "behavior", "communication"):
            assert od_store[tag]["rows"] == od_direct[tag]["rows"]
    finally:
        if runner_store is not None:
            runner_store.cleanup()
        if runner_direct is not None:
            runner_direct.cleanup()
        if abm_s is not None:
            abm_s.close()
        if abm_d is not None:
            abm_d.close()
        if comm_s is not None:
            comm_s.close()
        if comm_d is not None:
            comm_d.close()


def test_negative_comparator_detects_mutations(tmp_path):
    """The comparator must FAIL when any scientific field is mutated."""
    from copy import deepcopy

    from datasets.datasense.extraction import iter_behavior_rows, iter_pcap_feature_rows
    from datasets.datasense.feature_store import FeatureStoreReader
    from simulation.comparison import assert_scientific_equivalence
    from simulation.replay import ReplayRunner
    from srep.device_srep import SREPEngine

    session = _catalog_session()
    inv = _inventory()
    detector, profiler = _load_models()
    abm, gateway, comm = _stack(inv)
    reader = FeatureStoreReader(STORE)
    runner = None
    try:
        runner = ReplayRunner(
            reader.iter_network_records(SESSION),
            reader.iter_behavior_records(SESSION),
            reader.iter_communication_records(SESSION),
            detector=detector,
            profiler=profiler,
            gateway=gateway,
            abm=abm,
            comm_graph=comm,
            inventory=inv,
            source_mode="feature_store",
        )
        summary = runner.run()
        srep = SREPEngine(abm, comm.g).run()
    finally:
        if runner is not None:
            runner.cleanup()
        abm.close()
        comm.close()

    base = {"replay": deepcopy(summary), "srep": deepcopy(srep)}

    def mutated(kind):
        m = {"replay": deepcopy(summary), "srep": deepcopy(srep)}
        if kind == "device_network_risk":
            node = m["srep"]["device_risk_nodes"][0]
            node["network_risk"] = (
                0.123456 if node["network_risk"] is None else node["network_risk"] + 0.05
            )
        elif kind == "steps_replayed":
            m["srep"]["steps_replayed"] += 1
        elif kind == "blast_radius":
            m["replay"]["abm_final_digest"]["defended_blast_radius"] += 0.001
        else:
            raise ValueError(kind)
        return m

    with pytest.raises(AssertionError):
        assert_scientific_equivalence(base, mutated("device_network_risk"))
    with pytest.raises(AssertionError):
        assert_scientific_equivalence(base, mutated("steps_replayed"))
    with pytest.raises(AssertionError):
        assert_scientific_equivalence(base, mutated("blast_radius"))
