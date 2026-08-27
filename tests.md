# Automated Test Suites

## Purpose

The automated tests protect four boundaries:

1. Raw DataSense parsing, temporal alignment, feature semantics, and bounded memory.
2. Ground-truth isolation, model behavior, and scientific replay equivalence.
3. FastAPI contracts, replay lifecycle, event isolation, and snapshot behavior.
4. React synchronization, runtime validation, controls, and graph presentation.

## Canonical Commands

Run commands from the repository root unless noted otherwise.

```bash
# All Python tests
python -m pytest -q

# Focused Python suites
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests/integration/backend/api -q
python -m pytest tests/integration/backend/blackboard -q
python -m pytest tests/unit/blackboard -q
python -m pytest tests/regression -q
python -m pytest tests/real_data -q

# Collection without execution
python -m pytest --collect-only -q

# React/TypeScript tests and build checks
cd frontend
npm run type-check
npm test
npm run build
```

Current verified totals (2026-08-27, Stage-5 `feat/blackboard-ui`):

| Suite | Tests |
|---|---:|
| Python unit/integration/regression/real-data outside FastAPI | 178 |
| Python FastAPI | 66 |
| Blackboard core (Stage-4A, `tests/unit/blackboard`) | 134 |
| Blackboard integration (Stage-4B, `tests/integration/backend/blackboard`) | 30 |
| Python combined (`python -m pytest tests -q`) | 408 |
| Frontend Vitest — Stage-3 (prior) | 96 |
| Frontend Vitest — Stage-5 Blackboard (new) | 64 |
| Frontend Vitest combined (`cd frontend && npm test`) | 160 |
| Frontend type-check (`npm run type-check`) | 0 errors |
| Frontend production build (`npm run build`) | ✓ |

Backend Stage-4 tests remain the reference — Stage 5 is frontend-only and does not change `blackboard/` or `backend/app` quorum logic (see `docs/stage5_react_blackboard.md` §23).

## Python Layout

```text
tests/
├── conftest.py                     shared synthetic DataSense builders/fixtures
├── support/
│   ├── extraction.py               reusable synthetic-session construction
│   └── paths.py                    repository/data/model path constants
├── unit/
│   ├── ingestion/                  parsers, catalog, identity, time, ordering
│   ├── features/                   feature semantics, masks, schemas
│   ├── storage/                    feature store and bounded external sorting
│   ├── modeling/                   profiler and split policy
│   ├── runtime/                    Findings, replay control, ABM, SREP
│   └── blackboard/                 Stage-4A replicated core (quorum, hashing,
│                                   versions, reads, persistence, hooks)
├── integration/
│   ├── extraction/                 complete extraction paths and cleanup
│   ├── cli/                        command-line training safeguards
│   ├── runtime/                    per-window backend runtime behavior
│   ├── backend/api/                FastAPI contracts and replay lifecycle
│   └── backend/blackboard/         Stage-4B Gateway→Blackboard→API/events
├── regression/pipeline/            closure and scientific equivalence
└── real_data/                       bounded local DataSense validation
```

`pytest.ini` limits collection to `tests/test_*.py`, uses importlib mode, adds
the repository root to the Python path, registers suite markers, and retains
only narrow dependency-warning filters.

## Unit Test Catalog

### Ingestion

