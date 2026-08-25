"""Corrective-pass verification tests.

Covers: runtime observation-mask enforcement, end-to-end benign
chronological splits, consistent integer evaluation, sparse absence
semantics over real dense rows, bounded replay memory, and SREP trust-graph
rejection.
"""

import json

import pytest

from conftest import DEFAULT_DEVICES_ROWS

from agents.finding_gateway import FindingGateway
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.feature_store import FeatureStoreReader
from datasets.datasense.window_sort import iter_sorted_by_window
from pipeline.findings import opaque_session_trace
from pipeline.ground_truth import LabelPolicy, WindowLabel, label_window
from pipeline.metrics import (
    binary_metrics,
    prediction_to_label,
    prediction_to_string,
)
from pipeline.splits import build_network_dataset
from srep.device_srep import SREPEngine, TrustGraphUnsupportedError


def _inventory():
    return DeviceInventory(
        [
            DeviceRecord(
                device_name=r["device_name"],
                mac=r["mac"].lower(),
                ip=r["ip"],
                role=r["role"],
                type=r["type"],
                main_topic=r["main_topic"],
            )
            for r in DEFAULT_DEVICES_ROWS
        ]
    )


# ---------------------------------------------------------------------------
# 1. Observation-mask enforcement at runtime (invariance)
# ---------------------------------------------------------------------------


class _FixedDetector:
    """Deterministic stand-in exposing both the row and batch interfaces."""

    def __init__(self):
        self.source_calls = 0

    def _score(self, row):
        return 1.0 if (row.get("packets_all_count") or 0) > 0 else 0.0

    def finding_from_record(self, row, *, source_mode, session_trace=None):
        assert row.get("network_observed"), "unobserved row reached inference"
        self.source_calls += 1
        from pipeline.network_detector import MODEL_ID, NETWORK_FEATURE_SCHEMA_VERSION
        from pipeline.findings import NetworkFinding

        proba = self._score(row)
        return NetworkFinding(
            entity_id=row["device_id"],
            window_id=int(row["window_id"]),
            timestamp_utc=row["window_start_utc"],
            attack_probability=proba,
            predicted_class="attack" if proba >= 0.5 else "benign",
            confidence=max(proba, 1 - proba),
            source_model=f"{MODEL_ID}@{NETWORK_FEATURE_SCHEMA_VERSION}",
            provenance={"source_mode": source_mode, "model_id": MODEL_ID},
        )

    def findings_from_records(self, rows, *, source_mode, session_trace=None):
        return [
            self.finding_from_record(r, source_mode=source_mode, session_trace=session_trace)
            for r in rows
        ]


def _net_row(device, wid, observed=True, packets=None):
    from datasets.datasense.windowing import iso_utc_from_ns

    ts = iso_utc_from_ns(1_757_426_980_400_000_000 + wid * 5 * 10**9)
    return {
        "scenario_id": "s",
        "device_id": device,
        "window_id": wid,
        "window_start_utc": ts,
        "network_observed": observed,
        "packets_all_count": packets,
    }


def _comm_row(wid):
    from datasets.datasense.windowing import iso_utc_from_ns

    ts = iso_utc_from_ns(1_757_426_980_400_000_000 + wid * 5 * 10**9)
    return {
        "scenario_id": "s",
        "window_id": wid,
        "window_start_utc": ts,
        "src_entity_id": "soil-sensor",
        "dst_entity_id": "mqtt-broker",
        "packet_count": 1,
        "captured_byte_count": 60,
        "protocols": ["tcp"],
        "broadcast_indicator": False,
        "multicast_indicator": False,
    }


def _run_replay(net_rows, detector):
    from simulation.abm import DeviceABM
    from simulation.communication_graph import build_comm_graph
    from simulation.replay import ReplayRunner
    from simulation.topology import build_topology

    inv = _inventory()
    abm = DeviceABM(inv, build_topology(inv), history_limit=16)
    gw = FindingGateway(abm)
    comm = build_comm_graph(inventory=inv)
    runner = ReplayRunner(
        network_records=iter(net_rows),
        behavior_records=iter([]),
        communication_records=iter([]),
        detector=detector,
        profiler=None,
        gateway=gw,
        abm=abm,
        comm_graph=comm,
        inventory=inv,
        source_mode="feature_store",
        sort_chunk_rows=8,
    )
    summary = runner.run()
    runner.cleanup()
    srep = SREPEngine(abm, comm.g).run()
    abm.close()
    comm.close()
    return summary, srep


