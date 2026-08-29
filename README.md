# Agentic Cybersecurity in IoT Environments

Implemented device-layer cybersecurity research system built around the
**DataSense / CIC IIoT Dataset 2025**. The repository provides bounded raw
ingestion, a versioned feature store, smoke detection artifacts, Findings and
Gateway validation, a device ABM, risk and communication graphs, DEVICE_ONLY
SREP, a replicated Blackboard, a three-orchestrator quorum adjudication
substrate, a versioned FastAPI service, and a React dashboard.

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
  -> Network Detector + Behavioural Profiler (via five-agent adapters)
  -> Findings -> FindingGateway -> Device ABM / Device Risk Graph
  -> Threat Intelligence Correlator -> Risk Propagation Analyst
     -> pre-LZTAF Trust & Access Controller -> ALLOW/MONITOR/BLOCK
  -> replicated Blackboard (quorum-backed workflow records + confirmed feedback)
  -> COMMUNICATION_GRAPH_SNAPSHOT / SREP (DEVICE_ONLY)
  -> FastAPI REST/WebSocket (workflow/action/feedback + scientific events)
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
- `orchestration/`: authenticated three-replica opaque-route adjudication core
- `agentic_workflow/`: five-agent scientific core and live workflow — detectors, correlator, risk analyst, access controller, committer, Blackboard, orchestration dispatch
- `backend/app/services/workflow_service.py`: per-window orchestrated five-agent execution, Blackboard persistence, workflow/action/feedback APIs, scientific event chronology
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

## Blackboard Backend (Stage 4)

The backend carries a quorum-replicated Blackboard coordination substrate
(three independent SQLite replicas, two-of-three compatible commit policy,
authenticated/fail-stop assumptions — NOT Byzantine fault tolerance). During
replays it records accepted Network/Behavior findings from the Finding
Gateway plus one device-state and one SREP record per completed run; all
BLACKBOARD_* events flow through the same replay WebSocket chronology.

- Persistence: initialized lazily at first use under `runtime/blackboard/`
  (`replica_{a,b,c}.db`, gitignored). Override with `DATASENSE_BLACKBOARD_ROOT`;
  disable with `DATASENSE_BLACKBOARD=0`.
- API: `/api/v1/blackboard/{health,records,replicas,snapshot}` — record reads
  preserve full consistency semantics (`INSUFFICIENT_QUORUM`/`INCONSISTENT`
  never return a record as authoritative); listing is paginated.
- Tests: `python -m pytest tests/unit/blackboard tests/integration/backend/blackboard -q`

See `docs/stage4a_blackboard_core.md` and `docs/stage4b_blackboard_integration.md`.

## Orchestrator Quorum Backend (Stage 6)

The backend owns exactly three independent orchestrators (`orchestrator_a`,
`orchestrator_b`, `orchestrator_c`). They emit versioned HMAC-SHA256-authenticated
proposals and votes for caller-declared opaque routes. Two distinct compatible
`APPROVE` votes are required for a decision; timeout, delay, omission,
unavailability, disagreement, duplicates, conflicts, and provenance are exposed
through bounded REST history and the WebSocket-subscribable `orchestration-ops`
event namespace.

This is quorum-based adjudication under authenticated orchestrator-message
assumptions, not BFT, PBFT, or Byzantine consensus. A selected route is not
executed. Stage 6 adds no five-agent workflow, authoritative
ALLOW/MONITOR/BLOCK enforcement, L-ZTAF/Agent Trust Graph, watchdog, or Attack
Injection Engine. The three orchestrators are separate from Blackboard storage
`replica_a`, `replica_b`, and `replica_c`.

See `docs/stage6_orchestrator_quorum.md`.

## Five-Agent Live Workflow (Stage 8)

Stage 8 wires the five specialists through real Stage-6 quorum dispatch per window: `network_anomaly_detector`, `iot_behavioral_profiler`, `threat_intelligence_correlator`, `risk_propagation_analyst`, `trust_access_controller` (pre-LZTAF). Only ready routes become candidates; `DECIDED` with a registered route executes exactly one specialist, otherwise nothing (no fallback). Outputs are validated via `WorkflowOutputGateway` and quorum-committed to Blackboard (`THREAT_CORRELATION_RECORD`, `RISK_RECOMMENDATION_RECORD`, `ACCESS_RECOMMENDATION_RECORD`, `ENFORCEMENT_DECISION_RECORD`, `CONFIRMED_FEEDBACK_RECORD`), with `DEVICE_ONLY` SREP, `PRE_LZTAF_DEVICE_EVIDENCE` (`trust_vector_supported=False`), and `physical_enforcement_claimed=False` / `counterfactual_effect_applied=False`. Workflow/action/feedback REST and scientific `WORKFLOW_*`/`AGENT_*` events share the replay's `EventEnvelopeV1` sequence (`orchestration-ops` stays for explicit Stage-6 ops). See `docs/stage8_five_agent_workflow.md`.

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