| Module | Functionality |
|---|---|
| `tests/unit/ingestion/test_catalog.py` | Discovers PCAP/JSON pairs, groups attacks and targets, builds structured sessions, and reports catalog reconciliation diagnostics. |
| `tests/unit/ingestion/test_device_mapping.py` | Normalizes MAC addresses, resolves MAC/IP identities, handles unknown devices, and validates all supported sensor profiles. |
| `tests/unit/ingestion/test_pcap_streaming.py` | Streams classic PCAP and PCAPNG variants, endian and timestamp resolutions, GSO lengths, malformed formats, and truncated tails. |
| `tests/unit/ingestion/test_frame_decoder.py` | Decodes Ethernet II, IEEE 802.3/LLC/SNAP, VLAN, ARP, IPv4, TCP, UDP, ICMP, fragmentation, MSS, GSO, and runt frames. |
| `tests/unit/ingestion/test_ndjson_streaming.py` | Verifies lazy MQTT NDJSON iteration, typed messages, malformed-line accounting, and bounded reading. |
| `tests/unit/ingestion/test_timestamps_windowing.py` | Checks ISO/epoch-nanosecond conversion, round trips, floor semantics, boundaries, custom window size, and pre-start assignment. |
| `tests/unit/ingestion/test_prestart_policy.py` | Applies the shared network/telemetry tolerance, snapping, negative windows, displacement diagnostics, and exact boundaries. |
| `tests/unit/ingestion/test_telemetry_ordering.py` | Covers out-of-order telemetry, watermark failures, sorted-input equivalence, and exactly-once event accounting. |

### Features

| Module | Functionality |
|---|---|
| `tests/unit/features/test_network_features.py` | Validates counts, directions, protocols, flags, fragmentation, timing, size statistics, identity separation, empty rows, and unresolved packets. |
| `tests/unit/features/test_behavior_features.py` | Validates continuous, degenerate, sparse, unsupported, cross-window, and explicitly unobserved behavior rows. |
| `tests/unit/features/test_communication_records.py` | Preserves directed edges, aggregation, broadcast/multicast/external endpoints, bounded ports, deterministic protocols, schema, and capacity. |
| `tests/unit/features/test_observation_masks.py` | Distinguishes observed zero-valued cells from dense unobserved/null cells. |
| `tests/unit/features/test_leakage_schema.py` | Prevents labels and identities from becoming model features while allowing safe metadata and validating stored schemas. |

### Storage

| Module | Functionality |
|---|---|
| `tests/unit/storage/test_feature_store.py` | Tests Parquet round trips, atomic finalization, resume decisions, schema/window compatibility, regeneration, and reader validation. |
| `tests/unit/storage/test_window_sort_fanin.py` | Enforces bounded fan-in, reader limits, multipass ordering, abandonment cleanup, and failure cleanup. |

### Modeling

| Module | Functionality |
|---|---|
| `tests/unit/modeling/test_behavior_profiler.py` | Checks supported sensor profiles, continuous/sparse distinctions, benign-only fitting, excluded values, and artifact schemas. |
| `tests/unit/modeling/test_ground_truth_splits.py` | Validates target-aware labels, whole-network exclusions, observation masks, prohibited columns, session splits, chronological benign blocks, and fit isolation. |

### Runtime

| Module | Functionality |
|---|---|
| `tests/unit/runtime/test_findings_gateway.py` | Validates Finding routing, provenance, unknown entities, timestamps, label firewall, unsupported behavior, and subscribers. |
| `tests/unit/runtime/test_profiles_replay.py` | Verifies speed resolution, pacing equivalence, logical sleep intervals, and pacer reset. |
| `tests/unit/runtime/test_replay_control_boundaries.py` | Ensures cancellation is rechecked after a paused wake and fails immediately at cancelled checkpoints. |
| `tests/unit/runtime/test_topology_abm_srep.py` | Covers topology provenance, communication separation, ABM propagation/bounds/history, blast radius, DEVICE_ONLY SREP, and trust-graph rejection. |

### Blackboard Core (Stage 4A)

Run with `python -m pytest tests/unit/blackboard -q`. These lock the
corrected quorum semantics: `COMMITTED ⇒ ≥2 compatible ACK_COMMITTED`;
exactly one durable commit is `PARTIAL_COMMIT`; a single responsive replica
is `INSUFFICIENT_QUORUM` (never an authoritative record).

