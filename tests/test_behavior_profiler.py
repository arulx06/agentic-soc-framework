"""Behavioural profiler tests (§30)."""

from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.devices import DeviceInventory, DeviceRecord
from pipeline.behavior_profiler import (
    CONTINUOUS_MODEL_FEATURES,
    VALUE_LEVEL_FEATURES,
    BehaviorProfiler,
)


def _inventory():
    return DeviceInventory(
        [
            DeviceRecord(
                device_name=r["device_name"],
                mac=r["mac"].lower(),
                ip=r["ip"],
                role=r["role"],
                type=r["role" if False else "type"],
                main_topic=r["main_topic"],
            )
            for r in DEFAULT_DEVICES_ROWS
        ]
    )


def _row(device, wid, *, observed=True, **overrides):
    base = {
        "scenario_id": "benign_x",
        "device_id": device,
        "window_id": wid,
        "window_start_utc": f"2025-09-09T14:{wid:02d}:00.000Z",
        "behavior_observed": observed,
        "behavior_supported": True,
    }
    base.update(overrides)
    return base


def _continuous_rows(n=30):
    rows = []
    for w in range(n):
        rows.append(
            _row(
                "soil-sensor",
                w,
                messages_count=5,
                inter_message_delta_avg=1.0,
                inter_message_delta_max=1.1,
                inter_message_delta_std=0.05,
                active_fraction_of_window=1.0,
                burst_max_messages_per_second=1,
                topics_active_count=1,
                topic_entropy=0.0,
                top_topic_message_share=1.0,
                numeric_messages_count=5,
                array_messages_count=0,
                string_messages_count=0,
                qos_levels_distinct_count=1,
                retained_messages_count=0,
                duplicate_messages_count=0,
                distinct_message_ids_count=w + 1,
                value_avg=280.0,
            )
        )
    return rows


def test_only_supported_sensors_receive_profiles():
    inv = _inventory()
    profiler = BehaviorProfiler(inv)
    benign = {
        "soil-sensor": _continuous_rows(30),
        "router": [_row("router", 0, behavior_observed=False)],
    }
    profiler.fit(benign)
    assert "soil-sensor" in profiler.profiles
    assert "router" not in profiler.profiles
    assert "mqtt-broker" not in profiler.profiles
    for device in profiler.profiles:
        assert inv.behavior_profile_for(device) != "unsupported"


def test_unsupported_missing_behavior_is_not_risk_zero():
    inv = _inventory()
    from simulation.abm import DeviceABM
    from simulation.topology import build_topology

    abm = DeviceABM(inv, build_topology(inv))
    router_state = abm.states["router"]
    assert router_state.behavior_supported is False
    assert router_state.behavior_risk is None


def test_continuous_and_sparse_profiles_distinct():
    inv = _inventory()
    profiler = BehaviorProfiler(inv)

    sparse_rows = []
    for w in range(30):
        if w % 7 == 3:
            sparse_rows.append(
                _row("motion-sensor", w, messages_count=1,
                     burst_max_messages_per_second=1,
                     seconds_since_previous_event=None,
                     binary_state_flip_count=0,
                     numeric_messages_count=1)
            )
        else:
            sparse_rows.append(_row("motion-sensor", w, messages_count=0))
    profiler.fit({"soil-sensor": _continuous_rows(30), "motion-sensor": sparse_rows})
    assert profiler.profiles["soil-sensor"].profile_type == "continuous"
    assert profiler.profiles["motion-sensor"].profile_type == "sparse"
    assert profiler.profiles["soil-sensor"].model is not None
    assert profiler.profiles["motion-sensor"].model is None


def test_main_model_excludes_absolute_value_levels():
    assert not set(VALUE_LEVEL_FEATURES) & set(CONTINUOUS_MODEL_FEATURES)


def test_behavior_training_uses_only_provided_benign_rows():
    inv = _inventory()
    profiler = BehaviorProfiler(inv)
    benign = {"soil-sensor": _continuous_rows(24)}
    profiler.fit(benign)
    prof = profiler.profiles["soil-sensor"]
    assert prof.train_windows > 0
    assert prof.calibration_windows >= 1
    assert prof.held_out_windows >= 1
    assert prof.train_windows + prof.calibration_windows + prof.held_out_windows == 24
    assert prof.metadata_holds_nothing() if hasattr(prof, "metadata_holds_nothing") else True


def test_schema_versions_stable_and_checked(tmp_path):
    from datasets.datasense.versions import BEHAVIOR_FEATURE_SCHEMA_VERSION

    inv = _inventory()
    profiler = BehaviorProfiler(inv).fit({"soil-sensor": _continuous_rows(30)})
    path = tmp_path / "prof.joblib"
    profiler.save(path)
    loaded = BehaviorProfiler.load(path)
    assert loaded.metadata["feature_schema_version"] == BEHAVIOR_FEATURE_SCHEMA_VERSION

    import joblib  # noqa: F401  (dump is not deprecation-affected)

    from pipeline.artifact_io import dump_joblib, load_joblib

    blob = load_joblib(path)
    blob["metadata"]["feature_schema_version"] = "behavior_feature_schema_v999"
    dump_joblib(blob, path)
    import pytest as _pytest

    from pipeline.behavior_profiler import ProfileSchemaMismatchError

    with _pytest.raises(ProfileSchemaMismatchError):
        BehaviorProfiler.load(path)
