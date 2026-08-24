#!/usr/bin/env python3
"""Downstream pipeline CLI (Prompt 2).

Modes:

  train-network    our network feature store -> Network Detector artifact
  train-behavior   our benign telemetry feature store -> Behaviour Profiler
  replay-store     cached feature store -> models -> Gateway -> ABM/SREP
  demo-direct-raw  raw PCAP+JSON -> Prompt-1 extractor -> same downstream path

Vendor processed CSVs are never consumed here.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from agents.finding_gateway import FindingGateway  # noqa: E402
from datasets.datasense.catalog import build_catalog  # noqa: E402
from datasets.datasense.devices import DeviceInventory  # noqa: E402
from datasets.datasense.extraction import (  # noqa: E402
    iter_behavior_rows,
    iter_pcap_feature_rows,
)
from datasets.datasense.feature_store import FeatureStoreReader  # noqa: E402
from datasets.datasense.profiles import resolve_profile  # noqa: E402
from datasets.datasense.versions import EXTRACTOR_VERSION  # noqa: E402
from config import DATASENSE_BEHAVIOR_CHRONO_SPLIT  # noqa: E402
from pipeline.behavior_profiler import BehaviorProfiler  # noqa: E402
from pipeline.findings import opaque_session_trace  # noqa: E402
from pipeline.network_detector import NetworkDetector  # noqa: E402
from pipeline.splits import (  # noqa: E402
    assign_session_splits,
    benign_chronological_block,
    save_split_manifest,
)
from simulation.abm import DeviceABM  # noqa: E402
from simulation.communication_graph import build_comm_graph  # noqa: E402
from simulation.replay import ReplayRunner  # noqa: E402
from simulation.topology import build_topology  # noqa: E402
from srep.device_srep import SREPEngine  # noqa: E402

RAW_ROOT = REPO / "data/raw/datasense/dataset/raw_files"
ATTACKS_CSV = REPO / "data/raw/datasense/docs/site/attacks.csv"
DEVICES_CSV = REPO / "data/raw/datasense/docs/site/devices.csv"
DEFAULT_STORE = REPO / "data/processed/datasense"
MODELS_DIR = REPO / "models/saved_models"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("datasense_pipeline")


def _context():
    catalog, diagnostics = build_catalog(RAW_ROOT, ATTACKS_CSV)
    inventory = DeviceInventory.load(DEVICES_CSV)
    by_id = {r.scenario_id: r for r in catalog}
    return catalog, inventory, by_id


def cmd_train_network(args) -> int:
    from pipeline.ground_truth import LabelPolicy
    from pipeline.metrics import binary_metrics, prediction_to_label

    catalog, inventory, by_id = _context()
    splits = assign_session_splits(catalog, seed=args.seed)

    chosen = []
    if args.session:
        for sid in [s.strip() for s in args.session.split(",")]:
            rec = by_id[sid]
            chosen.append(
                {
                    "scenario_id": sid,
                    "is_attack": rec.is_attack,
                    "targets": tuple(rec.targets),
                    "whole_network": rec.whole_network_target,
                    "split": splits["attacks"].get(sid, "train"),
                }
            )
    else:
        for sid, split in sorted(splits["attacks"].items()):
            rec = by_id[sid]
            chosen.append(
                {
                    "scenario_id": sid,
                    "is_attack": True,
                    "targets": tuple(rec.targets),
                    "whole_network": rec.whole_network_target,
                    "split": split,
                }
            )

    benign_used = []
    if args.include_benign:
        benign_used = list(splits["benign_sessions"])
        for sid in benign_used:
            chosen.append(
                {
                    "scenario_id": sid,
                    "is_attack": False,
                    "targets": (),
                    "whole_network": True,
                }
            )

    policy = LabelPolicy(context_as_negative_ablation=args.ablation_context_negative)
    reader = FeatureStoreReader(args.store)
    from pipeline.splits import build_network_dataset

    dataset = build_network_dataset(
        args.store,
        chosen,
        inventory,
        reader=reader,
        policy=policy,
        chrono=DATASENSE_BEHAVIOR_CHRONO_SPLIT,
    )
    dataset.meta = dataset.meta  # split already assigned per row

    train_rows = [
        r for r, m in zip(dataset.X_rows, dataset.meta) if m["split"] == "train"
    ]
    y_train = [y for y, m in zip(dataset.y, dataset.meta) if m["split"] == "train"]

    def split_xy(split):
        rows = [r for r, m in zip(dataset.X_rows, dataset.meta) if m["split"] == split]
        ys = [y for y, m in zip(dataset.y, dataset.meta) if m["split"] == split]
        return rows, ys

    X_val, y_val = split_xy("validation")
    X_test, y_test = split_xy("test")

    detector = NetworkDetector().fit(train_rows, y_train, split_manifest_path=str(args.split_manifest))

    metrics: dict = {}

    def split_metrics(split):
        rows, ys = split_xy(split)
        if not rows:
            return None
        preds = [
            prediction_to_label(p)
            for p, _c, _lbl in detector.predict_proba_batch(rows)
        ]
        return binary_metrics(ys, preds)

    for split_name in ("validation", "test"):
        m = split_metrics(split_name)
        if m:
            metrics[split_name] = m

    manifest_payload = {
        "attack_session_splits": {
            c["scenario_id"]: c.get("split", "chronological") for c in chosen if c["is_attack"]
        },
        "benign_blocks": getattr(dataset, "benign_blocks", {}),
        "benign_policy": (
            "chronological non-overlapping blocks "
            f"{DATASENSE_BEHAVIOR_CHRONO_SPLIT} mapped to train/validation/test"
        ),
        "seed": args.seed,
        "label_policy_version": policy.version,
        "label_policy_description": policy.describe(),
        "context_as_negative_ablation": bool(args.ablation_context_negative),
        "smoke_label": "SMOKE TEST / NOT RESEARCH RESULT",
        "dataset_summary": {
            "rows": len(dataset.X_rows),
            "positives": sum(dataset.y),
            "by_split": {
                s: sum(1 for m in dataset.meta if m["split"] == s)
                for s in ("train", "validation", "test")
            },
        },
        "metrics_smoke": metrics,
    }
    save_split_manifest(Path(args.split_manifest), manifest_payload)

    out = Path(args.model_out) if args.model_out else MODELS_DIR / "network_detector_v1_smoke.joblib"
    detector.metadata["label"] = "SMOKE TEST / NOT RESEARCH RESULT"
    detector.metadata["ground_truth_policy"] = policy.describe()
    detector.save(out)
    print(
        json.dumps(
            {
                "artifact": str(out),
                "split_manifest": str(args.split_manifest),
                "label_policy": policy.describe(),
                "benign_blocks": manifest_payload["benign_blocks"],
                "metrics_smoke": metrics,
                "rows_trained": len(train_rows),
                "rows_validation": len(X_val),
                "rows_test": len(X_test),
            },
            indent=2,
        )
    )
    return 0


def cmd_train_behavior(args) -> int:
    catalog, inventory, by_id = _context()
    from pipeline.splits import require_benign_sessions

    try:
        benign_ids = require_benign_sessions(by_id, args.session.split(","))
    except ValueError as exc:
        print(f"REFUSING TO TRAIN BEHAVIOURAL PROFILER: {exc}", file=sys.stderr)
        return 2

    reader = FeatureStoreReader(args.store)
    rows_by_device: dict[str, list[dict]] = {}
    for sid in benign_ids:
        for row in reader.iter_behavior_records(sid):
            if row.get("behavior_observed"):
                rows_by_device.setdefault(row["device_id"], []).append(row)

    if not rows_by_device:
        print(
            "REFUSING TO TRAIN: no observed behaviour records in the "
            "requested benign session(s).",
            file=sys.stderr,
        )
        return 2

    profiler = BehaviorProfiler(inventory).fit(rows_by_device)
    profiler.metadata["benign_sessions"] = benign_ids
    out = (
        Path(args.model_out)
        if args.model_out
        else MODELS_DIR / "behavior_profiler_v1_smoke.joblib"
    )
    profiler.save(out)
    summary = {
        "artifact": str(out),
        "benign_sessions": benign_ids,
        "profiles_built": {
            d: {
                "profile_type": p.profile_type,
                "train_windows": p.train_windows,
                "calibration_windows": p.calibration_windows,
                "held_out_windows": p.held_out_windows,
                "held_out_false_positive_rate": p.stats.get(
                    "held_out_false_positive_rate"
                ),
            }
            for d, p in sorted(profiler.profiles.items())
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


def _build_stack(args, inventory):
    abm = DeviceABM(
        inventory,
        build_topology(inventory),
        history_limit=args.history_limit,
        spill_path=Path(args.spill) if args.spill else None,
    )
    gateway = FindingGateway(abm, history_limit=args.history_limit)
    comm = build_comm_graph(inventory=inventory)
    return abm, gateway, comm


def cmd_replay_store(args) -> int:
    _, inventory, _ = _context()
    reader = FeatureStoreReader(args.store)
    state = reader.check_compatible(args.session)
    assert state["status"] == "completed"

    detector = NetworkDetector.load(Path(args.network_model)) if args.network_model else None
    profiler = BehaviorProfiler.load(Path(args.behavior_model)) if args.behavior_model else None

    abm, gateway, comm = _build_stack(args, inventory)
    runner = ReplayRunner(
        reader.iter_network_records(args.session),
        reader.iter_behavior_records(args.session),
        reader.iter_communication_records(args.session),
        detector=detector,
        profiler=profiler,
        gateway=gateway,
        abm=abm,
        comm_graph=comm,
        inventory=inventory,
        source_mode="feature_store",
        replay_speed=args.replay_speed,
        session_trace=opaque_session_trace(args.session),
    )
    summary = runner.run()
    runner.cleanup()
    abm.close()
    comm.close()
    srep = SREPEngine(abm, comm.g).run()
    print(json.dumps({"replay": summary, "srep_mode": srep["mode"], "srep": srep}, indent=2))
    return 0


def cmd_demo_direct_raw(args) -> int:
    _, inventory, by_id = _context()
    session = by_id[args.session]
    settings = resolve_profile(args.profile)

    collect = {}
    fused = iter_pcap_feature_rows(
        session,
        inventory,
        window_seconds=args.window_seconds,
        clock_tolerance_ns=int(args.clock_tolerance_ms * 1e6),
        max_event_lateness_ns=int(args.max_lateness_seconds * 1e9),
        active_window_capacity=settings.active_window_capacity,
        read_chunk_bytes=settings.read_chunk_bytes,
        collect=collect,
    )
    behavior = iter_behavior_rows(
        session,
        inventory,
        window_seconds=args.window_seconds,
        clock_tolerance_ns=int(args.clock_tolerance_ms * 1e6),
        max_event_lateness_ns=int(args.max_lateness_seconds * 1e9),
        active_window_capacity=settings.active_window_capacity,
    )

    detector = NetworkDetector.load(Path(args.network_model)) if args.network_model else None
    profiler = BehaviorProfiler.load(Path(args.behavior_model)) if args.behavior_model else None

    abm, gateway, comm = _build_stack(args, inventory)

    runner = ReplayRunner(
        fused_records=fused,
        behavior_records=behavior,
        detector=detector,
        profiler=profiler,
        gateway=gateway,
        abm=abm,
        comm_graph=comm,
        inventory=inventory,
        source_mode="direct_raw",
        replay_speed=args.replay_speed,
        session_trace=opaque_session_trace(args.session),
    )
    summary = runner.run()
    runner.cleanup()
    abm.close()
    comm.close()
    srep = SREPEngine(abm, comm.g).run()
    print(
        json.dumps(
            {
                "source_session": args.session,
                "extraction_diagnostics": {
                    "pcap_packets": collect.get("pcap_stats", {}).get("packets_yielded"),
                    "communication_edges": collect.get("communication_edge_count"),
                },
                "replay": summary,
                "srep_mode": srep["mode"],
                "srep": srep,
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("train-network")
    p.add_argument("--session")
    p.add_argument("--include-benign", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--ablation-context-negative",
        action="store_true",
        help="ABLATION ONLY: retain NON_TARGET_CONTEXT windows as negatives",
    )
    p.add_argument("--model-out", type=Path)
    p.add_argument(
        "--split-manifest",
        type=Path,
        default=MODELS_DIR / "split_manifest_smoke.json",
    )

    p = sub.add_parser("train-behavior")
    p.add_argument("--session", required=True)
    p.add_argument("--model-out", type=Path)

    p = sub.add_parser("replay-store")
    p.add_argument("--session", required=True)
    p.add_argument("--network-model", type=Path)
    p.add_argument("--behavior-model", type=Path)
    p.add_argument("--replay-speed", choices=("1x", "5x", "10x", "max"), default="max")
    p.add_argument("--history-limit", type=int, default=256)
    p.add_argument("--spill", type=Path)

    p = sub.add_parser("demo-direct-raw")
    p.add_argument("--session", required=True)
    p.add_argument("--network-model", type=Path)
    p.add_argument("--behavior-model", type=Path)
    p.add_argument("--profile", choices=("low", "standard", "auto"), default="low")
    p.add_argument("--window-seconds", type=float, default=5.0)
    p.add_argument("--clock-tolerance-ms", type=float, default=10.0)
    p.add_argument("--max-lateness-seconds", type=float, default=60.0)
    p.add_argument("--replay-speed", choices=("1x", "5x", "10x", "max"), default="max")
    p.add_argument("--history-limit", type=int, default=256)
    p.add_argument("--spill", type=Path)

    return parser


def main(argv=None) -> int:
    handlers = {
        "train-network": cmd_train_network,
        "train-behavior": cmd_train_behavior,
        "replay-store": cmd_replay_store,
        "demo-direct-raw": cmd_demo_direct_raw,
    }
    args = build_parser().parse_args(argv)
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