| Module | Functionality |
|---|---|
| `test_contracts.py` | Record schema/registry, recursive ground-truth firewall, integrity binding, tamper detection. |
| `test_hashing.py` | Canonical JSON determinism, order invariance, mutation sensitivity, hashed-field set. |
| `test_replica_independence.py` | Three physical SQLite stores/locks, isolated state, exactly-three coordinator rule. |
| `test_versioning.py` | Monotonic v1/v2/v3, stale rejection, ahead-of-head schema rejection, replica-layer conflicts, lease takeover. |
| `test_quorum_lifecycle.py` | Quorum combinator (3/2/1/0/splits), prepare→commit lifecycle, abort-on-failure, equivocation-seam isolation. |
| `test_commit_quorum.py` | Commit-phase durability matrix (3/2/1/0 commits), restart after partial commit, COMMITTED⇒committed-quorum invariant battery. |
| `test_partial_commit_repair.py` | Divergence marking after missed commits, explicit head-aligned repair, no-majorsource refusal, authorization on repair. |
| `test_reads.py` | CONSISTENT / DEGRADED / NOT_FOUND / INSUFFICIENT_QUORUM / INCONSISTENT / UNAVAILABLE matrix, version reads, pending invisibility. |
| `test_persistence_restart.py` | Restart survival of committed state; pending/aborted never become committed; failed-quorum cleanliness. |
| `test_authorization.py` | Allow-all dev default vs deny-closed principal policy; denials change no state. |
| `test_fault_hooks.py` | Identity/pass-through default seams, hook-driven unavailability → UNAVAILABLE acks, no mutation vocabulary in production surface. |
| `test_concurrency.py` | Same-key thread races have one winner; optimistic retry converges without gaps; duelling coordinators. |
| `test_bounded_history.py` | Capped operation/rejection/latency rings, counter accuracy, settings validation. |
| `test_bounded_scan.py` | Explicit truncation/completeness flags for merged committed views under tiny configurable scan bounds. |
| `test_listener_isolation.py` | Phase-listener/publisher failures cannot alter outcomes, quorum, PARTIAL_COMMIT or persistence; failures counted. |

## Integration Test Catalog

| Module | Functionality |
|---|---|
| `tests/integration/extraction/test_extraction_engine.py` | Runs complete synthetic extraction, resume/failure recovery, resource-profile equivalence, direct/store equivalence, and event accounting. |
| `tests/integration/extraction/test_extraction_cleanup.py` | Proves sorter cleanup and absence of partial finalized output on feed, merge, close, and success paths. |
| `tests/integration/extraction/test_label_invariance.py` | Proves changed ground truth cannot change extracted scientific records and that direct/store records remain label-free. |
| `tests/integration/cli/test_behavior_training_guard.py` | Enforces benign-only behavioral training in both policy functions and the real CLI entry path. |
| `tests/integration/runtime/test_communication_per_window.py` | Verifies per-window communication deltas, cumulative totals, empty-window resets, bounded protocols, and API contract exposure. |

### FastAPI

| Module | Functionality |
|---|---|
| `tests/integration/backend/api/test_contracts.py` | Validates event, status, state, graph, SREP, saved-snapshot, error, and recursive firewall contracts. |
| `tests/integration/backend/api/test_ground_truth_firewall.py` | Applies forbidden-key checks across every backend serialization surface. |
| `tests/integration/backend/api/test_event_broker_replay_scope.py` | Ensures late history and live subscriber delivery never mix replay namespaces. |
| `tests/integration/backend/api/test_event_chronology.py` | Verifies sequence/window ordering, acceptance counts, one terminal event, and final scientific event ordering. |
| `tests/integration/backend/api/test_health_active_replay.py` | Verifies refresh recovery fields for unstarted and already-starting CREATED replays. |
| `tests/integration/backend/api/test_direct_raw_communication.py` | Checks direct-raw communication population and feature-store/direct-raw graph equivalence without graph regressions. |
| `tests/integration/backend/api/test_model_instance_isolation.py` | Ensures detector and profiler instances are fresh across loads, restarts, and sequential runs. |
| `tests/integration/backend/api/test_replay_controller.py` | Covers lifecycle transitions, one-active policy, controls, pacing, early totals, incremental progress, restart namespaces, construction cancellation, repeated restarts, and errors. |
| `tests/integration/backend/api/test_scientific_non_interference.py` | Proves event instrumentation does not alter scientific projections or observation-mask finding counts. |
| `tests/integration/backend/api/test_snapshot_event_boundary.py` | Verifies final event ordering and that temporary snapshot persistence emits no replay events. |

