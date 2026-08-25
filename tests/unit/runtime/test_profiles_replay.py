import pytest

from datasets.datasense.replay import ReplayPacer, paced
from datasets.datasense.profiles import REPLAY_SPEEDS, resolve_replay_speed


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _records():
    return [
        {"window_id": 0, "window_start_utc": "2025-01-15T21:25:10.307Z", "packets_all_count": 1},
        {"window_id": 1, "window_start_utc": "2025-01-15T21:25:15.307Z", "packets_all_count": 2},
        {"window_id": 2, "window_start_utc": "2025-01-15T21:25:20.307Z", "packets_all_count": 3},
    ]


def test_speed_table_and_resolution():
    assert set(REPLAY_SPEEDS) == {"1x", "5x", "10x", "max"}
    assert resolve_replay_speed("1x") == 1.0
    assert resolve_replay_speed("10x") == 10.0
    assert resolve_replay_speed("max") is None
    with pytest.raises(ValueError):
        resolve_replay_speed("100x")


def test_max_speed_yields_identical_records_without_sleeping():
    clock = FakeClock()
    out = list(paced(_records(), "max", clock=clock.time, sleeper=clock.sleep))
    assert out == _records()
    assert clock.sleeps == []


def test_paced_records_unchanged_in_order_and_values():
    clock = FakeClock()
    source = _records()
    snapshot = [dict(r) for r in source]
    out = list(paced(source, "5x", clock=clock.time, sleeper=clock.sleep))
    assert out == snapshot


def test_pacing_sleeps_between_logical_intervals_only():
    clock = FakeClock()
    list(paced(_records(), "1x", clock=clock.time, sleeper=clock.sleep))
    assert len(clock.sleeps) == 2
    assert clock.sleeps[0] == pytest.approx(5.0)
    assert clock.sleeps[1] == pytest.approx(5.0)


def test_ten_x_paces_faster_than_one_x():
    fast = FakeClock()
    list(paced(_records(), "10x", clock=fast.time, sleeper=fast.sleep))
    slow = FakeClock()
    list(paced(_records(), "1x", clock=slow.time, sleeper=slow.sleep))
    assert sum(fast.sleeps) * 10 == pytest.approx(sum(slow.sleeps))


def test_replay_pacer_reset():
    pacer = ReplayPacer("5x")
    pacer.wait_for(1_000_000_000)
    pacer.reset()
    assert pacer._start_wall is None and pacer._first_ts_ns is None
