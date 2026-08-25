#!/usr/bin/env python3
"""Read-only audit of the DataSense/CIC IIoT 2025 processed release.

Streams the processed CSVs in chunks and reports row counts, label semantics,
device coverage, sparsity, temporal alignment and duplicate statistics.
Writes JSON results to stdout (or a file given as argv[1]).

Usage: python scripts/datasense_audit.py [out.json]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "data/raw/datasense/dataset/processed_files/all_attack_benign_samples"
ATTACK_DIR = BASE / "attack_data"
BENIGN_DIR = BASE / "benign_data"
DEVICES_CSV = REPO / "data/raw/datasense/docs/site/devices.csv"
ATTACKS_CSV = REPO / "data/raw/datasense/docs/site/attacks.csv"

CHUNK = 50_000

LIST_COLS = {
    "log_data-types",
    "network_ips_all", "network_ips_dst", "network_ips_src",
    "network_macs_all", "network_macs_dst", "network_macs_src",
    "network_ports_all", "network_ports_dst", "network_ports_src",
    "network_protocols_all", "network_protocols_dst", "network_protocols_src",
}
ID_COLS = ["device_name", "device_mac"]
LABEL_COLS = ["label_full", "label1", "label2", "label3", "label4"]
TIME_COLS = ["timestamp", "timestamp_start", "timestamp_end"]

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def audit_file(path: Path, dupes: bool = True) -> dict:
    dev_counts = Counter()
    mac_by_dev = defaultdict(set)
    dev_by_mac = defaultdict(set)
    l1 = Counter()
    l2 = Counter()
    l3 = set()
    l4 = set()
    lfull = set()
    l4_matches = 0
    l4_total = 0
    benign_labels_uniform = True
    n_rows = 0
    n_net_zero = 0
    n_log_zero = 0
    n_both_zero = 0
    n_empty_lists_all = 0
    n_missing = 0
    n_bad_ts_format = 0
    dur_counter = Counter()
    t_min, t_max = None, None
    unsorted_devices = set()
    last_ts_by_dev = {}
    row_hashes = Counter()
    n_dup_rows = 0
    sessions = defaultdict(lambda: {"devices": set(), "n": 0,
                                    "t_min": None, "t_max": None})
    per_dev_l1 = defaultdict(Counter)

    reader = pd.read_csv(path, chunksize=CHUNK, dtype=str, keep_default_na=False)
    header = None
    for chunk in reader:
        if header is None:
            header = list(chunk.columns)
        n_rows += len(chunk)
        n_missing += int((chunk == "").sum().sum())

        # identity / labels
        dev_counts.update(chunk["device_name"])
        for d, m in zip(chunk["device_name"], chunk["device_mac"]):
            mac_by_dev[d].add(m)
            dev_by_mac[m].add(d)
        l1.update(chunk["label1"])
        l2.update(chunk["label2"])
        l3.update(chunk["label3"].unique())
        l4.update(chunk["label4"].unique())
        lfull.update(chunk["label_full"].unique())
        m4 = chunk["label4"] == (chunk["label2"] + "_" + chunk["label3"])
        l4_matches += int(m4.sum())
        l4_total += len(chunk)
        ben = chunk["label1"] == "benign"
        if ben.any():
            uniform = (chunk.loc[ben, ["label2", "label3", "label4"]] == "benign").all().all()
            benign_labels_uniform &= bool(uniform)

        per_dev = chunk.groupby("device_name")["label1"].value_counts()
        for (d, lab), c in per_dev.items():
            per_dev_l1[d][lab] += int(c)

        # sparsity
        net_num = [c for c in header if c.startswith("network_") and c not in LIST_COLS]
        log_num = [c for c in header if c.startswith("log_") and c not in LIST_COLS]
        net = chunk[net_num].apply(pd.to_numeric, errors="coerce")
        log = chunk[log_num].apply(pd.to_numeric, errors="coerce")
        net_zero = (net.fillna(0) == 0).all(axis=1)
        log_zero = (log.fillna(0) == 0).all(axis=1)
        lists_empty = chunk[list(LIST_COLS)].apply(
            lambda s: s.str.strip().isin(["[]", ""])).all(axis=1)
        n_net_zero += int(net_zero.sum())
        n_log_zero += int(log_zero.sum())
        n_both_zero += int((net_zero & log_zero).sum())
        n_empty_lists_all += int(lists_empty.sum())

        # time
        ok_start = chunk["timestamp_start"].str.match(TS_RE.pattern)
        ok_end = chunk["timestamp_end"].str.match(TS_RE.pattern)
        n_bad_ts_format += int((~(ok_start & ok_end)).sum())
        ts_s = pd.to_datetime(chunk["timestamp_start"], format="%Y-%m-%dT%H:%M:%S.%fZ", utc=True)
        ts_e = pd.to_datetime(chunk["timestamp_end"], format="%Y-%m-%dT%H:%M:%S.%fZ", utc=True)
        durs = ((ts_e - ts_s).dt.total_seconds()).round(3)
        dur_counter.update(durs.value_counts().to_dict())
        lo, hi = ts_s.min(), ts_s.max()
        t_min = lo if t_min is None else min(t_min, lo)
        t_max = hi if t_max is None else max(t_max, hi)

        # per-device chronological order
        for d, grp in chunk.assign(_ts=ts_s).groupby("device_name"):
            g = grp.sort_values("_ts")
            prev = last_ts_by_dev.get(d)
            first = g["_ts"].iloc[0]
            if prev is not None and first < prev:
                unsorted_devices.add(d)
            last_ts_by_dev[d] = g["_ts"].iloc[-1]

        # sessions (label_full = capture/session id)
        for lf, grp in chunk.groupby("label_full"):
            s = sessions[lf]
            s["devices"].update(grp["device_name"].unique())
            s["n"] += len(grp)
            gmin = ts_s[grp.index].min()
            gmax = ts_e[grp.index].max()
            s["t_min"] = gmin if s["t_min"] is None else min(s["t_min"], gmin)
            s["t_max"] = gmax if s["t_max"] is None else max(s["t_max"], gmax)

        if dupes:
            for row in chunk.itertuples(index=False, name=None):
                row_hashes[hashlib.md5("\x1f".join(row).encode()).hexdigest()] += 1

    if dupes:
        n_dup_rows = sum(c - 1 for c in row_hashes.values() if c > 1)

    return {
        "file": path.name,
        "size_mb": round(path.stat().st_size / 1e6, 1),
        "rows": n_rows,
        "missing_cells": n_missing,
        "duplicate_rows": n_dup_rows,
        "devices": {d: dict(c) for d, c in sorted(per_dev_l1.items())},
        "device_names": sorted(dev_counts),
        "mac_consistent_one_to_one": all(len(v) == 1 for v in mac_by_dev.values())
        and all(len(v) == 1 for v in dev_by_mac.values()),
        "dev_to_multi_mac": {d: sorted(v) for d, v in mac_by_dev.items() if len(v) > 1},
        "labels": {
            "label1": dict(l1),
            "label2": dict(l2),
            "label3_unique_count": len(l3),
            "label4_unique_count": len(l4),
            "label_full_unique_count": len(lfull),
            "label4_equals_cat_name_frac": round(l4_matches / max(l4_total, 1), 6),
            "benign_rows_have_all_benign_labels": benign_labels_uniform,
            "label3_samples": sorted(l3)[:400],
        },
        "sparsity": {
            "all_network_numeric_zero_pct": round(100 * n_net_zero / n_rows, 2),
            "all_log_numeric_zero_pct": round(100 * n_log_zero / n_rows, 2),
            "both_groups_zero_pct": round(100 * n_both_zero / n_rows, 2),
            "all_list_fields_empty_pct": round(100 * n_empty_lists_all / n_rows, 2),
            "both_zero_row_count": n_both_zero,
        },
        "time": {
            "bad_timestamp_rows": n_bad_ts_format,
            "window_duration_seconds_top": dict(sorted(
                dur_counter.items(), key=lambda kv: -kv[1])[:5]),
            "global_start_min": str(t_min),
            "global_end_max": str(t_max),
            "devices_with_non_monotonic_windows": sorted(unsorted_devices),
        },
        "sessions": {
            "count": len(sessions),
            "multi_device_sessions": sum(1 for s in sessions.values() if len(s["devices"]) > 1),
            "example": {
                lf: {"devices": sorted(s["devices"]), "rows": s["n"],
                     "start": str(s["t_min"]), "end": str(s["t_max"])}
                for lf, s in list(sorted(sessions.items()))[:3]
            },
        },
    }


def main() -> None:
    out = {}
    out["devices_csv"] = []
    devs = pd.read_csv(DEVICES_CSV, dtype=str)
    out["devices_csv_n"] = len(devs)
    out["devices_csv_roles"] = devs.groupby("role")["device_name"].apply(list).to_dict()

    att_inv = pd.read_csv(ATTACKS_CSV, dtype=str)
    out["attacks_inventory"] = {
        "rows": len(att_inv),
        "categories": att_inv["category"].value_counts().to_dict(),
        "unique_attack_names": int(att_inv.loc[att_inv.data_type == "attack",
                                               "attack_name"].nunique()),
        "attack_names_by_category": {
            c: sorted(g["attack_name"].unique())
            for c, g in att_inv.loc[att_inv.data_type == "attack"].groupby("category")
        },
        "benign_sessions": att_inv.loc[att_inv.data_type == "benign",
                                       ["filename", "doc_count"]].to_dict("records"),
        "targets_unique": sorted(att_inv.loc[att_inv.data_type == "attack",
                                             "attack_target"].unique()),
    }

    for sec in ("1sec", "5sec", "10sec"):
        out[f"attack_{sec}"] = audit_file(ATTACK_DIR / f"attack_samples_{sec}.csv")
        out[f"benign_{sec}"] = audit_file(BENIGN_DIR / f"benign_samples_{sec}.csv")

    # cross-side device set comparison (1 sec)
    a = set(out["attack_1sec"]["device_names"])
    b = set(out["benign_1sec"]["device_names"])
    inv = set(devs["device_name"]) | {"iot-cloud"}
    out["device_set_comparison"] = {
        "attack_only": sorted(a - b),
        "benign_only": sorted(b - a),
        "in_inventory_not_in_data": sorted(inv - a - b),
        "in_data_not_in_inventory": sorted((a | b) - inv),
    }

    # window alignment: fraction of benign windows shared by >=2 devices
    path = BENIGN_DIR / "benign_samples_1sec.csv"
    win_devs = defaultdict(set)
    for chunk in pd.read_csv(path, usecols=["timestamp", "device_name"],
                             chunksize=CHUNK, dtype=str):
        for w, d in zip(chunk["timestamp"], chunk["device_name"]):
            win_devs[w].add(d)
    shared = sum(1 for v in win_devs.values() if len(v) >= 2)
    out["benign_window_alignment"] = {
        "distinct_windows": len(win_devs),
        "windows_with_multiple_devices": shared,
        "max_devices_per_window": max(len(v) for v in win_devs.values()),
    }

    txt = json.dumps(out, indent=1, default=str)
    dest = sys.argv[1] if len(sys.argv) > 1 else None
    if dest:
        Path(dest).write_text(txt)
    else:
        print(txt)


if __name__ == "__main__":
    main()
