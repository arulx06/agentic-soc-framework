"""train-behavior benign-only enforcement (unit + CLI integration)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from conftest import DEFAULT_DEVICES_ROWS
from datasets.datasense.catalog import build_session_record
from datasets.datasense.devices import DeviceInventory, DeviceRecord
from pipeline.splits import require_benign_sessions

REPO = Path(__file__).resolve().parents[1]
BENIGN_ID = "benign_whole-network3"
ATTACK_ID = "attack_recon_host-disc-udp-ping_soil-sensor"


def _by_id():
    def rec(sid, is_attack):
        cat = "recon" if is_attack else "benign"
        name = "host-disc-udp-ping" if is_attack else "benign"
        target = "soil-sensor" if is_attack else "whole-network"
        return build_session_record(
            sid,
            {},
            [
                dict(
                    filename=sid,
                    data_type="attack" if is_attack else "benign",
                    category=cat,
                    attack_name=name,
                    attack_target=target,
                    doc_count=1,
                    start="2025-01-15T21:25:13.307Z",
                    end="2025-01-15T21:26:15.119Z",
                    start_timestamp=0.0,
                    end_timestamp=0.0,
                )
            ],
        )

    return {BENIGN_ID: rec(BENIGN_ID, False), ATTACK_ID: rec(ATTACK_ID, True)}


def test_validator_accepts_benign_and_rejects_attack():
    by_id = _by_id()
    assert require_benign_sessions(by_id, [BENIGN_ID]) == [BENIGN_ID]
    with pytest.raises(ValueError, match="attack session"):
        require_benign_sessions(by_id, [ATTACK_ID])
    with pytest.raises(ValueError, match="unknown session"):
        require_benign_sessions(by_id, ["not-a-session"])
    with pytest.raises(ValueError):
        require_benign_sessions(by_id, [])


def _pipeline_module():
    spec = importlib.util.spec_from_file_location(
        "datasense_pipeline", REPO / "scripts" / "datasense_pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["datasense_pipeline"] = module
    spec.loader.exec_module(module)
    return module


def test_cli_train_behavior_refuses_attack_session_before_fitting(tmp_path):
    pytest.importorskip("sklearn")
    module = _pipeline_module()
    out = tmp_path / "should_not_exist.joblib"
    rc = module.main(
        [
            "--store",
            str(REPO / "data/processed/datasense"),
            "train-behavior",
            "--session",
            ATTACK_ID,
            "--model-out",
            str(out),
        ]
    )
    assert rc == 2
    assert not out.exists()


def test_cli_train_behavior_accepts_genuine_benign_session(tmp_path):
    store = REPO / "data/processed/datasense"
    benign_store = store / "behavior" / BENIGN_ID
    if not benign_store.is_dir():
        pytest.skip("genuine benign_whole-network3 behaviour partition not extracted yet")
    module = _pipeline_module()
    out = tmp_path / "profiler_smoke.joblib"
    rc = module.main(
        [
            "--store",
            str(store),
            "train-behavior",
            "--session",
            BENIGN_ID,
            "--model-out",
            str(out),
        ]
    )
    assert rc == 0
    assert out.exists()
