"""Compatibility verification: current (optimized) direct-raw extraction vs
the pre-existing cached feature-store partitions for BOTH attack sessions.

Checks network / behaviour / communication records for identical
observation masks, window ids/timestamps, null semantics, feature values and
directed communication associations. Exits non-zero on any difference.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from datasets.datasense.catalog import build_catalog  # noqa: E402
from datasets.datasense.devices import DeviceInventory  # noqa: E402
from datasets.datasense.extraction import (  # noqa: E402
    iter_behavior_rows,
    iter_pcap_feature_rows,
)
from datasets.datasense.feature_store import FeatureStoreReader  # noqa: E402

SESSIONS = [
    "attack_recon_host-disc-udp-ping_soil-sensor",
    "attack_recon_ping-sweep_whole-network",
]


def norm_key(row, modality):
    if modality == "communication":
        return (row["window_id"], row["src_entity_id"], row["dst_entity_id"])
    return (row["window_id"], row["device_id"])


def main() -> int:
    inventory = DeviceInventory.load(REPO / "data/raw/datasense/docs/site/devices.csv")
    catalog, _ = build_catalog(
        REPO / "data/raw/datasense/dataset/raw_files",
        REPO / "data/raw/datasense/docs/site/attacks.csv",
    )
    by_id = {r.scenario_id: r for r in catalog}
    reader = FeatureStoreReader(REPO / "data/processed/datasense")
    all_ok = True

    for sid in SESSIONS:
        session = by_id[sid]
        collect = {}
        fused = iter_pcap_feature_rows(
            session,
            inventory,
            window_seconds=5.0,
            clock_tolerance_ns=10_000_000,
            max_event_lateness_ns=60 * 10**9,
            active_window_capacity=65536,
            read_chunk_bytes=1 << 20,
            collect=collect,
        )
        behavior = iter_behavior_rows(
            session,
            inventory,
            window_seconds=5.0,
            clock_tolerance_ns=10_000_000,
            max_event_lateness_ns=60 * 10**9,
            active_window_capacity=65536,
        )

        direct = {"network": {}, "communication": {}}
        for tag, row in fused:
            direct[tag][norm_key(row, tag)] = row
        direct["behavior"] = {
            norm_key(r, "behavior"): r for r in behavior
        }

        results = {}
        for modality in ("network", "behavior", "communication"):
            stored_iter = getattr(reader, f"iter_{modality}_records")(sid)
            stored = {norm_key(r, modality): r for r in stored_iter}
            same_keys = set(stored) == set(direct[modality])
            diff_vals = 0
            for k, stored_row in stored.items():
                if not same_keys:
                    break
                if stored_row != direct[modality][k]:
                    diff_vals += 1
            results[modality] = {
                "rows": len(stored),
                "keys_identical": same_keys,
                "value_diffs": diff_vals,
            }
            all_ok &= same_keys and diff_vals == 0

        sorter = collect.get("behavior_sorter_diagnostics", {})
        print(
            json.dumps(
                {
                    "session": sid,
                    **results,
                    "behavior_sorter": sorter,
                }
            )
        )

    print("COMPATIBLE" if all_ok else "INCOMPATIBLE")
    return 0 if all_ok else 1


def _json_default(o):
    return str(o)


import json  # noqa: E402

print_orig = json.dumps


if __name__ == "__main__":
    json.dumps = lambda o, **kw: print_orig(o, default=_json_default)  # type: ignore
    raise SystemExit(main())