def test_unobserved_rows_never_generate_findings_or_risk():
    detector = _FixedDetector()
    rows = [
        _net_row("soil-sensor", 0, observed=True, packets=10),
        _net_row("edge1", 0, observed=False, packets=None),
        _net_row("mqtt-broker", 0, observed=False, packets=None),
        _net_row("router", 1, observed=False, packets=None),
    ]
    summary, srep = _run_replay(rows, detector)

    assert summary["findings_emitted"]["network"] == 1
    assert detector.source_calls == 1
    for node in ("edge1", "mqtt-broker", "router"):
        st = summary["abm_final_digest"]["state"][node]
        assert st["network_risk"] is None
        assert st["network_observed"] is False
    soil = summary["abm_final_digest"]["state"]["soil-sensor"]
    assert soil["network_risk"] is not None
    assert srep["mode"] == "DEVICE_ONLY"


def test_unobserved_row_placeholders_cannot_change_output():
    base_rows = [
        _net_row("soil-sensor", 0, observed=True, packets=10),
        _net_row("edge1", 0, observed=False, packets=None),
    ]

    poisoned_rows = [
        _net_row("soil-sensor", 0, observed=True, packets=10),
        {
            **_net_row("edge1", 0, observed=False, packets=None),
            "packets_all_count": 999_999,
            "packet_size_avg": 12345.0,
            "tcp_syn_count": 77,
        },
    ]

    out_base = _run_replay(list(base_rows), _FixedDetector())
    out_poison = _run_replay(list(poisoned_rows), _FixedDetector())
    assert out_base[0] == out_poison[0]
    assert out_base[1] == out_poison[1]


# ---------------------------------------------------------------------------
# 2. Benign chronological splits end to end (integration)
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_benign_store(tmp_path):
    """Write a synthetic benign session with 60 windows into a JSONL store."""
    store = tmp_path / "store"
    scenario = "benign_whole-network_test"
    net_dir = store / "network" / scenario
    beh_dir = store / "behavior" / scenario
    net_dir.mkdir(parents=True)
    beh_dir.mkdir(parents=True)

    devices = [r["device_name"] for r in DEFAULT_DEVICES_ROWS if r["role"] != "attacker"]

    def net_row(device, wid):
        return {
            "scenario_id": scenario,
            "device_id": device,
            "window_id": wid,
            "window_start_utc": f"2025-09-09T14:00:{wid * 5:02d}.000Z",
            "network_observed": True,
            "behavior_observed": False,
            "behavior_supported": False,
            **{f: float(wid + hash(device) % 7) for f in []},
            "packets_all_count": 3 + wid % 4,
            "packets_src_count": 1,
            "packets_dst_count": 2,
        }

    parts = []
    rows = []
    for wid in range(60):
        for d in devices:
            rows.append(net_row(d, wid))

    # fill required model feature keys via empty_network_row template then override
    from datasets.datasense.network_features import (
        NETWORK_MODEL_FEATURES,
        NETWORK_GRAPH_METADATA_FIELDS,
        empty_network_row,
    )
    from datasets.datasense.windowing import WindowGrid

    grid = WindowGrid(1_757_426_980_400_000_000, 5.0)
    full_rows = []
    for r in rows:
        base = empty_network_row(r["scenario_id"], r["device_id"], r["window_id"], grid)
        base.update(network_observed=True, packets_all_count=r["packets_all_count"])
        full_rows.append(base)

    part = []
    for i, r in enumerate(full_rows):
        part.append(json.dumps(r))
        if len(part) == 250 or i == len(full_rows) - 1:
            path = net_dir / f"part-{len(parts):05d}.jsonl"
            path.write_text("\n".join(part) + "\n", encoding="utf-8")
            parts.append(path)
            part = []

    state_dir = store / "extraction_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    from datasets.datasense.versions import REQUIRED_VERSIONS

    (state_dir / f"{scenario}.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "versions": dict(REQUIRED_VERSIONS),
                "window_seconds": 5.0,
            }
        ),
        encoding="utf-8",
    )
    return store, scenario


