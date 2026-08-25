#!/usr/bin/env python3
"""CLI for the DataSense raw ingestion / feature-engineering foundation.

Modes:

  catalog      build and inspect the canonical raw session catalog
  extract      bounded extraction of raw PCAP/JSON into our feature store
  stream-raw   direct raw streaming: same extractor, records to stdout
  read-store   read cached raw-derived output through the same interface

Examples:

  python scripts/datasense_extract.py catalog
  python scripts/datasense_extract.py extract --session attack_recon_host-disc-udp-ping_soil-sensor
  python scripts/datasense_extract.py extract --category recon --limit 3 --profile low
  python scripts/datasense_extract.py stream-raw --session attack_recon_host-disc-udp-ping_soil-sensor
  python scripts/datasense_extract.py read-store --session attack_recon_host-disc-udp-ping_soil-sensor
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from datasets.datasense.catalog import build_catalog  # noqa: E402
from datasets.datasense.devices import DeviceInventory  # noqa: E402
from datasets.datasense.extraction import ExtractionEngine  # noqa: E402
from datasets.datasense.feature_store import (
    FeatureStoreReader,
    write_store_metadata,
)  # noqa: E402
from datasets.datasense.memory_probe import current_and_peak_rss_bytes  # noqa: E402
from datasets.datasense.profiles import resolve_profile  # noqa: E402
from datasets.datasense.replay import paced  # noqa: E402
from datasets.datasense.versions import (  # noqa: E402
    BEHAVIOR_FEATURE_SCHEMA_VERSION,
    EXTRACTOR_VERSION,
    NETWORK_FEATURE_SCHEMA_VERSION,
)

RAW_ROOT = REPO / "data/raw/datasense/dataset/raw_files"
ATTACKS_CSV = REPO / "data/raw/datasense/docs/site/attacks.csv"
DEVICES_CSV = REPO / "data/raw/datasense/docs/site/devices.csv"
DEFAULT_STORE = REPO / "data/processed/datasense"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("datasense_extract")


def _load_context():
    catalog_records, diagnostics = build_catalog(RAW_ROOT, ATTACKS_CSV)
    inventory = DeviceInventory.load(DEVICES_CSV)
    by_id = {rec.scenario_id: rec for rec in catalog_records}
    return catalog_records, diagnostics, inventory, by_id


def cmd_catalog(args) -> int:
    records, diagnostics, _, _ = _load_context()
    selected = records if not args.limit else records[: args.limit]
    payload = {
        "diagnostics": diagnostics,
        "versions": {
            "extractor": EXTRACTOR_VERSION,
            "network_schema": NETWORK_FEATURE_SCHEMA_VERSION,
            "behavior_schema": BEHAVIOR_FEATURE_SCHEMA_VERSION,
        },
        "sessions": [
            {
                "scenario_id": r.scenario_id,
                "is_attack": r.is_attack,
                "attack_category": r.attack_category,
                "targets": r.targets,
                "whole_network_target": r.whole_network_target,
                "start": r.session_start_iso,
                "end": r.session_end_iso,
                "pcap_bytes": (
                    Path(r.raw_pcap_path).stat().st_size if r.raw_pcap_path else None
                ),
            }
            for r in selected
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0


def _select_sessions(args, by_id: dict) -> list:
    if args.session:
        wanted = [s.strip() for s in args.session.split(",") if s.strip()]
        missing = [w for w in wanted if w not in by_id]
        if missing:
            raise SystemExit(f"unknown session id(s): {missing}")
        return [by_id[w] for w in wanted]
    records, diagnostics, _, _ = _load_context()
    candidates = records
    if args.category:
        candidates = [r for r in candidates if r.attack_category == args.category]
    if args.skip_large_bytes:
        def small(r):
            size = Path(r.raw_pcap_path).stat().st_size if r.raw_pcap_path else 0
            json_size = Path(r.raw_json_path).stat().st_size if r.raw_json_path else 0
            return max(size, json_size) <= args.skip_large_bytes
        candidates = [r for r in candidates if small(r)]
    if args.limit:
        candidates = candidates[: args.limit]
    return candidates


def cmd_extract(args) -> int:
    records, diagnostics, inventory, by_id = _load_context()
    sessions = _select_sessions(args, by_id)
    if not sessions:
        print("no sessions selected; nothing to do", file=sys.stderr)
        return 1
    write_store_metadata(args.store, records, diagnostics, inventory)
    settings = resolve_profile(args.profile)
    engine = ExtractionEngine(
        store_root=args.store,
        inventory=inventory,
        settings=settings,
        window_seconds=args.window_seconds,
        clock_tolerance_ns=int(args.clock_tolerance_ms * 1_000_000),
        max_event_lateness_ns=int(args.max_lateness_seconds * 1_000_000_000),
        force_regenerate=args.force_regenerate,
    )
    results = []
    for session in sessions:
        logger.info(
            "extracting %s (%s)", session.scenario_id, session.data_type
        )
        state = engine.run_session(session)
        results.append(
            {
                "scenario_id": session.scenario_id,
                "status": state.get("status"),
                "network_rows": state.get("network_record_count"),
                "behavior_rows": state.get("behavior_record_count"),
            }
        )
    rss_now, rss_peak = current_and_peak_rss_bytes()
    print(
        json.dumps(
            {"results": results, "peak_rss_mb": round(rss_peak / 1e6, 1), "profile": settings.profile_name},
            indent=2,
        )
    )
    return 0


def cmd_stream_raw(args) -> int:
    records, _, inventory, by_id = _load_context()
    sessions = _select_sessions(args, by_id)
    if len(sessions) != 1:
        raise SystemExit("stream-raw requires exactly one --session")
    session = sessions[0]
    modality_filter = args.modality if args.modality in ("network", "behavior", "communication") else None

    from datasets.datasense.extraction import (
        iter_behavior_rows,
        iter_pcap_feature_rows,
    )

    def source() -> Iterator[dict]:
        if modality_filter in (None, "network", "communication"):
            for tag, row in iter_pcap_feature_rows(
                session,
                inventory,
                args.window_seconds,
                int(args.clock_tolerance_ms * 1_000_000),
                int(args.max_lateness_seconds * 1_000_000_000),
                active_window_capacity=65536,
                read_chunk_bytes=4 * 1024 * 1024,
            ):
                if modality_filter is None or tag == modality_filter:
                    yield row
        if modality_filter in (None, "behavior"):
            yield from iter_behavior_rows(
                session,
                inventory,
                args.window_seconds,
                int(args.clock_tolerance_ms * 1_000_000),
                int(args.max_lateness_seconds * 1_000_000_000),
                active_window_capacity=65536,
            )

    rows = source()
    if args.replay_speed != "max":
        rows = paced(rows, speed_name=args.replay_speed, ts_key="window_start_utc")
    count = 0
    for row in rows:
        print(json.dumps(row, default=str))
        count += 1
    print(f"# streamed {count} records", file=sys.stderr)
    return 0


def cmd_read_store(args) -> int:
    reader = FeatureStoreReader(args.store)
    state = reader.check_compatible(args.session)
    count = 0

    modalities = (
        ("network", "behavior", "communication")
        if args.modality is None
        else (args.modality,)
    )

    def source() -> Iterator[dict]:
        for modality in modalities:
            yield from reader.iter_records(args.session, modality, validate=False)

    rows = source()
    if args.replay_speed != "max":
        rows = paced(rows, speed_name=args.replay_speed, ts_key="window_start_utc")
    for row in rows:
        print(json.dumps(row, default=str))
        count += 1
    print(
        f"# read {count} records for {args.session} "
        f"(status={state.get('status')}, window={state.get('window_seconds')}s)",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help="feature-store root")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cat = sub.add_parser("catalog", help="print raw session catalog summary")
    p_cat.add_argument("--limit", type=int, default=0)

    p_ext = sub.add_parser("extract", help="bounded extraction into the feature store")
    p_ext.add_argument("--session", help="comma-separated scenario ids")
    p_ext.add_argument("--category", help="attack category filter")
    p_ext.add_argument("--limit", type=int)
    p_ext.add_argument("--skip-large-bytes", type=int, help="only sessions whose largest file is below this size")
    p_ext.add_argument("--profile", choices=("low", "standard", "auto"), default="standard")
    p_ext.add_argument("--window-seconds", type=float, default=5.0)
    p_ext.add_argument(
        "--clock-tolerance-ms",
        type=float,
        default=10.0,
        help="pre-start clock-alignment tolerance (audit-grounded default 10 ms); "
        "earlier events keep negative window ids",
    )
    p_ext.add_argument(
        "--max-lateness-seconds",
        type=float,
        default=60.0,
        help="maximum event lateness before finalization; older events fail the session",
    )
    p_ext.add_argument("--force-regenerate", action="store_true")

    p_raw = sub.add_parser("stream-raw", help="direct raw streaming via the same extractor")
    p_raw.add_argument("--session", required=True)
    p_raw.add_argument("--modality", choices=("network", "behavior", "communication"))
    p_raw.add_argument("--window-seconds", type=float, default=5.0)
    p_raw.add_argument("--clock-tolerance-ms", type=float, default=10.0)
    p_raw.add_argument("--max-lateness-seconds", type=float, default=60.0)
    p_raw.add_argument("--replay-speed", choices=("1x", "5x", "10x", "max"), default="max")

    p_read = sub.add_parser("read-store", help="read cached raw-derived features")
    p_read.add_argument("--session", required=True)
    p_read.add_argument("--modality", choices=("network", "behavior", "communication"))
    p_read.add_argument("--replay-speed", choices=("1x", "5x", "10x", "max"), default="max")

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "catalog": cmd_catalog,
        "extract": cmd_extract,
        "stream-raw": cmd_stream_raw,
        "read-store": cmd_read_store,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
