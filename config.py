"""Project configuration and constants."""

DATA_RAW_DIR = "data/raw"
DATA_PROCESSED_DIR = "data/processed"
MODEL_PATH = "models/detector.pkl"
DEFAULT_RANDOM_STATE = 42

# Placeholder configuration for future integration.
MODEL_NAME = "RandomForestClassifier"

# ---------------------------------------------------------------------------
# DataSense raw ingestion / feature engineering (see
# docs/datasense_raw_pipeline_methodology.md)
# ---------------------------------------------------------------------------

DATASENSE_RAW_ROOT = "data/raw/datasense/dataset/raw_files"
DATASENSE_ATTACKS_CSV = "data/raw/datasense/docs/site/attacks.csv"
DATASENSE_DEVICES_CSV = "data/raw/datasense/docs/site/devices.csv"
DATASENSE_STORE_ROOT = "data/processed/datasense"

DATASENSE_DEFAULT_WINDOW_SECONDS = 5
DATASENSE_DEFAULT_PROFILE = "standard"

# ---------------------------------------------------------------------------
# Downstream pipeline (Prompt 2): models -> Findings -> Gateway -> ABM/SREP
# All propagation/criticality/fusion numbers below are SIMULATION-DEFINED
# parameters, not dataset measurements.
# ---------------------------------------------------------------------------

DATASENSE_NETWORK_MODEL_ID = "network_detector_v1"
DATASENSE_BEHAVIOR_MODEL_ID = "behavior_profiler_v1"

DATASENSE_SPLIT_RATIOS = {"train": 0.6, "validation": 0.2, "test": 0.2}
DATASENSE_SPLIT_SEED = 42

# Behavioural chronological partition of the benign baseline.
DATASENSE_BEHAVIOR_CHRONO_SPLIT = {"train": 0.6, "calibration": 0.2, "held_out": 0.2}

DATASENSE_SREP_PARAMS = {
    # SIMULATION-DEFINED PARAMETERS - not measured by DataSense.
    "propagation_weight": 0.5,
    "hop_decay": 0.5,
    "max_hops": 3,
    "criticality": {
        "mqtt-broker": 1.0,
        "edge1": 0.9,
        "router": 0.9,
        "switch": 0.8,
        "ap": 0.8,
        "sensor": 0.5,
        "camera": 0.6,
        "smart-plug": 0.4,
        "attacker": 0.0,
        "cloud": 0.7,
    },
    "default_criticality": 0.5,
}

DATASENSE_ABM_HISTORY_LIMIT = 256
