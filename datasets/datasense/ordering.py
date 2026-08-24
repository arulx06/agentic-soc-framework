"""Bounded-memory event-ordering policy shared by all extraction modalities.

Strategy: a maximum-lateness watermark.

The extractor tracks the highest window id observed so far. Windows strictly
below ``max_wid_seen - K`` (where ``K = ceil(max_lateness_ns / window_ns)``)
are finalized and emitted as soon as the watermark advances; their
accumulators are freed immediately, so live memory is proportional to the
lateness horizon, not to session duration.

Any valid event whose window has already been finalized raises
``EventOlderThanWatermarkError`` — a valid event is never silently excluded;
the whole session fails explicitly instead.

``max_event_lateness_ns`` is a SCIENTIFIC setting (it changes which events
could trigger a failure) and is therefore recorded in the extraction state,
NOT part of the operational resource profiles.
"""

from __future__ import annotations

from datasets.datasense.windowing import EventOlderThanWatermarkError


class WatermarkTracker:
    def __init__(self, window_ns: int, max_event_lateness_ns: int):
        if window_ns <= 0:
            raise ValueError("window_ns must be positive")
        if max_event_lateness_ns < 0:
            raise ValueError("max_event_lateness_ns must be non-negative")
        self.window_ns = int(window_ns)
        self.lateness_windows = -(-int(max_event_lateness_ns) // self.window_ns)
        self.max_wid_seen: int | None = None
        self.min_wid_seen: int | None = None
        self.finalized_floor: int | None = None
        self.max_ts_ns: int | None = None
        self.max_observed_lateness_ns = 0

    def ensure_acceptable(self, wid: int, what: str) -> None:
        if self.finalized_floor is not None and wid < self.finalized_floor:
            raise EventOlderThanWatermarkError(
                f"{what} belongs to window {wid}, but all windows < "
                f"{self.finalized_floor} are already finalized "
                f"(max_lateness={self.lateness_windows * self.window_ns} ns). "
                "Failing explicitly rather than losing the event."
            )

    def observe(self, ts_ns: int, wid: int) -> bool:
        """Record an accepted event. Returns True when the watermark advanced
        and the caller should finalize windows below ``finalized_floor``."""
        if self.max_wid_seen is None or wid > self.max_wid_seen:
            self.max_wid_seen = wid
        if self.min_wid_seen is None or wid < self.min_wid_seen:
            self.min_wid_seen = wid
        if self.max_ts_ns is None or ts_ns > self.max_ts_ns:
            self.max_ts_ns = ts_ns
        lateness = self.max_ts_ns - ts_ns
        if lateness > self.max_observed_lateness_ns:
            self.max_observed_lateness_ns = lateness
        advanced = False
        new_floor = self.max_wid_seen - self.lateness_windows
        if self.finalized_floor is None or new_floor > self.finalized_floor:
            advanced = True
            self.finalized_floor = new_floor
        return advanced

    def due_windows(self) -> tuple[int, int] | None:
        """Return (lo, hi) inclusive range of window ids that must be
        finalized now, or None when nothing is due."""
        if self.finalized_floor is None or self.min_wid_seen is None:
            return None
        lo = self.min_wid_seen
        hi = self.finalized_floor - 1
        if hi < lo:
            return None
        self.min_wid_seen = self.finalized_floor
        return lo, hi
