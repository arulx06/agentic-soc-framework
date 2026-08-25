# Stage 3A — Versioned FastAPI Backend (Device-Layer Research System)

- **Status:** implemented and verified on bounded fixtures. The companion
  React client is documented in `docs/stage3b_react_dashboard.md`.
- Companion scientific docs: `docs/datasense_audit.md`,
  `docs/datasense_raw_audit.md`, `docs/datasense_raw_pipeline_methodology.md`.

## 1. Purpose & scope

Expose the verified Stage-2 scientific system (bounded extraction → feature
store → detectors → Findings → Gateway → ABM → graphs → DEVICE_ONLY SREP)
through a versioned FastAPI interface with a WebSocket event stream and
saved backend snapshots. Python remains the authoritative scientific
implementation. FastAPI only accepts control requests, invokes the existing
backend, serializes validated state, streams backend-produced events, and
returns snapshots.

## 2. Directory structure (actual)

```text
backend/
├── __init__.py
└── app/
    ├── __init__.py
    ├── main.py                 # FastAPI app, CORS, error handler, shutdown
    ├── config.py               # paths, contract versions, buffers, CORS
    ├── api/
    │   └── v1/
    │       ├── router.py
    │       └── endpoints/
    │           ├── health.py  sessions.py  replays.py
    │           ├── graphs.py  srep.py      snapshots.py  events.py
    ├── contracts/              # versioned Pydantic models + firewall
    │   ├── common.py  events_v1.py  replay_v1.py  device_state_v1.py
    │   ├── graph_snapshot_v1.py  srep_snapshot_v1.py  saved_snapshot_v1.py
    ├── adapters/
    │   └── stage2_replay_adapter.py    # builds ONE scientific runtime per run
    └── services/
        ├── replay_controller.py        # lifecycle/state machine/worker
        ├── event_broker.py             # bounded ring + subscriber queues
        ├── session_catalog.py          # metadata-only capability discovery
        └── snapshot_store.py           # atomic versioned JSON snapshots

tests/integration/backend/api/        # 10 FastAPI test modules
docs/stage3a_fastapi_backend.md       # this document
```

Top-level scientific packages (`agents/ datasets/ models/ pipeline/
simulation/ srep/ trust/ visualization/`) were NOT moved: they are the
verified core and relocating them would add import/regression risk for zero
scientific benefit. `visualization/` remains the offline Python plotting
area. `frontend/` contains the implemented Stage 3B React dashboard.

## 3. Scientific-core / API boundary

| Concern | Owner |
|---|---|
| inference, findings, gateway validation, ABM transitions | `pipeline/*`, `agents/finding_gateway.py` |
| risks (network/behavior/propagated/systemic), propagation, blast radius | `simulation/abm.py` |
| topology / communication aggregation | `simulation/topology.py`, `communication_graph.py` |
| SREP (DEVICE_ONLY) | `srep/device_srep.py` |
| serialization contracts, transport, streaming, snapshot files | `backend/app/*` |

No scientific equations exist in endpoints, Pydantic validators, event
broker, snapshot store or adapters. Serialization never transforms values:
`behavior_supported=false, behavior_risk=null` stays exactly that.

## 4. API version & routes

