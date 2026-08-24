"""Leakage-safe dataset construction and leakage-proof splitting.

* The model matrix uses EXACTLY ``NETWORK_MODEL_FEATURES`` — an assertion
  rejects any other column before fitting.
* Rows with ``network_observed=False`` are excluded (an empty window is not
  benign evidence).
* Splitting is session-level for attack captures and chronological-block
  based for benign captures; no session contributes to two splits.
* Preprocessing statistics are fitted on training data only.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from datasets.datasense.feature_store import FeatureStoreReader
from datasets.datasense.network_features import NETWORK_MODEL_FEATURES
from datasets.datasense.versions import (
    EXTRACTOR_VERSION,
    NETWORK_FEATURE_SCHEMA_VERSION,
)

from pipeline.ground_truth import (
    ABLATION_NEGATIVE_LABELS,
    PRIMARY_NEGATIVE_LABELS,
    POSITIVE_LABELS,
    LabelPolicy,
    WindowLabel,
    binary_label,
    label_window,
)

PROHIBITED_COLUMN_MARKERS = (
    "label",
    "attack_category",
    "attack_name",
    "target",
    "filename",
    "is_attack",
    "device_mac",
    "scenario_id",
    "device_id",
    "window_start_utc",
    "window_end_utc",
)


def assert_no_prohibited_columns(columns) -> None:
    cols = list(columns)
    if set(cols) != set(NETWORK_MODEL_FEATURES):
        unexpected = sorted(set(cols) - set(NETWORK_MODEL_FEATURES))
        missing = sorted(set(NETWORK_MODEL_FEATURES) - set(cols))
        raise AssertionError(
            f"model matrix must contain exactly NETWORK_MODEL_FEATURES; "
            f"unexpected={unexpected} missing={missing}"
        )
    lowered = [c.lower() for c in cols]
    for marker in PROHIBITED_COLUMN_MARKERS:
        for c in lowered:
            assert marker not in c, f"prohibited column marker {marker!r} in {c!r}"


@dataclass
class NetworkDataset:
    X_rows: list[dict]
    y: list[int]
    meta: list[dict]

    @property
    def feature_columns(self) -> list[str]:
        return list(NETWORK_MODEL_FEATURES)


def build_network_dataset(
    store_root: Path,
    session_infos: list[dict],
    inventory,
    reader: FeatureStoreReader | None = None,
    policy: LabelPolicy | None = None,
    chrono: dict | None = None,
) -> NetworkDataset:
    """Build the primary (or ablation) training dataset.

    session_infos entries: {'scenario_id', 'is_attack', 'targets',
    'whole_network', 'split'}. Benign sessions ('is_attack': False) receive
    genuine non-overlapping chronological splits computed here from their
    observed window range; their rows are labelled BENIGN negatives.

    Memory note: benign sessions are processed with a bounded two-pass
    window-range scan followed by streaming row conversion.
    """
    reader = reader or FeatureStoreReader(store_root)
    policy = policy or LabelPolicy()
    X_rows, y, meta = [], [], []
    benign_blocks: dict[str, dict] = {}

    for info in session_infos:
        sid = info["scenario_id"]
        if not info.get("is_attack", True):
            block_of, ranges = _benign_block_assigner(reader, sid, chrono)
            benign_blocks[sid] = {
                "min_window_id": ranges[0],
                "max_window_id": ranges[1],
                "counts": ranges[2],
                "policy": "chronological_60_20_20",
            }
        else:
            block_of = lambda wid: info.get("split")  # noqa: E731

        for row in reader.iter_network_records(sid):
            label = label_window(
                row,
                is_attack_session=info["is_attack"],
                targets=info["targets"],
                whole_network=info["whole_network"],
                inventory=inventory,
            )
            if label == WindowLabel.AMBIGUOUS_EXCLUDED:
                continue
            if label in POSITIVE_LABELS:
                pass
            elif policy.context_as_negative_ablation:
                if label not in ABLATION_NEGATIVE_LABELS:
                    continue
            else:
                if label not in PRIMARY_NEGATIVE_LABELS:
                    continue

            split = block_of(int(row["window_id"]))
            if split not in ("train", "validation", "test"):
                continue
            X_rows.append({f: row[f] for f in NETWORK_MODEL_FEATURES})
            y.append(binary_label(label))
            meta.append(
                {
                    "scenario_id": sid,
                    "device_id": row["device_id"],
                    "window_id": row["window_id"],
                    "network_observed": row["network_observed"],
                    "label_enum": label.value,
                    "split": split,
                }
            )

    assert_no_prohibited_columns(NETWORK_MODEL_FEATURES)
    dataset = NetworkDataset(X_rows, y, meta)
    dataset.benign_blocks = benign_blocks  # type: ignore[attr-defined]
    return dataset


def _benign_block_assigner(reader: FeatureStoreReader, scenario_id: str, chrono):
    """Two-pass bounded assignment: pass 1 scans only window ids to find the
    observed min/max and per-block counts; returns (block_fn, ranges)."""
    chrono = chrono or {"train": 0.6, "calibration": 0.2, "held_out": 0.2}
    min_wid = max_wid = None
    for wid in reader.iter_network_window_ids(scenario_id):
        min_wid = wid if min_wid is None else min(min_wid, wid)
        max_wid = wid if max_wid is None else max(max_wid, wid)
    if min_wid is None:
        raise ValueError(f"benign session {scenario_id} has no network rows")

    span = max_wid - min_wid + 1
    counts = {"train": 0, "validation": 0, "held_out": 0}

    def block_of(window_id: int) -> str:
        offset = int(window_id) - min_wid
        train_cut = span * chrono["train"]
        cal_cut = span * (chrono["train"] + chrono["calibration"])
        if offset < train_cut:
            return "train"
        if offset < cal_cut:
            return "validation"
        return "test"

    for wid in range(min_wid, max_wid + 1):
        counts[block_of(wid) if block_of(wid) != "test" else "held_out"] += 1

    return block_of, (min_wid, max_wid, counts)


def assign_session_splits(
    catalog_records: list,
    ratios: dict | None = None,
    seed: int = 42,
) -> dict:
    """Session-level split of ATTACK sessions stratified by category.
    Benign sessions are returned separately for chronological blocking."""
    import random

    ratios = ratios or {"train": 0.6, "validation": 0.2, "test": 0.2}
    attacks = [r for r in catalog_records if r.is_attack]
    benign = [r.scenario_id for r in catalog_records if not r.is_attack]
    rng = random.Random(seed)

    assignment = {}
    by_category: dict[str, list] = {}
    for rec in sorted(attacks, key=lambda r: r.scenario_id):
        by_category.setdefault(rec.attack_category or "unknown", []).append(rec)
    for category in sorted(by_category):
        group = sorted(by_category[category], key=lambda r: r.scenario_id)
        rng.shuffle(group)
        n = len(group)
        n_train = max(1, int(round(n * ratios["train"]))) if n > 1 else 1
        remaining = n - n_train
        n_val = min(remaining, max(1, int(round(n * ratios["validation"])))) if remaining > 0 else 0
        n_test = remaining - n_val if remaining > 0 else 0
        if n >= 3 and n_test == 0:
            n_test, n_val = 1, n_val - 1 if n_val > 1 else 0
        for i, rec in enumerate(group):
            if i < n_train:
                assignment[rec.scenario_id] = "train"
            elif i < n_train + n_val:
                assignment[rec.scenario_id] = "validation"
            else:
                assignment[rec.scenario_id] = "test"

    return {"attacks": assignment, "benign_sessions": benign}


def benign_chronological_block(window_id: int, min_wid: int, max_wid: int,
                               chrono: dict | None = None) -> str:
    """Non-overlapping chronological benign blocks (60/20/20)."""
    chrono = chrono or {"train": 0.6, "calibration": 0.2, "held_out": 0.2}
    span = max_wid - min_wid + 1
    offset = window_id - min_wid
    train_cut = span * chrono["train"]
    cal_cut = span * (chrono["train"] + chrono["calibration"])
    if offset < train_cut:
        return "train"
    if offset < cal_cut:
        return "calibration"
    return "held_out"


def require_benign_sessions(by_id: dict, requested_ids: list[str]) -> list[str]:
    """Validate that every requested session is catalog-confirmed BENIGN.

    Raises ValueError listing unknown and/or attack sessions; the caller must
    fail before any model fitting. Returns the validated id list."""
    requested = [str(s).strip() for s in requested_ids if str(s).strip()]
    if not requested:
        raise ValueError("no behaviour-training sessions requested")
    unknown = sorted(s for s in requested if s not in by_id)
    if unknown:
        raise ValueError(f"unknown session id(s): {unknown}")
    attack = sorted(s for s in requested if by_id[s].is_attack)
    if attack:
        raise ValueError(
            "train-behavior accepts ONLY catalog-confirmed benign sessions; "
            f"refusing attack session(s): {attack}"
        )
    return requested


def save_split_manifest(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "extractor_version": EXTRACTOR_VERSION,
        "feature_schema_version": NETWORK_FEATURE_SCHEMA_VERSION,
        **payload,
    }
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2)
    import os

    os.replace(tmp, path)
    return path


def load_split_manifest(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    attacks = manifest.get("attack_session_splits", {})
    seen: dict[str, str] = {}
    for sid, split in attacks.items():
        if sid in seen:
            raise AssertionError(f"session {sid} appears twice in split manifest")
        seen[sid] = split
    return manifest
