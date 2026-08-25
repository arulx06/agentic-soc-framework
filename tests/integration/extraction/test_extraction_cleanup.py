"""Automatic extraction-wrapper sorter cleanup on every exit path (§5).

The wrapper owns the sorter lifecycle: feeding failure, sorted-consumption
failure and early consumer closure must all remove spilled temporary files
WITHOUT the caller invoking ``sorter.cleanup()`` manually.
"""

import json

import pytest

from conftest import DEFAULT_DEVICES_ROWS, mqtt_record
from datasets.datasense import extraction as extraction_mod
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from datasets.datasense.windowing import iso_utc_from_ns
from tests.support.extraction import build_synthetic_session

BASE_NS = 1_736_976_313 * 10**9 + 307_000_000


def _inventory():
    return DeviceInventory(
        [
            DeviceRecord(
                device_name=r["device_name"],
                mac=r["mac"].lower(),
                ip=r["ip"],
                role=r["role"],
                type=r["type"],
                main_topic=r["main_topic"],
            )
            for r in DEFAULT_DEVICES_ROWS
        ]
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Synthetic multi-chunk telemetry source + instrumented sorter factory."""
    lines = []
    for i in range(400):  # 400 rows / 25-per-chunk -> many spilled chunks
        wid = i % 11
        ts_ns = BASE_NS + wid * 5 * 10**9 + (i % 1000) * 1000
        rec = mqtt_record(
            iso_utc_from_ns(ts_ns),
            ip="192.168.1.12",
            mac="F0:08:D1:CE:CF:0C",
            value=float(i),
            message_id=i,
        )
        lines.append(json.dumps(rec))
    src = tmp_path / "src.json"
    src.write_text("\n".join(lines) + "\n", encoding="utf-8")

    inventory = _inventory()
    session = build_synthetic_session(tmp_path)
    session.raw_json_path = str(src)

    spool = tmp_path / "spool"
    real_sorter = extraction_mod.WindowSorter

    def small_factory(*a, **kw):
        return real_sorter(chunk_rows=25, tmp_dir=spool, merge_fan_in=3)

    monkeypatch.setattr(extraction_mod, "WindowSorter", small_factory)

    def spool_files():
        return list(spool.rglob("*.jsonl")) if spool.exists() else []

    def gen(**overrides):
        kwargs = dict(
            window_seconds=5.0,
            clock_tolerance_ns=10_000_000,
            max_event_lateness_ns=60 * 10**9,
            active_window_capacity=1024,
        )
        kwargs.update(overrides)
        return extraction_mod.iter_behavior_rows(session, inventory, **kwargs)

    return gen, spool_files


def test_auto_cleanup_on_source_feeding_failure(env, monkeypatch):
    gen, spool_files = env

    class Boom(Exception):
        pass

    real_iter = extraction_mod.iter_mqtt_events
    spill_snapshot_at_failure = []

    def failing_iter(path):
        count = 0
        for ev in real_iter(path):
            yield ev
            count += 1
            if count >= 250:  # several chunks already spilled
                spill_snapshot_at_failure.append(len(spool_files()))
                raise Boom()

    monkeypatch.setattr(extraction_mod, "iter_mqtt_events", failing_iter)

    consumed = 0
    with pytest.raises(Boom):
        for _row in gen():
            consumed += 1

    # Feeding failed after multiple chunk spills; the wrapper's finally must
    # have removed every spilled file without manual cleanup.
    assert spill_snapshot_at_failure and spill_snapshot_at_failure[0] >= 5
    assert consumed == 0  # consumption only starts after successful feeding
    assert spool_files() == [], "feeding failure must auto-clean spill files"


def test_auto_cleanup_on_early_consumer_close(env):
    gen, spool_files = env
    generator = gen()
    for _ in range(5):
        next(generator)
    generator.close()  # early consumer closure
    assert spool_files() == []


def test_auto_cleanup_on_success(env):
    gen, spool_files = env
    rows = list(gen())
    assert len(rows) > 0
    assert spool_files() == []


def test_no_partial_manager_output_after_failure(env, monkeypatch):
    """Feeding failure: exception propagates, ZERO rows yielded, manager
    finalization and dense-fill never run, spill files auto-cleaned."""
    gen, spool_files = env

    finish_calls = {"count": 0}
    real_manager = extraction_mod.BehaviorWindowManager

    class SpyManager(real_manager):
        def finish(self):
            finish_calls["count"] += 1
            return super().finish()

    monkeypatch.setattr(extraction_mod, "BehaviorWindowManager", SpyManager)

    class Boom(Exception):
        pass

    real_iter = extraction_mod.iter_mqtt_events
    spill_snapshot_at_failure = []

    def failing_iter(path):
        count = 0
        for ev in real_iter(path):
            yield ev
            count += 1
            if count >= 250:  # several chunks already spilled (25/chunk)
                spill_snapshot_at_failure.append(len(spool_files()))
                raise Boom()

    monkeypatch.setattr(extraction_mod, "iter_mqtt_events", failing_iter)

    got = []
    with pytest.raises(Boom):
        for row in gen():
            got.append(row)

    # feeding failed after multiple chunk spills; wrapper's finally cleaned up
    assert spill_snapshot_at_failure and spill_snapshot_at_failure[0] >= 5
    assert got == [], "a failed extraction must not yield any feature row"
    assert finish_calls["count"] == 0, (
        "manager.finish() must not be called after a feeding failure"
    )
    assert spool_files() == [], "spill files must be auto-removed"


def test_no_finalization_after_sorted_consumption_failure(env, monkeypatch):
    """Consumption/merge-phase failure AFTER successful feeding: exception
    propagates, no rows yielded, no finalization, spill files auto-cleaned."""
    gen, spool_files = env

    finish_calls = {"count": 0}
    real_manager = extraction_mod.BehaviorWindowManager

    class SpyManager(real_manager):
        def finish(self):
            finish_calls["count"] += 1
            return super().finish()

    monkeypatch.setattr(extraction_mod, "BehaviorWindowManager", SpyManager)

    real_parse = extraction_mod.parse_telemetry_line
    parse_calls = {"count": 0}

    def failing_parse(line):
        obj = real_parse(line)
        parse_calls["count"] += 1
        if parse_calls["count"] >= 120:  # mid sorted consumption
            raise RuntimeError("injected reconstruction failure")
        return obj

    monkeypatch.setattr(extraction_mod, "parse_telemetry_line", failing_parse)

    got = []
    with pytest.raises(RuntimeError, match="injected reconstruction failure"):
        for row in gen():
            got.append(row)

    assert got == []
    assert finish_calls["count"] == 0
    assert spool_files() == []
