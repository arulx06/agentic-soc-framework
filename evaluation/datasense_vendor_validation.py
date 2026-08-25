#!/usr/bin/env python3
"""INTERNAL FEATURE VALIDATION - DataSense vendor-processed CSV comparator.

ISOLATION GUARANTEE: this utility exists only for offline cross-checking of
our raw-derived five-second features against the vendor release's processed
CSVs. No production ingestion or feature-store component imports, requires,
or falls back to vendor processed files. Removing ``processed_files/`` from
the dataset leaves the whole pipeline fully operational.

Regression fixture (audited exact reproduction, see docs/datasense_raw_audit.md
section 8): session ``attack_recon_host-disc-udp-ping_soil-sensor`` where the
audit reproduced vendor ``network_packets_all_count`` and ``log_messages_count``
exactly on all twelve 5 s windows.

Usage:
    python evaluation/datasense_vendor_validation.py \
        --session attack_recon_host-disc-udp-ping_soil-sensor \
        [--device soil-sensor] [--store data/processed/datasense]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from datasets.datasense.feature_store import FeatureStoreReader  # noqa: E402

VENDOR_BASE = (
    REPO / "data/raw/datasense/dataset/processed_files/all_attack_benign_samples"
)
DEFAULT_VENDOR_CSV = VENDOR_BASE / "attack_data" / "attack_samples_5sec.csv"

REGRESSION_FIXTURE_SESSION = "attack_recon_host-disc-udp-ping_soil-sensor"


def load_our_records(
    store: Path, scenario_id: str, modality: str, device_name: str | None = None
) -> dict[int, dict]:
    reader = FeatureStoreReader(store)
    if modality == "network":
        iterator = reader.iter_network_records(scenario_id)
    else:
        iterator = reader.iter_behavior_records(scenario_id)
    rows = {}
    for row in iterator:
        if device_name is not None and row["device_id"] != device_name:
            continue
        rows[int(row["window_id"])] = row
    return rows


def scan_vendor_rows(vendor_csv: Path, scenario_id: str) -> list[dict]:
    """Chunk-free bounded scan: one row at a time via csv.reader streaming."""
    matched = []
    with open(vendor_csv, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("label_full") == scenario_id:
                matched.append(row)
    return matched


def compare_counts(
    our_rows: dict[int, dict],
    vendor_rows: list[dict],
    device_name: str,
    our_field: str,
    vendor_field: str,
    start_ns: int,
    window_ns: int,
) -> dict:
    from datasets.datasense.windowing import epoch_ns_from_iso

    vendor_by_wid = {}
    for row in vendor_rows:
        if row["device_name"] != device_name:
            continue
        epoch_ns = epoch_ns_from_iso(row["timestamp_start"])
        wid = (epoch_ns - start_ns) // window_ns
        vendor_by_wid[wid] = int(float(row[vendor_field]))
    mismatches = []
    compared = 0
    for wid, ours in sorted(our_rows.items()):
        if wid not in vendor_by_wid:
            continue
        expected = vendor_by_wid[wid]
        actual = ours.get(our_field)
        actual_val = int(actual) if actual is not None else None
        compared += 1
        if actual_val != expected:
            mismatches.append(
                {"window_id": wid, "ours": actual_val, "vendor": expected}
            )
    missing_in_ours = sorted(set(vendor_by_wid) - set(our_rows))
    return {
        "field": our_field,
        "vendor_field": vendor_field,
        "device": device_name,
        "windows_compared": compared,
        "mismatches": mismatches,
        "vendor_windows_missing_in_ours": missing_in_ours,
        "passed": compared > 0 and not mismatches and not missing_in_ours,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="INTERNAL FEATURE VALIDATION")
    parser.add_argument("--session", default=REGRESSION_FIXTURE_SESSION)
    parser.add_argument("--device", help="inventory device name (default: inferred)")
    parser.add_argument("--vendor-csv", type=Path, default=DEFAULT_VENDOR_CSV)
    parser.add_argument("--store", type=Path, default=REPO / "data/processed/datasense")
    args = parser.parse_args(argv)

    print("=== INTERNAL FEATURE VALIDATION ===")
    print(f"our store : {args.store}")
    print(f"vendor csv: {args.vendor_csv}")
    if not args.vendor_csv.is_file():
        print("vendor CSV not available; nothing to validate (pipeline unaffected).")
        return 0

    catalog_mod = __import__(
        "datasets.datasense.catalog", fromlist=["build_catalog"]
    )
    records, _diag = catalog_mod.build_catalog(
        REPO / "data/raw/datasense/dataset/raw_files",
        REPO / "data/raw/datasense/docs/site/attacks.csv",
    )
    session = next((r for r in records if r.scenario_id == args.session), None)
    if session is None:
        print(f"session {args.session} not in raw catalog", file=sys.stderr)
        return 2
    if args.device:
        device = args.device
    else:
        targets = [t for t in session.targets if "whole-network" not in t.lower()]
        device = targets[0] if targets else session.targets[0]

    window_seconds = 5.0
    start_ns = session.session_start_ns
    window_ns = int(window_seconds * 1e9)

    report = {
        "label": "INTERNAL FEATURE VALIDATION",
        "session": args.session,
        "device": device,
        "window_seconds": window_seconds,
        "checks": [],
    }

    our_net = load_our_records(args.store, args.session, "network", device)
    vendor_net = scan_vendor_rows(args.vendor_csv, args.session)
    report["checks"].append(
        compare_counts(
            our_net,
            vendor_net,
            device,
            "packets_all_count",
            "network_packets_all_count",
            start_ns,
            window_ns,
        )
    )

    our_beh = load_our_records(args.store, args.session, "behavior", device)
    if our_beh:
        report["checks"].append(
            compare_counts(
                our_beh,
                vendor_net,
                device,
                "messages_count",
                "log_messages_count",
                start_ns,
                window_ns,
            )
        )

    all_passed = all(check["passed"] for check in report["checks"]) and bool(report["checks"])
    report["overall"] = "PASS" if all_passed else "FAIL"
    print(json.dumps(report, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
