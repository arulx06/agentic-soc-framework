"""Resource profiles and replay-speed configuration.

Resource profiles (low / standard / auto) control ONLY operational settings:
read chunk size, worker count, concurrent sessions, queue depth, prefetch,
output buffer size, Parquet row-group size and active-window capacity.

They must never alter feature definitions, window definitions, event order,
scientific output, schema or labels. The same raw input produces logically
equivalent extraction results under every profile.

Replay pacing is intentionally separate: it controls wall-clock pacing of the
event stream only and never changes logical timestamps, window assignment,
feature values or event order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from datasets.datasense.memory_probe import total_and_available_bytes

logger = logging.getLogger(__name__)

GIB = 1024**3


@dataclass(frozen=True)
class OperationalSettings:
    profile_name: str
    read_chunk_bytes: int
    max_workers: int
    max_concurrent_sessions: int
    queue_depth: int
    prefetch_sessions: int
    output_buffer_rows: int
    parquet_row_group_size: int
    active_window_capacity: int

    def with_overrides(self, **overrides) -> "OperationalSettings":
        return replace(self, **overrides)


LOW_PROFILE = OperationalSettings(
    profile_name="low",
    read_chunk_bytes=1 * 1024 * 1024,
    max_workers=1,
    max_concurrent_sessions=1,
    queue_depth=4,
    prefetch_sessions=0,
    output_buffer_rows=2_000,
    parquet_row_group_size=10_000,
    active_window_capacity=8_192,
)

STANDARD_PROFILE = OperationalSettings(
    profile_name="standard",
    read_chunk_bytes=4 * 1024 * 1024,
    max_workers=4,
    max_concurrent_sessions=1,
    queue_depth=16,
    prefetch_sessions=1,
    output_buffer_rows=10_000,
    parquet_row_group_size=50_000,
    active_window_capacity=65_536,
)

PROFILE_NAMES = ("low", "standard", "auto")

AUTO_TOTAL_GIB_THRESHOLD = 20.0
AUTO_AVAILABLE_GIB_THRESHOLD = 8.0


def resolve_profile(name: str = "standard") -> OperationalSettings:
    """Resolve a resource profile name into concrete operational settings.

    ``auto`` inspects available memory and selects conservative settings on
    smaller machines. Only operational knobs are ever produced here.
    """
    if name == "low":
        resolved = LOW_PROFILE
    elif name == "standard":
        resolved = STANDARD_PROFILE
    elif name == "auto":
        try:
            total, available = total_and_available_bytes()
            total_gib = total / GIB
            available_gib = available / GIB
            if total_gib < AUTO_TOTAL_GIB_THRESHOLD or available_gib < AUTO_AVAILABLE_GIB_THRESHOLD:
                resolved = LOW_PROFILE.with_overrides(profile_name="auto(low)")
            else:
                resolved = STANDARD_PROFILE.with_overrides(profile_name="auto(standard)")
            logger.info(
                "auto profile detected total=%.1f GiB available=%.1f GiB -> %s",
                total_gib,
                available_gib,
                resolved.profile_name,
            )
        except RuntimeError as exc:
            logger.warning("memory probe failed (%s); falling back to low", exc)
            resolved = LOW_PROFILE.with_overrides(profile_name="auto(low-fallback)")
    else:
        raise ValueError(f"unknown resource profile {name!r}; expected one of {PROFILE_NAMES}")
    logger.info(
        "resource profile %s resolved: read_chunk=%d B workers=%d concurrent_sessions=%d "
        "queue_depth=%d prefetch=%d output_buffer_rows=%d parquet_row_group=%d "
        "active_windows=%d",
        resolved.profile_name,
        resolved.read_chunk_bytes,
        resolved.max_workers,
        resolved.max_concurrent_sessions,
        resolved.queue_depth,
        resolved.prefetch_sessions,
        resolved.output_buffer_rows,
        resolved.parquet_row_group_size,
        resolved.active_window_capacity,
    )
    return resolved


REPLAY_SPEEDS: dict[str, float | None] = {
    "1x": 1.0,
    "5x": 5.0,
    "10x": 10.0,
    "max": None,
}


def resolve_replay_speed(name: str) -> float | None:
    """Resolve a replay-speed name; None means unpaced ('max')."""
    if name not in REPLAY_SPEEDS:
        raise ValueError(f"unknown replay speed {name!r}; expected one of {sorted(REPLAY_SPEEDS)}")
    return REPLAY_SPEEDS[name]