- Stage-3: Device Risk Graph, Communication Graph, device state, `SREP MODE: DEVICE_ONLY`, findings/provenance (see `docs/stage3b_react_dashboard.md`).
- Stage-5: Quorum-replicated Blackboard explainability — health/snapshot, three replica cards, committed-record browser (paginated, filtered), record detail/version with provenance, bounded/truncated warnings, live BLACKBOARD_* activity in backend `sequence_number` order, operation trace grouped by backend `operation_id` (terminal only, never ACK-inferred), hash copy, NOT-BFT disclaimer. React never implements quorum — Python backend is authoritative.
- Stage-7: Read-only orchestration explainability with three orchestrator operational cards, proposal/vote evidence, a paginated decision browser and detail panel, chronological `orchestration-ops` activity, disagreement/timeout/delay/omission/unavailability facts, backend quorum/final outcomes, operational latency, provenance, and explicit bounded-history warnings. Routes remain opaque and are not executed.
- Stage-9: Five-agent workflow explainability — entity-scoped specialist chain (Network/Behavior → Gateway → Threat Correlator → Risk Analyst → pre-LZTAF Trust & Access → ALLOW/MONITOR/BLOCK), Findings/Gateway, threat mappings (MATCHED/UNMAPPED/UNSUPPORTED), risk recommendations, pre-LZTAF access recommendations, **recommended vs committed action** distinction, ALLOW/MONITOR/BLOCK inspection (recorded replay decision only, `physical_enforcement_claimed=false`, `counterfactual_effect_applied=false`), bounded retained action browser, chronological workflow trace with real Stage-6 dispatch, and confirmed-feedback UI with explicit confirmation and audit principal. React displays backend `AccessRecommendation`/`EnforcementDecision`; it does not calculate policy, risk, or quorum. See `docs/stage9_react_five_agent_workflow.md`.

The views share one dashboard via `Device View | Blackboard | Orchestration | Five-Agent Workflow` tabs. No raw `fetch()` escapes `ApiClient`; scientific and orchestration event histories use separate bounded sequence namespaces. React is explanatory only: Python owns orchestration quorum, workflow decisions, and final actions.

See `docs/stage3b_react_dashboard.md`, `docs/stage5_react_blackboard.md`, `docs/stage7_react_orchestration.md`, `docs/stage8a_five_agent_core.md`, `docs/stage8_five_agent_workflow.md`, and `docs/stage9_react_five_agent_workflow.md`.

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

Current verified totals are 580 Python tests and 341 frontend tests (Vitest,
16 files, 76 agentic core/closure-boundary + 22 live workflow + 67 Stage-9 workflow + 23 micro-closure). Suite
layout, prerequisites, fixtures, temporary-file policy, and every test module's
responsibility are documented in `tests.md`.

## Documentation

- `docs/datasense_raw_pipeline_methodology.md`: ingestion and scientific method
- `docs/datasense_raw_audit.md`: raw release audit
- `docs/datasense_audit.md`: processed release audit
- `docs/stage3a_fastapi_backend.md`: backend contracts and replay lifecycle
- `docs/stage3b_react_dashboard.md`: frontend synchronization and rendering
- `docs/stage4a_blackboard_core.md` / `docs/stage4b_blackboard_integration.md`: replicated Blackboard substrate
- `docs/stage5_react_blackboard.md`: Blackboard frontend visualization — authoritative boundary, endpoints/events, overview/replicas/records/trace, bounded views, NOT-BFT
- `docs/stage6_orchestrator_quorum.md`: authenticated three-orchestrator two-of-three adjudication, REST/events, fault assumptions and boundaries
- `docs/stage7_react_orchestration.md`: backend-authoritative React orchestration explainability, bounded live history, decision inspection, and stage boundaries
- `docs/stage8a_five_agent_core.md`: pure five-agent contracts, adapters, policy, committer, hooks, firewall
- `docs/stage8_five_agent_workflow.md`: live orchestrated workflow, Blackboard, action/feedback, events, lifecycle, smoke
- `tests.md`: complete automated-test catalog
