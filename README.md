# Agentic Cybersecurity in IoT Environments

Implemented device-layer cybersecurity research system built around the
**DataSense / CIC IIoT Dataset 2025**. The repository provides bounded raw
ingestion, a versioned feature store, smoke detection artifacts, Findings and
Gateway validation, a device ABM, risk and communication graphs, DEVICE_ONLY
SREP, a versioned FastAPI service, and a React dashboard.

## Data Source

The canonical source is the DataSense raw release:

```text
data/raw/datasense/dataset/raw_files/   PCAP/PCAPNG and MQTT NDJSON pairs
data/raw/datasense/docs/site/           attacks.csv and devices.csv metadata
data/processed/datasense/               project-generated feature-store cache
```

The backend discovers available sessions from completed extraction-state
records instead of hardcoding a dataset split. The currently materialized
sessions are:

- `attack_recon_host-disc-udp-ping_soil-sensor`
- `attack_recon_ping-sweep_whole-network`
- `benign_whole-network3`

`CIS/CIC-IDS`, `CIC-IDS2017`, and `TON-IoT` are **not used by the current
pipeline**. Their old loader stubs are legacy placeholders only. Vendor
DataSense processed CSV files are optional validation references and are never
runtime or model inputs.

## Pipeline

```text
DataSense PCAP + MQTT NDJSON
  -> bounded parsers and exact 5-second temporal alignment
  -> network, behaviour, and directed communication records
  -> versioned DataSense feature store
  -> Network Detector + Behavioural Profiler
  -> Findings -> FindingGateway
  -> Device ABM + Device Risk Graph + Communication Graph
  -> DEVICE_ONLY SREP
  -> FastAPI REST/WebSocket
  -> React presentation state
```

Ground-truth labels are isolated to catalog/training/evaluation code. They do
not enter extracted feature records, runtime Findings, replay events, graphs,
SREP, or saved replay snapshots.

## Main Directories

- `datasets/datasense/`: catalog, streaming parsers, features, extraction, store
- `pipeline/`: network detector, behaviour profiler, splits, artifact handling
- `agents/`: Findings and FindingGateway validation
- `simulation/`: replay runner, control boundaries, ABM, and graphs
- `srep/`: DEVICE_ONLY security-risk evaluation
- `backend/app/`: FastAPI routes, contracts, controller, broker, snapshots
- `frontend/`: React 18, TypeScript, Vite dashboard
- `tests/`: organized Python unit, integration, regression, and real-data suites
- `docs/`: scientific audits, methodology, FastAPI, and React documentation

## Extraction And Models

```bash
# Extract one bounded DataSense session
python scripts/datasense_extract.py extract \
  --session attack_recon_host-disc-udp-ping_soil-sensor

# Inspect direct-raw and cached records through the same interface
python scripts/datasense_extract.py stream-raw --session <session-id>
python scripts/datasense_extract.py read-store --session <session-id>

# Train smoke artifacts from raw-derived feature records
python scripts/datasense_pipeline.py train-network --session <session-ids>
python scripts/datasense_pipeline.py train-behavior --session <benign-session-id>

# Replay the feature store or the equivalent direct-raw path
python scripts/datasense_pipeline.py replay-store --session <session-id> \
  --network-model models/saved_models/network_detector_v1_smoke.joblib \
  --behavior-model models/saved_models/behavior_profiler_v1_smoke.joblib
python scripts/datasense_pipeline.py demo-direct-raw --session <session-id> \
  --network-model models/saved_models/network_detector_v1_smoke.joblib \
  --behavior-model models/saved_models/behavior_profiler_v1_smoke.joblib

# Optional internal comparison against vendor DataSense features
python evaluation/datasense_vendor_validation.py
```

## FastAPI Backend

```bash
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload
```

The API is served under `/api/v1`. It exposes health and session capabilities,
replay creation and controls, device state, both graph types, DEVICE_ONLY SREP,
saved snapshots, and replay-scoped WebSocket events at
`/replays/{replay_id}/events`.

Only one non-terminal replay is active per backend process. Browser refreshes
recover `CREATED`, starting, `RUNNING`, or `PAUSED` replays through `/health`.
Restart cooperatively stops and joins the old worker, creates a new replay ID,
and auto-starts the replacement. REST status remains authoritative while the
React client uses replay-scoped events for timely synchronization.

See `docs/stage3a_fastapi_backend.md`.

## React Dashboard

```bash
cd frontend
npm install
npm run dev
npm run type-check
npm test
npm run build
```

Default development URLs:

- FastAPI: `http://localhost:8000`
- Vite: `http://localhost:5173`
- `VITE_API_BASE_URL=http://localhost:8000/api/v1`
- `VITE_WS_BASE_URL=ws://localhost:8000/api/v1`

The browser validates every REST response and event with Zod. It does not
calculate scientific values. Startup is guarded while the backend constructs a
runtime, active replay state is recovered after refresh, and foreign replay
events are rejected before sequence tracking.

See `docs/stage3b_react_dashboard.md`.

## Tests

```bash
# Complete Python suite
python -m pytest -q

# Focused Python suites
python -m pytest tests/unit -q
python -m pytest tests/integration/backend/api -q
python -m pytest tests/regression -q
python -m pytest tests/real_data -q

# Frontend suite
cd frontend
npm test
```

Current verified totals are 244 Python tests and 80 frontend tests. Suite
layout, prerequisites, fixtures, temporary-file policy, and every test module's
responsibility are documented in `tests.md`.

## Documentation

- `docs/datasense_raw_pipeline_methodology.md`: ingestion and scientific method
- `docs/datasense_raw_audit.md`: raw release audit
- `docs/datasense_audit.md`: processed release audit
- `docs/stage3a_fastapi_backend.md`: backend contracts and replay lifecycle
- `docs/stage3b_react_dashboard.md`: frontend synchronization and rendering
- `tests.md`: complete automated-test catalog
