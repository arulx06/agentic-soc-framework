"""Scientific non-interference: event sink must not alter results (§21.4)."""

from copy import deepcopy

import pytest

from backend.app.services.replay_controller import ReplayController
from datasets.datasense.devices import DeviceInventory
from simulation.comparison import assert_scientific_equivalence, scientific_projection
from simulation.replay import ReplayRunner, ReplayControl
from simulation.topology import build_topology
from srep.device_srep import SREPEngine

REPO = None
SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"


def _repo():
    global REPO
    if REPO is None:
        from pathlib import Path

        REPO = Path(__file__).resolve().parents[2]
    return REPO


def _inventory():
    from datasets.datasense.devices import DeviceInventory

    return DeviceInventory.load(_repo() / "data/raw/datasense/docs/site/devices.csv")


def _run_replay(with_instrumentation: bool):
    from simulation.abm import DeviceABM
    from simulation.communication_graph import build_comm_graph

    inv = _inventory()
    abm = DeviceABM(inv, build_topology(inv))
    comm = build_comm_graph(inventory=inv)
    control = ReplayControl()
    events = []

    def build_runner():
        from backend.app.adapters.stage2_replay_adapter import load_models
        from agents.finding_gateway import FindingGateway
        from datasets.datasense.feature_store import FeatureStoreReader

        detector, profiler = load_models()
        gateway = FindingGateway(abm)
        reader = FeatureStoreReader(_repo() / "data/processed/datasense")
        return ReplayRunner(
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

    runner_holder = {}
    runner = build_runner()
    runner_holder["runner"] = runner

    sink = (lambda etype, **data: events.append((etype, data))) if with_instrumentation else None
    summary = runner.run(event_sink=sink, control=control if with_instrumentation else None)
    srep = SREPEngine(abm, comm.g).run()

    def cleanup():
        runner_holder["runner"].cleanup()
        abm.close()
        comm.close()

    return summary, srep, events, cleanup


@pytest.fixture(scope="module")
def both_runs():
    plain = _run_replay(with_instrumentation=False)
    instrumented = _run_replay(with_instrumentation=True)
    try:
        yield plain[:2], instrumented[:2], instrumented[2]
    finally:
        plain[3]()
        instrumented[3]()


def test_sink_does_not_change_scientific_state(both_runs):
    (plain_summary, plain_srep), (inst_summary, inst_srep), _events = both_runs
    assert_scientific_equivalence(
        {"replay": plain_summary, "srep": plain_srep},
        {"replay": deepcopy(inst_summary), "srep": deepcopy(inst_srep)},
    )


def test_sink_actually_captured_events(both_runs):
    (_p, _ps), (_i, _is), events = both_runs
    types = [t for t, _ in events]
    assert types.count("NETWORK_FINDING") == 475
    assert types.count("BEHAVIOR_FINDING") == 150
    assert "WINDOW_COMPLETED" in types


def test_observation_mask_475_findings(both_runs):
    (plain_summary, _), (_, __), ___ = both_runs
    assert plain_summary["findings_emitted"]["network"] == 475