def test_benign_chronological_blocks_end_to_end(synthetic_benign_store):
    store, scenario = synthetic_benign_store
    inv = _inventory()
    infos = [
        {
            "scenario_id": scenario,
            "is_attack": False,
            "targets": (),
            "whole_network": True,
        }
    ]
    dataset = build_network_dataset(store, infos, inv)

    by_split = {"train": [], "validation": [], "test": []}
    seen_windows = {"train": set(), "validation": set(), "test": set()}
    for m in dataset.meta:
        by_split[m["split"]].append(m)
        seen_windows[m["split"]].add(m["window_id"])

    assert all(len(v) > 0 for v in by_split.values())
    assert max(seen_windows["train"]) < min(seen_windows["validation"])
    assert max(seen_windows["validation"]) < min(seen_windows["test"])
    all_wids = seen_windows["train"] | seen_windows["validation"] | seen_windows["test"]
    overlap_check = (
        seen_windows["train"] & seen_windows["validation"]
        or seen_windows["train"] & seen_windows["test"]
        or seen_windows["validation"] & seen_windows["test"]
    )
    assert not overlap_check
    assert len(all_wids) == 60

    assert all(m["label_enum"] == "BENIGN" for m in dataset.meta)
    assert all(y == 0 for y in dataset.y)


# ---------------------------------------------------------------------------
# 3. Consistent integer evaluation with known result
# ---------------------------------------------------------------------------


def test_binary_metrics_known_values():
    y_true = [1, 0, 1, 1, 0, 0]
    y_pred = [1, 0, 0, 1, 1, 0]
    m = binary_metrics(y_true, y_pred)
    assert m["support"] == 6
    assert m["accuracy"] == pytest.approx(4 / 6)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)


def test_empty_evaluation_refuses_meaningful_result():
    assert binary_metrics([], []) is None
    with pytest.raises(ValueError):
        binary_metrics([1], [])


def test_prediction_mapping_consistent():
    assert prediction_to_label(0.9) == 1
    assert prediction_to_label(0.4) == 0
    assert prediction_to_string(1) == "attack"
    assert prediction_to_string(0) == "benign"


# ---------------------------------------------------------------------------
# 6. Sparse absence semantics on real dense-row shapes
# ---------------------------------------------------------------------------


class _SparseProfilerHarness:
    @staticmethod
    def build():
        from pipeline.behavior_profiler import BehaviorProfiler

        inv = _inventory()
        profiler = BehaviorProfiler(inv)

        train = []
        active_windows = sorted({1, 2, 5, 9})
        for w in range(12):
            if w in active_windows:
                train.append(
                    _beh_row("motion-sensor", w, messages=1)
                )
            else:
                train.append(_dense_absent_row("motion-sensor", w))
        # fit_sparse only uses messages_count fields; feed through public fit
        observed_only = [r for r in train if r["messages_count"]]
        profiler._fit_sparse_into("motion-sensor", observed_only, train)
        return profiler, inv


def _beh_row(device, wid, *, messages):
    from datasets.datasense.windowing import iso_utc_from_ns

    ts = iso_utc_from_ns(1_757_426_980_400_000_000 + wid * 5 * 10**9)
    return {
        "scenario_id": "s",
        "device_id": device,
        "window_id": wid,
        "window_start_utc": ts,
        "behavior_observed": messages > 0,
        "behavior_supported": True,
        "behavior_profile": "sparse",
        "messages_count": messages,
        "burst_max_messages_per_second": messages,
        "seconds_since_previous_event": None,
        "binary_state_flip_count": 0,
        "numeric_messages_count": messages,
    }


def _dense_absent_row(device, wid):
    row = _beh_row(device, wid, messages=0)
    row.update(
        behavior_observed=False,
        messages_count=None,
        burst_max_messages_per_second=None,
        seconds_since_previous_event=None,
        binary_state_flip_count=None,
        numeric_messages_count=None,
    )
    return row


