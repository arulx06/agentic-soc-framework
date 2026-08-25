# Agentic Cybersecurity in IoT Environments

This workspace is set up as a starter project for the research and implementation pipeline described in your brief.

## Suggested structure
- data/raw - raw dataset downloads
- data/processed - cleaned dataset outputs
- datasets/ - dataset loaders and preprocessing helpers
- models/ - detector training, evaluation, and saved model artifacts
- agents/ - detection, triage, and response flow
- srep/ - graph workflow and risk logic
- security/ - attack simulation modules
- trust/ - trust and access-control logic
- evaluation/ - benchmark and experiment helpers
- visualization/ - plotting and graph visualization

## Next steps
1. Download the CIC-IDS2017 and TON-IoT datasets into data/raw.
2. Implement dataset loaders in datasets/.
3. Build preprocessing and train a detector in models/.
4. Connect the workflow in agents/ and srep/.

## DataSense raw pipeline (current work)

The canonical research source is the raw DataSense release
(`data/raw/datasense/dataset/raw_files/`, ~937 pcap+json pairs). Raw PCAP/JSON
are ingested through bounded streaming parsers with exact temporal handling
(explicit pre-start tolerance, watermark ordering) into our own aligned
5-second windows, producing per-device network features, per-sensor behaviour
features and lossless directed communication records in the versioned store
under `data/processed/datasense/`. Labels/targets never affect extraction;
they live only in the isolated session catalog. Vendor processed CSVs are
optional validation only.

- Methodology: `docs/datasense_raw_pipeline_methodology.md`
- Audits: `docs/datasense_audit.md`, `docs/datasense_raw_audit.md`

```bash
# bounded extraction (single session)
python scripts/datasense_extract.py extract --session attack_recon_host-disc-udp-ping_soil-sensor

# direct raw streaming / cached store reading (same record interface; network+behaviour+communication)
python scripts/datasense_extract.py stream-raw --session <id>
python scripts/datasense_extract.py read-store --session <id>

# INTERNAL FEATURE VALIDATION vs vendor CSV (optional)
python evaluation/datasense_vendor_validation.py

## Downstream pipeline (Prompt 2)

Models consume only the raw-derived feature records above:

```bash
python scripts/datasense_pipeline.py train-network --session <ids>      # RF detector (smoke)
python scripts/datasense_pipeline.py train-behavior --session <benign>  # sensor profiles
python scripts/datasense_pipeline.py replay-store --session <id> \
    --network-model models/saved_models/network_detector_v1_smoke.joblib \
    --behavior-model models/saved_models/behavior_profiler_v1_smoke.joblib
python scripts/datasense_pipeline.py demo-direct-raw --session <id> \
    --network-model ... --behavior-model ...   # same path straight from raw
```

## Stage-3A FastAPI backend (versioned)

```bash
pip install fastapi "uvicorn[standard]" httpx     # backend deps
python -m uvicorn backend.app.main:app --reload   # start API (dev)
python -m pytest tests/stage3_api -q -ra          # Stage-3A tests
```

Routes live under `/api/v1/` (health, sessions, replay lifecycle + controls,
device-state, both graphs, DEVICE_ONLY SREP, saved snapshots, WebSocket
events). Contracts are versioned Pydantic models; ground truth never enters
scientific payloads. Docs: `docs/stage3a_fastapi_backend.md`.

Chain: features -> Findings -> FindingGateway -> Device ABM + G_topology /
G_communication -> SREP (DEVICE_ONLY; simulation parameters in `config.py`).
Labels are evaluation-only and cannot enter runtime findings.

## Stage-3B React Dashboard

```bash
pip install fastapi "uvicorn[standard]" httpx    # backend deps (if not installed)
python -m uvicorn backend.app.main:app --reload  # FastAPI at http://localhost:8000
cd frontend && npm install                        # frontend deps
npm run dev                                      # Vite at http://localhost:5173
npm test                                         # Vitest (21 tests)
npm run build                                    # production build → frontend/dist/
```

Env vars: `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` (see `frontend/.env.example`).
Docs: `docs/stage3b_react_dashboard.md` (all routes, contracts, sync strategy).
```
