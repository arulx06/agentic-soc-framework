from pathlib import Path

from datasets.datasense.windowing import (
    WindowGrid,
    epoch_ns_from_iso,
    iso_utc_from_ns,
)

NS = 1_000_000_000


def test_epoch_ns_from_iso_z_suffix():
    assert epoch_ns_from_iso("1970-01-01T00:00:00Z") == 0
    assert epoch_ns_from_iso("2025-01-15T21:25:13.307Z") == 1_736_976_313 * NS + 307_000_000


def test_epoch_ns_from_iso_microseconds_and_offset():
    us = epoch_ns_from_iso("2025-09-09T14:09:40.400012Z")
    ms = epoch_ns_from_iso("2025-09-09T14:09:40.400Z")
    assert us - ms == 12_000
    assert epoch_ns_from_iso("2025-01-15T21:25:13.307+00:00") == 1_736_976_313 * NS + 307_000_000


def test_iso_roundtrip_millisecond_precision():
    ts = 1_736_976_313 * NS + 307_000_000
    text = iso_utc_from_ns(ts)
    assert text == "2025-01-15T21:25:13.307Z"
    assert epoch_ns_from_iso(text) == ts


def test_window_grid_floor_semantics():
    start = 1_700_000_000 * NS
    grid = WindowGrid(start, window_seconds=5)
    assert grid.window_id(start) == 0
    assert grid.window_id(start + 4 * NS + 999_999_999) == 0
    assert grid.window_id(start + 5 * NS) == 1
    assert grid.window_id(start + 61 * NS) == 12


def test_window_grid_bounds_are_consistent():
    start = 1_736_976_313 * NS + 307_000_000
    grid = WindowGrid(start, window_seconds=5)
    wid = grid.window_id(start + 7_500_000_000)
    lo, hi = grid.window_bounds(wid)
    assert lo <= start + 7_500_000_000 < hi
    assert hi - lo == 5 * NS
    assert grid.window_start_utc(wid).endswith("Z")


def test_events_at_start_are_in_grid():
    start = 1_700_000_000 * NS
    grid = WindowGrid(start, window_seconds=5)
    wid, disp = grid.assign(start)
    assert wid == 0 and disp == "in_grid"
    wid, disp = grid.assign(start + 5 * NS)
    assert wid == 1 and disp == "in_grid"


def test_prestart_within_tolerance_snaps_to_zero():
    start = 1_700_000_000 * NS
    grid = WindowGrid(start, window_seconds=5)
    tol = 1_000_000_000
    wid, disp = grid.assign(start - 1, tol)
    assert wid == 0 and disp == "prestart_snapped"
    wid, disp = grid.assign(start - tol, tol)
    assert wid == 0 and disp == "prestart_snapped"


def test_prestart_beyond_tolerance_keeps_negative_window():
    start = 1_700_000_000 * NS
    grid = WindowGrid(start, window_seconds=5)
    tol = 1_000_000_000
    wid, disp = grid.assign(start - tol - 1, tol)
    assert wid == -1 and disp == "prestart_negative"
    wid, disp = grid.assign(start - 6 * NS, tol)
    assert wid == -2 and disp == "prestart_negative"


def test_exact_five_second_boundaries_are_positive_windows():
    start = 1_700_000_000 * NS
    grid = WindowGrid(start, window_seconds=5)
    for k in (1, 2, 10):
        wid, disp = grid.assign(start + k * 5 * NS)
        assert wid == k and disp == "in_grid"


def test_custom_window_size_configurable():
    start = 0
    grid = WindowGrid(start, window_seconds=10)
    assert grid.window_id(10 * NS - 1) == 0
    assert grid.window_id(10 * NS) == 1
