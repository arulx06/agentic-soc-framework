"""Execution equivalence (§33): profiles, replay speeds, direct vs store.

Uses the real cached smoke store for the audited fixture session and
smoke models trained in-test on the same bounded data.
"""

import json

import pytest

from agents.finding_gateway import FindingGateway
from datasets.datasense.devices import DeviceInventory
from datasets.datasense.feature_store import FeatureStoreReader
from simulation.abm import DeviceABM
from simulation.communication_graph import build_comm_graph
from simulation.replay import ReplayRunner
from simulation.topology import build_topology
from srep.device_srep import SREPEngine

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
STORE = REPO / "data/processed/datasense"
SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"

pytestmark = pytest.mark.skipif(
    not (STORE / "network" / SESSION).is_dir(),
    reason="cached smoke feature store for the fixture session is unavailable",
)


def _inventory():
    return DeviceInventory.load(REPO / "data/raw/datasense/docs/site/devices.csv")


def _train_smoke_models(tmp_path):
    from pipeline.network_detector import NetworkDetector
    from pipeline.behavior_profiler import BehaviorProfiler

    reader = FeatureStoreReader(STORE)
    net_rows = list(reader.iter_network_records(SESSION))
    train_rows = [r for r in net_rows if r["network_observed"]]
    y = [0] * len(train_rows)
    detector = NetworkDetector().fit(train_rows, y)

    beh_by_device = {}
    for row in reader.iter_behavior_records(SESSION):
        if row.get("behavior_observed"):
            beh_by_device.setdefault(row["device_id"], []).append(row)
    profiler = BehaviorProfiler(_inventory()).fit(beh_by_device)
    return detector, profiler


def _run(mode, detector, profiler, *, speed="max", sleeper=None, history_limit=64):
    inv = _inventory()
    abm = DeviceABM(inv, build_topology(inv), history_limit=history_limit)
    gw = FindingGateway(abm)
    comm = build_comm_graph(inventory=inv)
    reader = FeatureStoreReader(STORE)
    runner = ReplayRunner(
        reader.iter_network_records(SESSION),
        reader.iter_behavior_records(SESSION),
        reader.iter_communication_records(SESSION),
        detector=detector,
        profiler=profiler,
        gateway=gw,
        abm=abm,
        comm_graph=comm,
        inventory=inv,
        source_mode=mode,
        replay_speed=speed,
        sleeper=sleeper,
    )
    summary = runner.run()
    srep = SREPEngine(abm, comm).run()
    abm.close()

    def scrub(d):
        if isinstance(d, dict):
            return {
                k: scrub(v)
                for k, v in d.items()
                if k not in ("recorded_at", "generated_at", "replay_speed", "source_mode")
            }
        if isinstance(d, list):
            return [scrub(x) for x in d]
        return d

    return {"replay": scrub(summary), "srep": scrub(srep)}


@pytest.fixture(scope="module")
def smoke_models(tmp_path_factory):
    return _train_smoke_models(tmp_path_factory.mktemp("models"))


def test_replay_speeds_identical_logical_output(smoke_models):
    detector, profiler = smoke_models
    sleeps = []
    out_max = _run("feature_store", detector, profiler, speed="max")
    out_1x = _run(
        "feature_store",
        detector,
        profiler,
        speed="1x",
        sleeper=lambda s: sleeps.append(s),
    )
    assert sleeps and all(abs(s - 5.0) < 1e-9 for s in sleeps)
    assert out_max == out_1x


def test_history_limits_do_not_change_scientific_state(smoke_models):
    detector, profiler = smoke_models
    small = _run("feature_store", detector, profiler, history_limit=4)
    big = _run("feature_store", detector, profiler, history_limit=512)
    assert small["replay"]["abm_final_digest"] == big["replay"]["abm_final_digest"]
    assert small["srep"] == big["srep"]
    assert small["replay"]["history_length"] <= 4


def test_direct_raw_matches_feature_store_downstream(smoke_models):
    """Direct-raw extraction feeds the same ReplayRunner; final state must
    equal feature-store mode."""
    from datasets.datasense.catalog import build_catalog
    from datasets.datasense.extraction import iter_pcap_feature_rows, iter_behavior_rows

    catalog, diagnostics = build_catalog(
        REPO / "data/raw/datasense/dataset/raw_files",
        REPO / "data/raw/datasense/docs/site/attacks.csv",
    )
    session = next(r for r in catalog if r.scenario_id == SESSION)
    inventory = _inventory()

    detector, profiler = smoke_models

    inv2 = DeviceInventory.load(REPO / "data/raw/datasense/docs/site/devices.csv")
    abm2 = DeviceABM(inv2, build_topology(inv2), history_limit=64)
    gw2 = FindingGateway(abm2)
    comm2 = build_comm_graph(inventory=inv2)
    fused = iter_pcap_feature_rows(
        session,
        inv2,
        window_seconds=5.0,
        clock_tolerance_ns=10_000_000,
        max_event_lateness_ns=60 * 10**9,
        active_window_capacity=65536,
        read_chunk_bytes=1 << 20,
    )
    behavior = iter_behavior_rows(
        session,
        inv2,
        window_seconds=5.0,
        clock_tolerance_ns=10_000_000,
        max_event_lateness_ns=60 * 10**9,
        active_window_capacity=65536,
    )
    runner = ReplayRunner(
        fused_records=fused,
        behavior_records=behavior,
        detector=detector,
        profiler=profiler,
        gateway=gw2,
        abm=abm2,
        comm_graph=comm2,
        inventory=inv2,
        source_mode="direct_raw",
    )
    summary_direct = runner.run()
    srep_direct = SREPEngine(abm2, comm2).run()
    abm2.close()

    out_store = _run("feature_store", detector, profiler)
    assert summary_direct["findings_emitted"] == out_store["replay"]["findings_emitted"]
    assert summary_direct["windows"] == out_store["replay"]["windows"]
    assert (
        summary_direct["abm_final_digest"]["defended_blast_radius"]
        == out_store["replay"]["abm_final_digest"]["defended_blast_radius"]
    )
    assert (
        summary_direct["abm_final_digest"]["state"]
        == out_store["replay"]["abm_final_digest"]["state"]
    )
    assert srep_direct["defended_blast_radius"] == out_store["srep"]["defended_blast_radius"]
    assert srep_direct["mode"] == out_store["srep"]["mode"] == "DEVICE_ONLY"