### Blackboard Integration (Stage 4B)

Run with `python -m pytest tests/integration/backend/blackboard -q`.

| Module | Functionality |
|---|---|
| `test_blackboard_api.py` | Health/records/versions/replicas/snapshot endpoints, pagination + filters, truncated-vs-complete view flags, authorization before prepare, masquerade restriction, persistence through backend reconstruction. |
| `test_blackboard_events.py` | Real PROPOSED→3 ACKs→COMMITTED chronology in one sequence namespace; stale/conflict/quorum-failure/partial event fidelity (PARTIAL never emits WRITE_COMMITTED); read/inconsistent-read events; disabled-integration 503. |
| `test_blackboard_pipeline_integration.py` | Mandatory scientific non-interference on the bounded feature-store session, Gateway rejection isolation, no-double-processing control, leakage scans over events/snapshot/rejections, documented chronology policy, observation-semantics preservation (`behavior_supported=False ⇒ behavior_risk=None`), direct/store record equivalence after excluding operational provenance. |

## Regression And Real-Data Catalog

| Module | Functionality |
|---|---|
| `tests/regression/pipeline/test_closure_regression.py` | Checks scalar/vector behavior equivalence, row/batch network equivalence, stable sorting, finding order, and cleanup ownership. |
| `tests/regression/pipeline/test_corrective_pass.py` | Covers observation-mask invariance, benign chronological data, metrics, sparse absence, stress replay, and sorter round trips. |
| `tests/regression/pipeline/test_replay_equivalence.py` | Proves speed/history invariance and direct-raw versus feature-store downstream equivalence. |
| `tests/regression/pipeline/test_scientific_equivalence.py` | Performs strict saved-model scientific projection comparison and negative mutation detection. |
| `tests/real_data/test_raw_sessions.py` | Runs bounded checks against the local DataSense fixture, audited packet/message counts, masks/schemas, and optional vendor parity. |

## Frontend Test Catalog

Frontend tests live under `frontend/src/test` and run with Vitest/jsdom.

| Module | Functionality |
|---|---|
| `communicationPerWindow.test.ts` | Maps per-window communication deltas into line width and directional particle behavior. |
| `dashboard.test.tsx` | Covers header warnings/progress, device unsupported/zero semantics, trust placeholder, and DEVICE_ONLY SREP display. |
| `graphModel.test.ts` | Validates graph conversion, topology identity, coordinates, filtering, and presentation metadata. |
| `nodeModelRegistry.test.ts` | Validates 3D node model registry and material contracts (Stage-3D). |
| `replayControlsHybrid.test.tsx` | Enforces lifecycle control availability, startup guards, terminal Create, pacing rules, and restart overrides. |
| `replaySocket.test.ts` | Rejects foreign replay envelopes before sequence and terminal tracking. |
| `replaySync.test.ts` | Covers bounded event history, gaps, namespace reset, startup lifecycle, and stale terminal-state rejection. |
| `replaySynchronizer.test.ts` | Covers REST authority, active replay recovery, Create conflicts, startup races, coalescing, terminal convergence, and stale-request protection. |
| `stage3b.test.tsx` | Exercises REST control contracts and core Stage 3B component behavior. |
| `stage3b_corrective.test.ts` | Covers contract rejection, graph stability, search/neighborhood behavior, and corrective presentation rules. |
| `blackboard.test.tsx` | Stage-5: API/types, overview (healthy/degraded/offline + N/A + NOT-BFT), replica cards (3×, HEALTHY/DIVERGED/UNAVAILABLE, PRESERVED_DIVERGENT_HEAD, no trust), record browser (pagination/filters/hash/author/null semantics), bounded view (complete/truncated, qualified vs authoritative totals + non-vacuous snapshot warning), write outcomes (COMMITTED/PARTIAL_COMMIT/FAILED_QUORUM/FAILED_STORAGE/STALE/CONFLICT), read outcomes (CONSISTENT/DEGRADED/INSUFFICIENT/INCONSISTENT/UNAVAILABLE), live events (sequence order + 13 BLACKBOARD_* shapes), operation trace (grouping by operation_id, backend terminal not ACK-count, two mandatory negative architecture tests), WebSocket disconnect/reconnecting/gap (genuine BlackboardView + real reducer/gapDetected, REST preserved, no fabricate), bounded-refresh regression (same-length replacement triggers refresh via sequence+event_id, duplicate no-loop) + dashboard regression (SREP DEVICE_ONLY / placeholder / nav tabs), ground-truth leakage, hash helpers and 30-value EventEnvelope acceptance (64 tests). |