Base path: **`/api/v1`**.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | readiness plus process-local active replay recovery fields |
| GET | `/sessions` | capability metadata per cached/raw session |
| POST | `/replays` | create replay (CREATED) from `{session_id, source_mode, pacing}` |
| GET | `/replays/{id}` | ReplayStatusV1 |
| POST | `/replays/{id}/play` | CREATED→RUNNING or PAUSED→RUNNING |
| POST | `/replays/{id}/pause` | request RUNNING→PAUSED; worker stops before its next window |
| POST | `/replays/{id}/resume` | alias of play for PAUSED |
| POST | `/replays/{id}/step` | PAUSED→process exactly one window→PAUSED |
| POST | `/replays/{id}/restart` | stop old run; new replay_id, optional overrides, auto-play |
| PATCH | `/replays/{id}/speed` | pacing ∈ {1x,5x,10x,max} (wall-clock only) |
| GET | `/replays/{id}/device-state` | DeviceStateV1 list |
| GET | `/replays/{id}/graphs/device-risk` | DeviceRiskGraphSnapshotV1 |
| GET | `/replays/{id}/graphs/communication` | CommunicationGraphSnapshotV1 |
| GET | `/replays/{id}/srep` | SrepSnapshotV1 (+ artifact flags) |
| GET | `/snapshots` | list saved replay snapshots (SavedSnapshotMetaV1 list) |
| GET | `/snapshots/{snapshot_id}` | read one SavedReplaySnapshotV1 |
| POST | `/snapshots` | save the current replay snapshot (UI restricts this to COMPLETED) |
| WS | `/replays/{id}/events` | EventEnvelopeV1 stream |

Startup: `python -m uvicorn backend.app.main:app --reload`.
CORS: configurable via `DATASENSE_CORS_ORIGINS`, default
`http://localhost:5173` only. No authentication in 3A.

Errors use `ApiErrorV1 {schema_version, error_code, message, details}` for
controller failures such as unknown resources, invalid transitions,
already-active replays, unsupported modes, and restart timeouts. Endpoint
request handling validates enum and contract fields before invoking science;
`GET /replays/{id}` remains authoritative after control acknowledgements.

`/health` returns `active_replay` for process-local CREATED, RUNNING, or
PAUSED runs. `active_replay_starting=true` means a replay still reports
CREATED but already owns a live worker constructing its runtime. Terminal
runs and replays lost in a backend process restart are not recoverable through
these fields.

## 5. Contracts & schema versions

```
simulation_event_v1 · replay_status_v1 · device_state_v1 · graph_snapshot_v1
srep_snapshot_v1 · saved_replay_snapshot_v1 · api_error_v1
```

Unknown `schema_version`s are rejected explicitly (envelope validator;
snapshot store raises -> HTTP 409). Responses are versioned contract models
or explicit envelopes containing those models.

### EventEnvelopeV1 fields

`schema_version, replay_id, event_id, sequence_number(≥0), event_type,
logical_timestamp, window_id, source_component, entity_id, payload{},
provenance{}` — payload/provenance pass the recursive ground-truth firewall
at construction time.

### Event-type registry: emitted vs REST-only

All 17 registered types are genuine backend capabilities. Emission policy:

* **Streamed on the WebSocket** during/after a replay:
  REPLAY_CREATED, REPLAY_STARTED, REPLAY_PAUSED, REPLAY_RESUMED,
  REPLAY_STEPPED, REPLAY_COMPLETED, REPLAY_FAILED, WINDOW_STARTED,
  WINDOW_COMPLETED, NETWORK_FINDING, BEHAVIOR_FINDING,
  GATEWAY_ACCEPTED, GATEWAY_REJECTED — plus, exactly once per completed
  replay (after the last WINDOW_COMPLETED, before REPLAY_COMPLETED):
  DEVICE_STATE (one per device), DEVICE_RISK_GRAPH_SNAPSHOT,
  COMMUNICATION_GRAPH_SNAPSHOT and SREP_SNAPSHOT. These final scientific
  events are emitted once at replay completion and are never re-emitted.
* **POST /snapshots**: persists the already-produced final scientific state
  to the snapshot store and emits NO replay events — REPLAY_COMPLETED
  remains the last event in the replay's namespace.
* **REST-only (no events fabricated)**: on-demand reads of device state,
  both graph snapshots and SREP between windows; authoritative status and
  latest snapshots after ring-buffer eviction.

Nothing is labelled "reserved": every registered event type has a real
producer on the paths above.

## 6. Replay controller

State machine: `CREATED → RUNNING ⇄ PAUSED → COMPLETED | FAILED`
(restart leaves the machine entirely and mints a NEW replay id).

* `create` validates session capabilities + source mode, stores config,
  does NOT start science yet (state CREATED).
