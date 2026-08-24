#!/usr/bin/env python3
"""Read-only behavioural event-accounting reconciliation for a session.

Verifies, from the completed extraction state and the stored behaviour
partition WITHOUT re-extraction:

    parsed_events == contributing_events + unresolved + ignored
                     (+ malformed / missing-timestamp reported separately)

    sum(messages_count for behavior_observed=True rows) == contributing_events

Dense unobserved rows carry null message counts and contribute nothing.
Exits 0 on reconciliation success, 1 on mismatch, 2 when the state is absent.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from datasets.datasense.feature_store import FeatureStoreReader  # noqa: E402


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="benign_whole-network3")
    parser.add_argument("--store", type=Path, default=REPO / "data/processed/datasense")
    args = parser.parse_args(argv)

    state_path = args.store / "extraction_state" / f"{args.session}.json"
    if not state_path.is_file():
        print(f"no extraction state for {args.session}", file=sys.stderr)
        return 2
    state = json.loads(state_path.read_text(encoding="utf-8"))
    accounting = (
        state.get("diagnostics", {}).get("behavior", {}).get("valid_event_accounting")
    )
    if accounting is None:
        print(
            "state predates event-accounting persistence; nothing to reconcile "
            "(historical limitation, not fabricated)",
            file=sys.stderr,
        )
        return 2

    reader = FeatureStoreReader(args.store)
    observed_message_sum = 0
    observed_rows = 0
    dense_unobserved_rows = 0
    for row in reader.iter_behavior_records(args.session):
        if row.get("behavior_observed"):
            observed_rows += 1
            mc = row.get("messages_count")
            if mc is not None:
                observed_message_sum += int(mc)
        else:
            dense_unobserved_rows += 1
            assert row.get("messages_count") is None, "dense row must be null-counted"

    parsed = accounting["parsed_events"]
    contributing = accounting["contributing_events"]
    unresolved = accounting["unresolved_source_events"]
    ignored = accounting["ignored_unsupported_events"]

    identity_ok = parsed == contributing + unresolved + ignored
    sum_ok = observed_message_sum == contributing

    print(json.dumps({
        "session": args.session,
        "parsed_events": parsed,
        "malformed_lines": accounting["malformed_lines"],
        "missing_timestamp_lines": accounting["missing_timestamp_lines"],
        "unresolved_source_events": unresolved,
        "ignored_unsupported_events": ignored,
        "contributing_events": contributing,
        "duplicate_contributions_structural": accounting[
            "duplicate_contributions_structural"
        ],
        "late_events_within_tolerance": accounting["late_events_within_tolerance"],
        "max_observed_lateness_ns": accounting["max_observed_lateness_ns"],
        "behavior_rows_observed": observed_rows,
        "behavior_rows_dense_unobserved": dense_unobserved_rows,
        "sum_messages_count_observed_rows": observed_message_sum,
        "identity_holds": identity_ok,
        "message_sum_matches_contributing": sum_ok,
    }, indent=2))
    return 0 if (identity_ok and sum_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
