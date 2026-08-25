"""Repository paths shared by tests regardless of suite nesting."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASENSE_STORE_ROOT = REPO_ROOT / "data/processed/datasense"
DATASENSE_RAW_ROOT = REPO_ROOT / "data/raw/datasense/dataset/raw_files"
ATTACKS_CSV = REPO_ROOT / "data/raw/datasense/docs/site/attacks.csv"
DEVICES_CSV = REPO_ROOT / "data/raw/datasense/docs/site/devices.csv"
VENDOR_ATTACK_5S_CSV = (
    REPO_ROOT
    / "data/raw/datasense/dataset/processed_files/all_attack_benign_samples"
    / "attack_data/attack_samples_5sec.csv"
)
NETWORK_MODEL_PATH = REPO_ROOT / "models/saved_models/network_detector_v1_smoke.joblib"
BEHAVIOR_MODEL_PATH = REPO_ROOT / "models/saved_models/behavior_profiler_v1_smoke.joblib"