`frontend/src/test/fixtures.ts` contains test-only contracts and snapshots;
`frontend/src/test/setup.ts` installs shared jsdom matchers. Neither is a
collected test module.

### Stage-5 verification outputs (2026-08-28, micro-closure)

```text
# Backend (unchanged Stage-4)
python -m pytest tests -q                          → 408 passed
python -m pytest tests/unit/blackboard -q         → 134 passed
python -m pytest tests/integration/backend/blackboard -q → 30 passed

# Frontend
cd frontend
npm run type-check                                 → 0 errors
npm test                                           → 11 files, 160 passed (96 Stage-3 + 64 Stage-5)
npm run build                                      → ✓ 473 modules, build succeeded
```

Micro-closure fixes: BlackboardView refresh now keyed to newest relevant `sequence_number` + `event_id` (not `length`), `eventsVersion` removed; vacuous `toBeGreaterThanOrEqual(0)` snapshot test replaced with `findByTestId("snapshot-truncated-warning")` + content; WebSocket disconnect/reconnect/gap tests now exercise real `BlackboardView` + `ReplayContext`/`replayReducer` `EVENT_GAP`; added bounded-refresh regression (same-length replacement).

## Data And Artifact Prerequisites

Most unit tests use synthetic bounded data and require no local DataSense
release. The following suites use repository-local caches or artifacts:

- `tests/real_data`: raw fixture, `attacks.csv`, and `devices.csv`; vendor CSV is optional.
- Replay/scientific regression: extracted feature-store partitions and saved smoke models.
- Direct-raw FastAPI tests: the matching raw PCAP/NDJSON pair and metadata.
- Behavioral CLI acceptance: the extracted benign behavior partition when available.

Tests with optional external prerequisites use explicit skip conditions where
appropriate. The standard development fixture is
`attack_recon_host-disc-udp-ping_soil-sensor`.

## Fixtures And Temporary Files

- `tests/conftest.py` owns synthetic frame, PCAP, PCAPNG, NDJSON, device, and extraction fixtures.
- `tests/support/extraction.py` builds reusable synthetic session metadata.
- `tests/support/paths.py` prevents folder depth from affecting repository paths.
- Pytest `tmp_path` and `tmp_path_factory` own generated feature stores, sorter spills, models, and snapshots.
- Snapshot API tests replace the production `SnapshotStore` with a temporary store.
- Replay controllers and worker threads must be shut down by their owning fixture or test.
- `__pycache__`, `.pytest_cache`, coverage output, models, raw data, and experiment results are ignored by `.gitignore`.

## Adding Tests

1. Place isolated component tests under the matching `tests/unit` area.
2. Place multi-component paths under `tests/integration`.
3. Place scientific equivalence/closure checks under `tests/regression`.
4. Place local release validation under `tests/real_data` with clear skip behavior.
5. Use `tests/support/paths.py`; do not calculate the repository root from a test file's nesting depth.
6. Keep generated files under pytest temporary directories.
7. Preserve deterministic seeds, bounded inputs, lifecycle cleanup, and ground-truth isolation.
