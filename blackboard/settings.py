"""Operational settings and default runtime locations for the Blackboard.

All caps are configurable so experiments can tighten or loosen bounds;
defaults favour a bounded local research deployment.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Default physical home of per-replica SQLite stores. Generated runtime
#: databases live here (gitignored) — never under data/raw/.
RUNTIME_BLACKBOARD_ROOT = REPO_ROOT / "runtime" / "blackboard"

DEFAULT_REPLICA_IDS: tuple[str, ...] = ("replica_a", "replica_b", "replica_c")


def utc_now_str() -> str:
    """Second-resolution UTC wall-clock tag (operational use only — it never
    participates in logical record hashes)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(frozen=True)
class BlackboardSettings:
    """Bounded-memory and lifecycle knobs for the Blackboard core."""

    #: Reject records whose canonical serialization exceeds this many bytes.
    max_record_canonical_bytes: int = 262_144

    #: Ring-buffer cap for recent global write operations kept in RAM.
    recent_operations_limit: int = 256

    #: Ring-buffer cap for recent rejections kept in RAM.
    recent_rejections_limit: int = 64

    #: Cap on retained latency samples per measured series.
    latency_samples_limit: int = 512

    #: A prepared-but-never-committed proposal older than this many seconds
    #: loses its seat and may be replaced by a conflicting proposal.
    pending_lease_seconds: float = 300.0

    #: Compatible prepared acknowledgements required to commit (of 3).
    quorum_size: int = 2

    #: Explicit research scan bound for merged committed-view reads
    #: (listing/snapshot). Scanning stops at this many rows per replica;
    #: views then carry an explicit ``truncated`` indicator instead of
    #: silently pretending completeness.
    committed_scan_max_rows: int = 10_000

    #: Rows fetched per storage chunk while scanning a replica's committed
    #: table (bounded-memory iteration; never a whole-table load).
    committed_scan_chunk_size: int = 1_000

    def __post_init__(self) -> None:
        if self.max_record_canonical_bytes < 1:
            raise ValueError("max_record_canonical_bytes must be >= 1")
        if self.recent_operations_limit < 1:
            raise ValueError("recent_operations_limit must be >= 1")
        if self.recent_rejections_limit < 1:
            raise ValueError("recent_rejections_limit must be >= 1")
        if self.latency_samples_limit < 1:
            raise ValueError("latency_samples_limit must be >= 1")
        if self.pending_lease_seconds <= 0:
            raise ValueError("pending_lease_seconds must be > 0")
        if self.quorum_size < 1:
            raise ValueError("quorum_size must be >= 1")
        if self.committed_scan_max_rows < 1:
            raise ValueError("committed_scan_max_rows must be >= 1")
        if self.committed_scan_chunk_size < 1:
            raise ValueError("committed_scan_chunk_size must be >= 1")
