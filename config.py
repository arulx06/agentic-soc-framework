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
