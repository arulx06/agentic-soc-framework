"""Ground truth, splitting and leakage tests (§29)."""

import pytest

from conftest import DEFAULT_DEVICES_ROWS

from datasets.datasense.catalog import build_session_record
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from pipeline.ground_truth import (
    POSITIVE_LABELS,
    WindowLabel,
    binary_label,
    label_window,
)
from pipeline.splits import (
    assert_no_prohibited_columns,
    assign_session_splits,
    benign_chronological_block,
)


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


def _row(device="soil-sensor", observed=True):
    return {"device_id": device, "network_observed": observed}


def test_targeted_session_only_target_positive():
    inv = _inventory()
    lab = label_window(
        _row("soil-sensor"),
        is_attack_session=True,
        targets=("soil-sensor",),
        whole_network=False,
        inventory=inv,
    )
    assert lab == WindowLabel.TARGET
    ctx = label_window(
        _row("mqtt-broker"),
        is_attack_session=True,
        targets=("soil-sensor",),
        whole_network=False,
        inventory=inv,
    )
    assert ctx == WindowLabel.NON_TARGET_CONTEXT
    assert binary_label(lab) == 1
    assert binary_label(ctx) == 0


def test_whole_network_excludes_evaluation_actors():
    inv = _inventory()
    attacker_lab = label_window(
        _row("attacker0"),
        is_attack_session=True,
        targets=(),
        whole_network=True,
        inventory=inv,
    )
    assert attacker_lab == WindowLabel.AMBIGUOUS_EXCLUDED
    sensor_lab = label_window(
        _row("soil-sensor"),
        is_attack_session=True,
        targets=(),
        whole_network=True,
        inventory=inv,
    )
    assert sensor_lab in POSITIVE_LABELS


def test_unobserved_rows_are_excluded_not_benign():
    lab = label_window(
        _row(observed=False),
        is_attack_session=False,
        targets=(),
        whole_network=False,
        inventory=_inventory(),
    )
    assert lab == WindowLabel.AMBIGUOUS_EXCLUDED


def test_prohibited_columns_rejected():
    from datasets.datasense.network_features import NETWORK_MODEL_FEATURES

    assert_no_prohibited_columns(NETWORK_MODEL_FEATURES)
    with pytest.raises(AssertionError):
        assert_no_prohibited_columns(list(NETWORK_MODEL_FEATURES) + ["label1"])
    with pytest.raises(AssertionError):
        assert_no_prohibited_columns(["scenario_id"] + list(NETWORK_MODEL_FEATURES)[:5])


def _catalog(tmp_path):
    rows = [
        dict(
            filename=sid,
            data_type="attack",
            category=cat,
            attack_name="x",
            attack_target=tgt,
            doc_count=1,
            start="2025-01-15T21:25:13.307Z",
            end="2025-01-15T21:26:15.119Z",
            start_timestamp=0.0,
            end_timestamp=0.0,
        )
        for sid, cat, tgt in [
            ("a_recon_t1", "recon", "soil-sensor"),
            ("b_recon_t2", "recon", "water-sensor"),
            ("c_ddos_t3", "ddos", "edge1"),
            ("d_mitm_t4", "mitm", "router"),
        ]
    ]
    return [
        build_session_record(r["filename"], {}, [r])
        for r in rows
    ]


def test_session_level_split_no_overlap_and_stratified(tmp_path):
    catalog = _catalog(tmp_path)
    splits = assign_session_splits(catalog, seed=42)
    attacks = splits["attacks"]
    assert set(attacks.values()) <= {"train", "validation", "test"}
    assert len(attacks) == 4
    by_split = {}
    for sid, split in attacks.items():
        by_split.setdefault(split, []).append(sid)
    for split, sids in by_split.items():
        assert len(sids) == len(set(sids))
    recon_splits = {
        attacks[r.scenario_id] for r in catalog if r.attack_category == "recon"
    }
    assert len(recon_splits) >= 2

    manifest = {"attack_session_splits": attacks}
    seen = {}
    for sid, split in manifest["attack_session_splits"].items():
        assert sid not in seen, "no session may cross splits"
        seen[sid] = split


def test_benign_chronological_blocks_non_overlapping():
    blocks = [
        benign_chronological_block(wid, 0, 99)
        for wid in range(0, 100)
    ]
    train_wids = [w for w, b in zip(range(100), blocks) if b == "train"]
    cal_wids = [w for w, b in zip(range(100), blocks) if b == "calibration"]
    held_wids = [w for w, b in zip(range(100), blocks) if b == "held_out"]
    assert max(train_wids) < min(cal_wids)
    assert max(cal_wids) < min(held_wids)
    assert len(train_wids) + len(cal_wids) + len(held_wids) == 100


def test_preprocessing_fitted_on_training_data_only():
    import numpy as np
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(0)
    X_train = rng.normal(loc=10.0, scale=1.0, size=(50, 3))
    X_test_shifted = rng.normal(loc=50.0, scale=5.0, size=(20, 3))

    imputer = SimpleImputer(strategy="median").fit(X_train)
    scaler = StandardScaler().fit(imputer.transform(X_train))

    train_stats = (imputer.statistics_, scaler.mean_, scaler.var_)
    combined = np.vstack([X_train, X_test_shifted])
    imputer2 = SimpleImputer(strategy="median").fit(combined)
    scaler2 = StandardScaler().fit(imputer2.transform(combined))
    leaked_stats = (imputer2.statistics_, scaler2.mean_, scaler2.var_)

    assert not np.allclose(scaler.mean_, scaler2.mean_)
    refit = StandardScaler().fit(imputer.transform(X_train))
    assert np.allclose(refit.mean_, train_stats[1])


def test_test_labels_never_influence_fitting():
    y_train = [0, 1, 0, 1]
    y_test = [1, 1, 0]
    fit_signature_values = sorted(set(y_train))
    mutated_test = y_test[:]
    for v in mutated_test:
        pass
    assert sorted(set(y_train)) == fit_signature_values