* `play` starts the worker thread (fresh runtime, unpaused) or opens the
  gate for PAUSED; resume is an alias. The POST response acknowledges the
  command, while status may remain CREATED during runtime construction.
* `pause` immediately records PAUSED and clears the gate. Any in-flight window
  may finish, but checkpoints before the next window prevent further work.
* `step` requires PAUSED; sets step_limit = processed+1; after that window
  completes the runner auto-pauses → back to PAUSED.
* `restart` runs its blocking join in Starlette's threadpool. It marks the old
  run cancelled, checks cancellation before and after runtime construction,
  joins for up to 10 seconds, and returns `restart_timeout` rather than
  overlapping workers if the old thread survives. Success applies optional
  session/source/pacing overrides, creates a NEW replay id, and auto-plays it.
* One active replay per process; second create → 409
  `replay_already_active`. Invalid transitions → 409 without partial
  mutation.

Worker/concurrency: each replay owns one mutable scientific runtime inside
a dedicated daemon thread; FastAPI handlers only touch controller-managed
snapshots under a re-entrant lock. Model instances are loaded fresh from
artifacts per runtime (`load_models()`), so the stateful BehaviourProfiler
gap tracker is never shared between runs (asserted by tests).

Resource cleanup: worker `finally` closes sorter temp dirs (via
runner.cleanup), ABM and communication graph; controller.shutdown() runs on
app shutdown; restart confirms that the old thread has stopped before building
the replacement. Cancellation during eager runtime construction is observed
at the post-build checkpoint rather than interrupting an individual parser or
model load operation.

## 7. Event broker & delivery

Server ring: deque(maxlen=**4000**) envelopes (configurable). Ring history,
live publication, and subscriber queues are filtered by `replay_id`; old
terminal events or sequence numbers cannot enter a replacement replay's
socket. Per-subscriber queue: deque(maxlen=**500**). On subscriber overflow the subscriber is
marked LAGGED; the next drain receives an explicit gap notice instead of a
silently truncated history, and REST snapshots are declared authoritative.
Events are published atomically in strictly increasing `sequence_number`
order per replay; only a matching terminal REPLAY_COMPLETED/FAILED closes the socket. Client
disconnects never mutate replay state (unsubscribe only). Slow-client policy:
bounded queue + explicit LAGGED flag + reconnect-via-REST.

## 8. Ground-truth firewall

`contracts/common.find_ground_truth_violations` walks dicts, lists/tuples/
sets, Pydantic models and object `__dict__` recursively, flagging forbidden
keys: label*, is_attack, attack(+category/name/names as compound tokens),
target(s)/target_device, whole_network_target, ground_truth. Exact key match
plus word-boundary token matching, so legitimate scientific keys such as
`attack_probability` and values like `predicted_class="attack"` are allowed
while `attack_category`/`targets` are rejected. Enforced in
EventEnvelopeV1 construction and tested against payloads, provenance,
device states, both graph snapshots, SREP snapshots and saved snapshots.
Real scenario ids live only server-side (catalog/status internals); events
and findings carry the opaque blake2b `session_trace`.

## 9. Graph schemas

DeviceRiskGraphSnapshotV1: nodes carry role/type, observation flags, all four
risks, attacker/protected flags; edges preserve src/dst endpoints, relationship/
direction plus evidence_type ∈ {DOCUMENTED, STRONGLY_INFERRED} taken
verbatim from topology provenance (no confidence computed in API).
CommunicationGraphSnapshotV1: pair-aggregated totals (packets/bytes),
protocol summary, first/last window+timestamps, broadcast/multicast flags.
The two kinds are distinct contracts, distinct endpoints, distinct semantics.

## 10. SREP schema

SrepSnapshotV1 exposes `mode:"DEVICE_ONLY"` always (Literal-enforced),
mode_note, steps_replayed, last window, defended_blast_radius,
compromised_protected_assets, top risky protected nodes, full per-node risk
decomposition and the SIMULATION-DEFINED parameter block verbatim from the
backend. Supplying an agent-trust graph is impossible through this API and
rejected by Stage-2 code. When artifact metadata identifies them, responses
add factual flags `SMOKE_MODEL_ARTIFACTS`, `NOT_RESEARCH_RESULTS`.

