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

Current verified totals:

| Suite | Tests |
|---|---:|
| Python unit/integration/regression/real-data outside FastAPI | 178 |
| Python FastAPI | 66 |
| Python combined | 244 |
| Frontend Vitest | 80 |

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
│   └── runtime/                    Findings, replay control, ABM, SREP
├── integration/
│   ├── extraction/                 complete extraction paths and cleanup
│   ├── cli/                        command-line training safeguards
│   ├── runtime/                    per-window backend runtime behavior
│   └── backend/api/                FastAPI contracts and replay lifecycle
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
| `replayControlsHybrid.test.tsx` | Enforces lifecycle control availability, startup guards, terminal Create, pacing rules, and restart overrides. |
| `replaySocket.test.ts` | Rejects foreign replay envelopes before sequence and terminal tracking. |
| `replaySync.test.ts` | Covers bounded event history, gaps, namespace reset, startup lifecycle, and stale terminal-state rejection. |
| `replaySynchronizer.test.ts` | Covers REST authority, active replay recovery, Create conflicts, startup races, coalescing, terminal convergence, and stale-request protection. |
| `stage3b.test.tsx` | Exercises REST control contracts and core Stage 3B component behavior. |
| `stage3b_corrective.test.ts` | Covers contract rejection, graph stability, search/neighborhood behavior, and corrective presentation rules. |

`frontend/src/test/fixtures.ts` contains test-only contracts and snapshots;
`frontend/src/test/setup.ts` installs shared jsdom matchers. Neither is a
collected test module.

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
