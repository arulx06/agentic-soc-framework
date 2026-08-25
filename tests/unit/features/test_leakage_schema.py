import pytest

from datasets.datasense.behavior_features import (
    BEHAVIOR_COMMON_FEATURES,
    CONTINUOUS_PROFILE_FEATURES,
    SPARSE_PROFILE_FEATURES,
)
from datasets.datasense.feature_store import FeatureStoreReader
from datasets.datasense.network_features import (
    NETWORK_GRAPH_METADATA_FIELDS,
    NETWORK_MODEL_FEATURES,
)
from datasets.datasense.versions import REQUIRED_VERSIONS

NS = 1_000_000_000

BANNED_PREFIXES = ("label", "attack_", "target", "device", "session_", "filename", "is_attack")
BANNED_SEGMENTS = {"mac", "label", "attacker", "category", "name"}


def _segments(name: str) -> set[str]:
    cleaned = name.lower().removesuffix("_count").removesuffix("_avg").removesuffix("_max")
    cleaned = cleaned.removesuffix("_min").removesuffix("_std")
    return set(cleaned.split("_"))


def test_network_model_feature_names_are_leak_free():
    violations = []
    for feature in NETWORK_MODEL_FEATURES:
        lowered = feature.lower()
        if lowered.startswith(BANNED_PREFIXES):
            violations.append((feature, "prefix"))
        segs = _segments(lowered)
        hit = segs & BANNED_SEGMENTS
        if hit:
            violations.append((feature, sorted(hit)))
    assert violations == []


def test_behavior_model_feature_names_are_leak_free():
    all_features = (
        BEHAVIOR_COMMON_FEATURES + CONTINUOUS_PROFILE_FEATURES + SPARSE_PROFILE_FEATURES
    )
    violations = []
    for feature in all_features:
        lowered = feature.lower()
        if lowered.startswith(BANNED_PREFIXES):
            violations.append((feature, "prefix"))
        if _segments(lowered) & BANNED_SEGMENTS:
            violations.append((feature, "segment"))
    assert violations == []


def test_key_fields_carry_identity_but_are_not_model_features():
    keys = ["scenario_id", "device_id", "window_id", "window_start_utc", "window_end_utc"]
    for key in keys:
        assert key not in NETWORK_MODEL_FEATURES


def test_graph_metadata_may_hold_identities():
    assert {"observed_ips_all", "observed_macs_all"} <= set(NETWORK_GRAPH_METADATA_FIELDS)


def test_stored_records_separate_model_and_metadata(tmp_extracted_store):
    store, scenario_id = tmp_extracted_store
    reader = FeatureStoreReader(store)
    state = reader.check_compatible(scenario_id)
    assert state["versions"] == REQUIRED_VERSIONS
    for row in reader.iter_network_records(scenario_id):
        model_values = [row[f] for f in NETWORK_MODEL_FEATURES]
        assert all(v is None or isinstance(v, (int, float)) for v in model_values), row["window_id"]
        meta_values = [row[f] for f in NETWORK_GRAPH_METADATA_FIELDS]
        assert any(isinstance(v, list) for v in meta_values)
        assert row["scenario_id"] == scenario_id
        break
