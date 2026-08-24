"""Closure-pass regression tests: vector/scalar equivalence, row/batch
network inference, stable multi-pass sorting with duplicate keys, and
temporary-file cleanup ownership."""

import pytest

from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.window_sort import WindowSorter
from pipeline.behavior_profiler import BehaviorProfiler
from pipeline.network_detector import NetworkDetector


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


TOL = 1e-12


# ---------------------------------------------------------------------------
# Behavioural scalar-vs-vector scoring equivalence
# ---------------------------------------------------------------------------


def _continuous_rows(n=40):
    rows = []
    for w in range(n):
        rows.append(
            {
                "scenario_id": "benign_x",
                "device_id": "soil-sensor",
                "window_id": w,
                "window_start_utc": f"2025-09-09T14:{w:02d}:00.000Z",
                "behavior_observed": True,
                "messages_count": 4 + (w % 3),
                "inter_message_delta_avg": 1.0 + 0.01 * (w % 4),
                "inter_message_delta_max": 1.5,
                "inter_message_delta_std": 0.2,
                "active_fraction_of_window": 1.0,
                "burst_max_messages_per_second": 1,
                "topics_active_count": 1,
                "topic_entropy": 0.0,
                "top_topic_message_share": 1.0,
                "numeric_messages_count": 5,
                "array_messages_count": 0,
                "string_messages_count": 0,
                "qos_levels_distinct_count": 1,
                "retained_messages_count": 0,
                "duplicate_messages_count": 0,
                "distinct_message_ids_count": w + 10,
                "value_avg": 280.0 + (w % 2),
            }
        )
    return rows


def test_behavior_vectorized_matches_scalar(tmp_path):
    inv = _inventory()
    profiler = BehaviorProfiler(inv)
    benign = {"soil-sensor": _continuous_rows(40)}
    profiler.fit(benign)
    prof = profiler.profiles["soil-sensor"]

    probe_rows = _continuous_rows(40)[30:]
    X = prof.feature_list
    from datasets.datasense.network_features import OnlineStats

    import numpy as np

    def score_scalar(row):
        raw = -float(prof.model.decision_function(
            np.array([[row[f] if row[f] is not None else 0.0 for f in X]],
                     dtype=np.float64)
        )[0])
        return float((raw + 0.5) / 1.5)

    # vectorized batch via internal helper on the same rows
    from pipeline.behavior_profiler import _vector

    X_batch = np.vstack([_vector(r, X) for r in probe_rows])
    raw_batch = -prof.model.decision_function(X_batch)
    batch_scores = [float((v + 0.5) / 1.5) for v in raw_batch]

    scalar_scores = [score_scalar(r) for r in probe_rows]
    assert len(batch_scores) == len(scalar_scores)
    for b, s in zip(batch_scores, scalar_scores):
        assert abs(b - s) <= TOL

    # threshold decisions identical either way
    tau = prof.thresholds["tau"]
    decisions_batch = [b >= tau for b in batch_scores]
    decisions_scalar = [s >= tau for s in scalar_scores]
    assert decisions_batch == decisions_scalar

    # held-out FPR recomputation matches recorded metadata
    held = _continuous_rows(40)[32:]
    held_scores = [
        float((v + 0.5) / 1.5)
        for v in (-prof.model.decision_function(np.vstack([_vector(r, X) for r in held])))
    ]
    fpr = sum(1 for s in held_scores if s >= tau) / max(1, len(held_scores))
    assert abs(fpr - prof.stats["held_out_false_positive_rate"]) <= TOL


def test_behavior_finding_membership_identical_scalar_vector(tmp_path):
    inv = _inventory()
    profiler = BehaviorProfiler(inv).fit({"soil-sensor": _continuous_rows(40)})
    rows = _continuous_rows(40)[36:]
    findings = [
        profiler.predict_record(r, source_mode="test") for r in rows
    ]
    assert all(f is not None for f in findings)


# ---------------------------------------------------------------------------
# Network row-vs-batch inference equivalence
# ---------------------------------------------------------------------------


def _trained_detector():
    from datasets.datasense.feature_store import FeatureStoreReader

    store = REPO_STORE
    reader = FeatureStoreReader(store)
    sid = "attack_recon_host-disc-udp-ping_soil-sensor"
    if not (store / "network" / sid).is_dir():
        pytest.skip("cached fixture network partition unavailable")
    rows = [
        r for r in reader.iter_network_records(sid) if r["network_observed"]
    ]
    detector = NetworkDetector().fit(rows[:200], [0, 1] * 100)
    return detector, rows[200:260]


REPO_STORE = None  # set in conftest-style below


def test_network_row_vs_batch_equivalent():
    global REPO_STORE
    REPO_STORE = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/processed/datasense"
    )
    detector, rows = _trained_detector()
    batch = detector.predict_proba_batch(rows)
    single = [detector.predict_proba_row(r) for r in rows]
    for (pb, _cl, _cf), (ps, _cls, _cfs) in zip(batch, single):
        assert abs(pb - ps) <= TOL
    # unobserved rows never enter the batch
    poisoned = [dict(rows[0], network_observed=False)]
    with pytest.raises(ValueError):
        detector.predict_proba_batch(poisoned)
    # stable ordering
    again = detector.predict_proba_batch(rows)
    assert [p for p, _c, _l in again] == [p for p, _c, _l in batch]


def test_findings_from_records_one_per_row_ordered():
    global REPO_STORE
    REPO_STORE = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "data/processed/datasense"
    )
    detector, rows = _trained_detector()
    trace = opaque_trace("s")
    findings = detector.findings_from_records(
        rows, source_mode="feature_store", session_trace=trace
    )
    assert len(findings) == len(rows)
    assert [f.entity_id for f in findings] == [r["device_id"] for r in rows]
    assert [f.window_id for f in findings] == [int(r["window_id"]) for r in rows]
    assert all(f.provenance.get("session_trace") == trace for f in findings)


def opaque_trace(sid):
    from pipeline.findings import opaque_session_trace

    return opaque_session_trace(sid)


# ---------------------------------------------------------------------------
# Stable multi-pass sorting with duplicate keys
# ---------------------------------------------------------------------------


def test_multipass_sort_stable_with_duplicate_window_ids(tmp_path):
    sorter = WindowSorter(chunk_rows=7, tmp_dir=tmp_path / "s", merge_fan_in=3)
    input_order = []
    for i in range(60):
        wid = i % 9
        row = {"window_id": wid, "seq": i}
        input_order.append(row)
        sorter.add(row)

    out = list(sorter.iter_sorted())
    assert [r["window_id"] for r in out] == sorted(r["window_id"] for r in input_order)
    # stability: within equal window_id, original arrival order preserved
    for wid in range(9):
        expected_seq = [r["seq"] for r in input_order if r["window_id"] == wid]
        got_seq = [r["seq"] for r in out if r["window_id"] == wid]
        assert got_seq == expected_seq
    assert sorter.max_open_readers <= 3


# ---------------------------------------------------------------------------
# Cleanup ownership on feeding failure
# ---------------------------------------------------------------------------


def test_cleanup_on_input_feeding_failure(tmp_path):
    class Boom(Exception):
        pass

    def source():
        for i in range(50):
            yield {"window_id": i % 6, "seq": i}
        raise Boom()

    sorter = WindowSorter(chunk_rows=8, tmp_dir=tmp_path / "s", merge_fan_in=2)
    fed = 0
    with pytest.raises(Boom):
        for row in source():
            sorter.add(row)
            fed += 1
    assert fed == 50
    sorter.cleanup()
    leftovers = list((tmp_path / "s").rglob("*.jsonl"))
    assert leftovers == []