"""Replay-speed pacing at the raw event / feature-stream boundary.

Replay speed controls ONLY wall-clock pacing of an event stream; it never
changes logical timestamps, window assignment, feature values or event
order. Resource profiles control memory and concurrency; the two axes are
independent by construction.

Speeds: 1x, 5x, 10x and 'max' (unpaced). A sleeper callable is injectable so
tests can verify semantics without real sleeping.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, Iterator

from datasets.datasense.profiles import resolve_replay_speed


class ReplayPacer:
    """Paces consumption of a timestamped record stream.

    ``speed=None`` (max) disables pacing entirely. ``sleeper`` defaults to
    ``time.sleep`` and is injectable for deterministic tests.
    """

    def __init__(
        self,
        speed_name: str = "max",
        ts_key: str = "_replay_ts_ns",
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.speed = resolve_replay_speed(speed_name)
        self.speed_name = speed_name
        self.ts_key = ts_key
        self.clock = clock
        self.sleeper = sleeper
        self._start_wall: float | None = None
        self._first_ts_ns: int | None = None

    def reset(self) -> None:
        self._start_wall = None
        self._first_ts_ns = None

    def wait_for(self, ts_ns: int | float) -> None:
        if self.speed is None:
            return
        ts_ns = int(ts_ns)
        now = self.clock()
        if self._start_wall is None or self._first_ts_ns is None:
            self._start_wall = now
            self._first_ts_ns = ts_ns
            return
        logical_elapsed = (ts_ns - self._first_ts_ns) / 1e9
        target_wall = self._start_wall + logical_elapsed / self.speed
        delay = target_wall - self.clock()
        if delay > 0:
            self.sleeper(delay)


def paced(
    records: Iterable[dict],
    speed_name: str = "max",
    ts_key: str = "window_start_utc",
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> Iterator[dict]:
    """Yield feature records unchanged, pacing wall-clock consumption only.

    Records carry their logical time in ``ts_key`` (an ISO UTC field such as
    ``window_start_utc``) or in a precomputed ``_replay_ts_ns`` integer key.
    The yielded objects are identical to the inputs; nothing but timing is
    affected.
    """
    pacer = ReplayPacer(speed_name, ts_key="_replay_ts_ns", clock=clock, sleeper=sleeper)

    def to_epoch_ns(record: dict):
        special = record.get("_replay_ts_ns")
        if special is not None:
            return int(special)
        from datasets.datasense.windowing import epoch_ns_from_iso

        value = record.get(ts_key)
        if value is None:
            return None
        return epoch_ns_from_iso(str(value))

    for record in records:
        ts = to_epoch_ns(record)
        if ts is not None:
            pacer.wait_for(ts)
        yield record