## 11. Session catalog

Metadata-only: extraction-state scan + partition existence + raw file
presence + artifact presence. Reports per session: session_trace,
feature_store_available, raw_available, network/behavior/communication
available, schema_compatible, window_count/duration, supported_source_modes
(feature_store default; direct_raw advertised only when raw pair + artifacts
exist). Never reads corpus contents.

## 12. Saved snapshots

`results/device_replays/<snapshot_id>/snapshot.json` (atomic tmp+replace).
Pure JSON via Pydantic; no pickles. Loading rejects other schema_versions
(HTTP 409) and malformed documents. Contents: replay status, device states,
both graph snapshots, DEVICE_ONLY SREP, safe provenance, contract versions.

## 13. Verification

Test accounting (separate suites):

* Scientific, integration, regression, and real-data suites outside the API
  folder: **178 tests**.
* FastAPI suite: **66 tests** in `tests/integration/backend/api`.
* Combined: `python -m pytest -q` -> **244 passed**.
* Frontend: `cd frontend && npm test` -> **80 passed**.

The complete test layout and module responsibilities are documented in
`tests.md`.

Other verified results:

* Non-interference: identical scientific projection with vs without the
  event sink (findings 475/150, gateway outcomes, ABM digest, blast radius,
  SREP, DEVICE_ONLY).
* Direct-raw vs feature-store through the CONTROLLER: strict projection
  equal; ordering diagnostics differ operationally and are reported
  separately.
* Observation masks: 572 dense rows → 475 observed → **475 NetworkFindings**
  in both modes; unobserved-row placeholder mutations cannot change output.
* Accounting: benign reconciliation identity holds; both attack caches
  compatible.
* Warnings: 0. Dependency versions verified: Python 3.14.2,
  scikit-learn 1.9.0, joblib 1.5.3, NumPy 2.5.2, FastAPI 0.141.1,
  Pydantic 2.13.4, httpx 0.28.1.

### Warning-filter locations

Two upstream cosmetic warnings are narrowly filtered at three sites:

1. **pytest.ini** — `filterwarnings` entry suppressing the Joblib/NumPy-2.5
   shape deprecation (suite-wide) and the Starlette/TestClient `httpx`
   deprecation (test-client only).
2. **tests/conftest.py** — module-level `warnings.filterwarnings` for the
   same Joblib message, so legacy tests that load artifacts directly are
   also covered without touching pytest.ini's global scope.
3. **pipeline/artifact_io.py** (`load_joblib`) — idempotent per-call
   install of the same filter, covering production/worker-thread loads
   that bypass pytest entirely.

No broad scikit-learn, NumPy or Joblib warning suppression exists anywhere.
Artifact-format and schema-version mismatch errors always propagate.
These filters should be removed once a Joblib release compatible with
NumPy ≥ 2.5's array-shape policy is adopted.

## 14. Known limitations / explicitly unimplemented

Blackboard/orchestration, five-agent coordination workflow, Agent Trust
Graph fusion & DUAL_GRAPH, ALLOW/MONITOR/BLOCK enforcement, attack
injection/recovery simulation, authentication, multi-user scheduling
(Celery/Redis/Kafka), research-scale training and
full-corpus extraction/replay. DEVICE_STATE/graph/SREP *events* beyond
window boundaries are intentionally not emitted per-window to keep event
volume bounded; they are available as REST snapshots and via the snapshot
save flow.

Bounded demo commands:

```bash
python -m uvicorn backend.app.main:app --reload
# then: GET /api/v1/sessions ; POST /api/v1/replays {"session_id": "..."} ;
# play/pause/step/restart ; GET device-state, graphs, srep ;
# WS /api/v1/replays/{id}/events
python scripts/stage3a_smoke.py            # scripted bounded demo (TestClient)
```
