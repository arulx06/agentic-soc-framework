"""Backend configuration (operational only — no scientific equations)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

API_VERSION = "v1"

CONTRACT_VERSIONS = {
    "simulation_event": "simulation_event_v1",
    "replay_status": "replay_status_v1",
    "device_state": "device_state_v1",
    "graph_snapshot": "graph_snapshot_v1",
    "srep_snapshot": "srep_snapshot_v1",
    "saved_replay_snapshot": "saved_replay_snapshot_v1",
    "orchestration_request": "orchestration_request_v1",
    "orchestrator_proposal": "orchestrator_proposal_v1",
    "orchestrator_vote": "orchestrator_vote_v1",
    "orchestration_decision": "orchestration_decision_v1",
}

FEATURE_STORE_ROOT = REPO_ROOT / "data" / "processed" / "datasense"
RAW_ROOT = REPO_ROOT / "data/raw/datasense/dataset/raw_files"
ATTACKS_CSV = REPO_ROOT / "data/raw/datasense/docs/site/attacks.csv"
DEVICES_CSV = REPO_ROOT / "data/raw/datasense/docs/site/devices.csv"
MODELS_DIR = REPO_ROOT / "models/saved_models"
SNAPSHOT_ROOT = REPO_ROOT / "results/device_replays"

NETWORK_MODEL_PATH = MODELS_DIR / "network_detector_v1_smoke.joblib"
BEHAVIOR_MODEL_PATH = MODELS_DIR / "behavior_profiler_v1_smoke.joblib"

DEFAULT_SESSION_ID = "attack_recon_host-disc-udp-ping_soil-sensor"

EVENT_RING_BUFFER_SIZE = 4_000
SUBSCRIBER_QUEUE_SIZE = 500

# Stage-4B Blackboard integration (operational only)
BLACKBOARD_OPS_RUN_ID = "blackboard-ops"
BLACKBOARD_RECORDS_DEFAULT_LIMIT = 50
BLACKBOARD_RECORDS_MAX_LIMIT = 200
BLACKBOARD_SNAPSHOT_RECENT_LIMIT = 100
BLACKBOARD_SNAPSHOT_MAX_KEYS = 500
BLACKBOARD_DEV_WRITE_PAYLOAD_MAX_BYTES = 65_536

# Stage-6 orchestration operational integration (not a scientific replay)
ORCHESTRATION_OPS_RUN_ID = "orchestration-ops"
ORCHESTRATION_DECISIONS_DEFAULT_LIMIT = 50
ORCHESTRATION_DECISIONS_MAX_LIMIT = 200
ORCHESTRATION_DECISION_HISTORY_LIMIT = 256
ORCHESTRATION_DEFAULT_TIMEOUT_SECONDS = 0.25

WINDOW_SECONDS_DEFAULT = 5.0
CLOCK_TOLERANCE_MS_DEFAULT = 10.0
MAX_LATENESS_SECONDS_DEFAULT = 60.0
ACTIVE_WINDOW_CAPACITY_DEFAULT = 65_536
READ_CHUNK_BYTES_DEFAULT = 4 * 1024 * 1024

CORS_ALLOW_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "DATASENSE_CORS_ORIGINS", "http://localhost:5173"
    ).split(",")
    if o.strip()
]
