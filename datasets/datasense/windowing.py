"""Shared deterministic temporal windowing for network and telemetry events.

Both the PCAP and the MQTT/JSON extraction paths MUST use exactly this grid:

    window_id = floor((event_timestamp_ns - scenario_start_ns) / window_ns)

The scenario start is authoritative metadata from ``attacks.csv`` and is
validated against raw event timestamps during extraction. All arithmetic is
integer nanoseconds so results are deterministic across platforms.

This project-owned absolute-grid alignment intentionally does NOT reproduce
the vendor release's per-device window anchoring (see docs/datasense_audit.md
section 9): every device in a scenario shares one grid here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

NS_PER_SECOND = 1_000_000_000

from datasets.datasense.versions import (  # noqa: E402
    DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS,
)

DISPOSITION_IN_GRID = "in_grid"
DISPOSITION_PRESTART_SNAPPED = "prestart_snapped"
DISPOSITION_PRESTART_NEGATIVE = "prestart_negative"


class EventOlderThanWatermarkError(RuntimeError):
    """Raised when an event belongs to a window that has already been
    finalized. No valid event may be silently excluded after finalization;
    the extraction fails explicitly instead."""


def epoch_ns_from_iso(value: str) -> int:
    """Parse an ISO-8601 UTC timestamp string into epoch nanoseconds.

    Accepts trailing 'Z' offsets and arbitrary fractional-second digits
    (e.g. millisecond telemetry stamps and microsecond vendor stamps).
    """
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = dt - epoch
    return (
        delta.days * 86_400 * NS_PER_SECOND
        + delta.seconds * NS_PER_SECOND
        + delta.microseconds * 1_000
    )


def iso_utc_from_ns(ts_ns: int) -> str:
    """Format epoch nanoseconds as an ISO-8601 UTC string (millisecond trim)."""
    seconds, remainder = divmod(int(ts_ns), NS_PER_SECOND)
    dt = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        seconds=seconds, microseconds=remainder // 1000
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class WindowGrid:
    """Integer-nanosecond window grid anchored at a scenario start."""

    scenario_start_ns: int
    window_seconds: float = 5.0

    def __post_init__(self):
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

    @property
    def window_ns(self) -> int:
        return int(round(self.window_seconds * NS_PER_SECOND))

    def window_id(self, ts_ns: int) -> int:
        return (int(ts_ns) - self.scenario_start_ns) // self.window_ns

    def assign(
        self, ts_ns: int, clock_tolerance_ns: int = DEFAULT_CLOCK_ALIGNMENT_TOLERANCE_NS
    ) -> tuple[int, str]:
        """Assign an event timestamp to a window with an explicit pre-start
        policy.

        Policy (identical for network and telemetry):

        * events at or after the scenario start map normally
          (disposition ``in_grid``);
        * events before the start by no more than ``clock_tolerance_ns``
          snap into window 0 (``prestart_snapped``) and MUST be counted by
          the caller together with their maximum displacement;
        * earlier events keep a deterministic negative window id
          (``prestart_negative``); they are never silently clamped.

        Window timestamps remain deterministic in all branches.
        """
        raw_wid = self.window_id(ts_ns)
        if raw_wid >= 0:
            return raw_wid, DISPOSITION_IN_GRID
        displacement = self.scenario_start_ns - int(ts_ns)
        if 0 <= displacement <= int(clock_tolerance_ns):
            return 0, DISPOSITION_PRESTART_SNAPPED
        return raw_wid, DISPOSITION_PRESTART_NEGATIVE

    def window_bounds(self, window_id: int) -> tuple[int, int]:
        start = self.scenario_start_ns + window_id * self.window_ns
        return start, start + self.window_ns

    def window_start_utc(self, window_id: int) -> str:
        return iso_utc_from_ns(self.window_bounds(window_id)[0])

    def window_end_utc(self, window_id: int) -> str:
        return iso_utc_from_ns(self.window_bounds(window_id)[1])
