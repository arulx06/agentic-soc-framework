"""Scientific-output projection for direct-raw vs feature-store comparison.

Defines exactly which fields are scientific state (MUST match between modes)
and which are non-scientific run variants (allowed to differ). The closure
rule: risk values, replay step/window counters, SREP fields and finding data
are NEVER stripped to obtain equality.
"""

from __future__ import annotations

# Top-level replay summary fields that are display/provenance only.
NON_SCIENTIFIC_REPLAY_FIELDS = {
    "source_mode",       # display label ('feature_store' vs 'direct_raw')
    "replay_speed",      # display label ('max', '1x', ...)
}

# Direct-raw-only diagnostic blocks (physical extraction instrumentation).
NON_SCIENTIFIC_REPLAY_FIELDS |= {"extraction_diagnostics"}

# SREP timestamp is wall-clock provenance.
NON_SCIENTIFIC_SREP_FIELDS = {"generated_at"}

# Ordering diagnostics describe PHYSICAL arrival order, which legitimately
# differs between a recorded store partition stream and a live raw stream.
# They are compared SEPARATELY by the caller, never stripped silently.
ORDERING_DIAGNOSTICS_FIELD = "ordering_diagnostics"


def scientific_projection(replay_summary: dict, srep_report: dict) -> dict:
    """Return the comparable scientific projection of one replay result.

    Kept fields include (non-exhaustive): windows, window_id_range,
    findings_emitted (+ behaviour_absence), findings_accepted, gateway_stats,
    communication_edges/nodes, history_length, abm_final_digest (full per-node
    network/behavior/propagated/systemic risks, masks, compromised flags,
    defended_blast_radius), SREP mode/mode_note/parameters/top risky nodes/
    device_risk_nodes (incl. every risk field)/last_window_id/steps_replayed.
    """
    replay = {
        k: v
        for k, v in replay_summary.items()
        if k not in NON_SCIENTIFIC_REPLAY_FIELDS
        and k != ORDERING_DIAGNOSTICS_FIELD
    }
    srep = {
        k: v
        for k, v in srep_report.items()
        if k not in NON_SCIENTIFIC_SREP_FIELDS
    }
    return {"replay": replay, "srep": srep}


def ordering_projection(ordering_diagnostics: dict) -> dict:
    """Operational-only projection used for the separate diagnostics check."""
    out = {}
    for tag, d in sorted(ordering_diagnostics.items()):
        out[tag] = {
            "rows": d["rows"],
            "inversions": d["inversions"],
            "max_inversion_windows": d["max_inversion_windows"],
            "chunks_written": d["chunks_written"],
            "merge_passes": d["merge_passes"],
            "merge_fan_in": d["merge_fan_in"],
        }
    return out


def assert_scientific_equivalence(a: dict, b: dict) -> None:
    pa = scientific_projection(a["replay"], a["srep"])
    pb = scientific_projection(b["replay"], b["srep"])
    if pa != pb:
        diffs = []

        def walk(x, y, path):
            if isinstance(x, dict) and isinstance(y, dict):
                for k in sorted(set(x) | set(y)):
                    walk(x.get(k), y.get(k), f"{path}/{k}")
            elif x != y:
                diffs.append((path, x, y))

        walk(pa, pb, "")
        raise AssertionError(
            "scientific projections differ:\n"
            + "\n".join(f"  {p}: {x!r} != {y!r}" for p, x, y in diffs[:20])
        )