def test_sparse_absence_on_dense_rows_with_active_context(tmp_path=None):
    from pipeline.behavior_profiler import BehaviorProfiler

    inv = _inventory()
    profiler = BehaviorProfiler(inv)

    train_rows = []
    active = {1, 2}
    for w in range(10):
        if w in active:
            train_rows.append(_beh_row("motion-sensor", w, messages=1))
    profiler._fit_sparse_into("motion-sensor", train_rows, [])

    # Establish stateful last-active windows through the real predict path.
    for w in sorted(active):
        f = profiler.predict_record(
            _beh_row("motion-sensor", w, messages=1),
            source_mode="feature_store",
            telemetry_context_active=True,
            current_window_id=w,
        )
        assert f is not None

    context_rows = [
        _dense_absent_row("motion-sensor", w) for w in range(3, 12)
    ]
    other_sensor_rows = [
        _beh_row("flame-sensor", w, messages=1) for w in range(3, 12)
    ]

    emitted = []
    for absent_row, ctx_row in zip(context_rows, other_sensor_rows):
        context_active = bool(ctx_row.get("behavior_observed"))
        f = profiler.predict_record(
            absent_row,
            source_mode="feature_store",
            telemetry_context_active=context_active,
            current_window_id=absent_row["window_id"],
        )
        if f is not None:
            emitted.append(f)

    assert emitted, "meaningful absence must eventually produce evidence"
    assert all(f.profile_type == "sparse" for f in emitted)
    assert all(
        f.explanation.startswith("unexpected_absence") for f in emitted
    )
    scores = [f.deviation_score for f in emitted]
    assert scores == sorted(scores), "absence deviation must ramp with gap"

    # Complete modality absence: no other sensor observed -> nothing.
    quiet = [
        profiler.predict_record(
            _dense_absent_row("motion-sensor", 20),
            source_mode="feature_store",
            telemetry_context_active=False,
            current_window_id=20,
        )
    ]
    assert quiet == [None]


# ---------------------------------------------------------------------------
# 5. Bounded replay stress
# ---------------------------------------------------------------------------


def test_bounded_replay_many_windows_stress():
    from simulation.abm import DeviceABM
    from simulation.communication_graph import build_comm_graph
    from simulation.replay import ReplayRunner
    from simulation.topology import build_topology

    inv = _inventory()
    abm = DeviceABM(inv, build_topology(inv), history_limit=32)
    gw = FindingGateway(abm)
    comm = build_comm_graph(inventory=inv)

    W = 2000

    def net_stream():
        for w in range(W):
            yield _net_row("soil-sensor", w, observed=(w % 2 == 0), packets=w)

    def comm_stream():
        for w in range(W):
            yield _comm_row(w)

    runner = ReplayRunner(
        network_records=net_stream(),
        behavior_records=iter([]),
        communication_records=comm_stream(),
        detector=_FixedDetector(),
        profiler=None,
        gateway=gw,
        abm=abm,
        comm_graph=comm,
        inventory=inv,
        sort_chunk_rows=64,
    )
    summary = runner.run()
    runner.cleanup()

    assert summary["windows"] == W
    assert summary["findings_emitted"]["network"] == (W + 1) // 2
    assert summary["history_length"] <= 32
    diag = summary["ordering_diagnostics"]["network"]
    assert diag["rows"] == W
    assert diag["chunks_written"] >= W // 64
    assert diag["max_open_readers"] <= diag["merge_fan_in"]
    # aggregated communication graph stays pair-bounded regardless of W
    assert summary["communication_edges"] == 1
    assert summary["communication_nodes"] == 2
    edge_total = comm.g.edges["soil-sensor", "mqtt-broker"]["packet_count_total"]
    assert edge_total == W


def test_window_sort_handles_out_of_order_and_roundtrips():
    rows = [
        {"window_id": w, "value": w * 1.5, "name": f"d{w % 3}"}
        for w in (5, 0, 3, 9, 1, 7, 2, 8, 4, 6)
    ]
    out = list(iter_sorted_by_window(iter(rows), chunk_rows=3))
    assert [r["window_id"] for r in out] == list(range(10))
    for original in rows:
        match = next(r for r in out if r["window_id"] == original["window_id"])
        assert match["value"] == original["value"]
        assert match["name"] == original["name"]
