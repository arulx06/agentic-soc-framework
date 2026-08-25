"""Bounded-fan-in external merge tests for WindowSorter."""

import pytest

from datasets.datasense.window_sort import WindowSorter, iter_sorted_by_window


def _rows(n, shuffle_seed=7):
    import random

    rows = [{"window_id": w, "payload": w * 2, "tag": f"t{w % 5}"} for w in range(n)]
    random.Random(shuffle_seed).shuffle(rows)
    return rows


def test_fan_in_bounds_open_readers_with_many_chunks(tmp_path):
    sorter = WindowSorter(chunk_rows=10, tmp_dir=tmp_path / "sort", merge_fan_in=3)
    for row in _rows(300):
        sorter.add(row)

    out = list(sorter.iter_sorted())

    assert [r["window_id"] for r in out] == list(range(300))
    assert sorter.total_chunks_written >= 25
    assert sorter.merge_passes >= 1
    assert sorter.max_open_readers <= 3
    assert sorter.final_level_size <= 3
    # multi-pass merging consumed the initial chunks; nothing left on disk
    assert not sorter._live_paths
    leftovers = list((tmp_path / "sort").glob("*.jsonl"))
    assert leftovers == []


def test_cleanup_after_consumer_failure(tmp_path):
    sorter = WindowSorter(chunk_rows=5, tmp_dir=tmp_path / "sort", merge_fan_in=2)
    for row in _rows(120):
        sorter.add(row)

    class Boom(Exception):
        pass

    consumed = 0
    with pytest.raises(Boom):
        for _row in sorter.iter_sorted():
            consumed += 1
            if consumed == 4:
                raise Boom()
    sorter.cleanup()

    assert consumed == 4
    assert not sorter._live_paths
    leftovers = list((tmp_path / "sort").glob("*.jsonl"))
    assert leftovers == []


def test_wrapper_cleans_up_on_abandonment(tmp_path):
    gen = iter_sorted_by_window(
        iter(_rows(80)), chunk_rows=6, tmp_dir=tmp_path / "w", merge_fan_in=2
    )
    first = next(gen)
    assert first["window_id"] == 0
    gen.close()

    leftovers = list((tmp_path / "w").rglob("*.jsonl"))
    assert leftovers == []


def test_small_chunk_count_single_final_merge(tmp_path):
    sorter = WindowSorter(chunk_rows=50, tmp_dir=tmp_path / "s", merge_fan_in=8)
    for row in _rows(100):
        sorter.add(row)
    out = list(sorter.iter_sorted())
    assert [r["window_id"] for r in out] == list(range(100))
    assert sorter.total_chunks_written == 2
    assert sorter.merge_passes == 0
    assert sorter.max_open_readers == 2
