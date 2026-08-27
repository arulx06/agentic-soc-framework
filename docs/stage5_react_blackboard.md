# Stage 5 — React Blackboard Integration and Explainability Dashboard

Status: implemented on branch `feat/blackboard-ui` (uncommitted — pending manual review).  
Builds on verified Stage-4B replicated Blackboard backend (`docs/stage4a_blackboard_core.md`, `docs/stage4b_blackboard_integration.md`).

> **React does not implement quorum or scientific Blackboard logic. The Python backend is authoritative.**
>
> **PARTIAL_COMMIT is NOT COMMITTED.**
>
> **INSUFFICIENT_QUORUM does not expose an authoritative record.**

---

## 1. Purpose

Provide a frontend/explainability stage that visualizes backend-produced Blackboard facts without reproducing distributed-state logic. Researchers can observe replication health, committed records, operation lifecycles, and read/write outcomes as reported by the quorum-replicated backend, while existing Device-layer analysis remains undisturbed.

---

## 2. Frontend architecture

```
frontend/src/
  api/
    client.ts          ApiClient (typed fetch + Zod, baseUrl VITE_API_BASE_URL)
    contracts.ts       TS ↔ Python contracts (Zod, EVENT_TYPE_VALUES 30)
    replaySocket.ts    existing WS — now accepts 30-value enum
    validation.ts      typed errors
  state/
    ReplayContext.tsx  context + ApiClient singleton
    replayReducer.ts   single source presentation state
                       events bounded EVENT_BUFFER_LIMIT=1500 (unchanged)
  hooks/
    useReplayEvents.ts         lifecycle socket + hydrate
    replaySynchronizer.ts      REST-authoritative hydration (unchanged)
    useBlackboard.ts           NEW — REST-authoritative health/snapshot/replicas/listing
    useSnapshots.ts            unchanged
  utils/
    blackboardHelpers.ts       NEW — shortenHash, write/read/health labels,
                               groupBlackboardEvents (presentation grouping only)
  components/blackboard/
    BlackboardView.tsx         composition root for Blackboard tab
    BlackboardOverview.tsx     health/snapshot/counters/latencies
    ReplicaCards.tsx           3-replica operational view
    RecordBrowser.tsx          paginated committed-record listing
    RecordDetailDrawer.tsx     read result + null semantics + provenance
    LiveActivity.tsx           chronological BLACKBOARD_* stream (sequence_number order)
    OperationTrace.tsx         grouped by operation_id, backend terminal only
    HashField.tsx              truncated display + full hash tooltip/copy/sr-only
  pages/
    DashboardPage.tsx          single dashboard with Device View / Blackboard segmented control
  styles/
    dashboard.css              existing tokens + tone classes (tone-committed/partial/failed etc.)
  test/
    blackboard.test.tsx        NEW — 64 tests covering A-L + mandatory negative tests + bounded-refresh regression
```

`ApiClient` remains centralized — no raw `fetch()` in components. `ReplayContext` provides `client`/`state`/`dispatch`. `useBlackboard` fetches health/snapshot/replicas/listing on mount and refreshes conservatively after terminal BLACKBOARD events keyed by newest relevant `sequence_number` + `event_id` (not array length) via `useRef` guard.

---

## 3. Backend-authoritative boundary

React **never** calculates:

* quorum
* commit success
* read consistency
* replica agreement
* record authority
* conflict resolution
* stale-write determination
* trust scores, systemic risk, SREP, agent trust, orchestrator decisions

Example forbidden code never present:

```ts
if (successfulAcks.length >= 2) outcome = "COMMITTED"; // NOT ALLOWED
```

Allowed frontend-only presentation work:

* sorting (`sequence_number` order), filtering, pagination controls
* timestamp formatting, shortening hashes for display, display percentages, latency units
* grouping events by `operation_id` for display only
* bounded list management, `filter`/`select` inputs

All outcomes (`WriteOutcome`, `ReadOutcome`, `AckStatus`, `ReplicaHealth`, `event_type`, `ack_count`/`required_quorum`, `replica_sync`, `health`) are displayed verbatim from backend.

---

## 4. Navigation

Single research dashboard extended, not replaced.

* Segmented control in `DashboardPage` (reuses existing `segmented-control` style):
  ```
  Device View | Blackboard
  ```
  `Device View` (default) renders the Stage-3 runtime summary, Device Risk Graph + Communication Graph, device table, findings, SREP, provenance, Agent Trust placeholder, snapshots — unchanged.

  `Blackboard` renders `BlackboardView` — overview, replicas, record browser, detail drawer, live activity, operation trace, bounded warnings, NOT-BFT footer.

* `SREP MODE: DEVICE_ONLY` remains in `Header` (`data-testid="srep-mode-badge"`) and `SrepPanel`. No `DUAL_GRAPH`.

* `TrustGraphPlaceholder` (`aria-disabled="true"`) retained in Device View and not fed by Blackboard.

---

## 5. API endpoints consumed

Base `VITE_API_BASE_URL ?? http://localhost:8000/api/v1`

| TS method | HTTP | Path | Schema |
|---|---|---|---|
| `getBlackboardHealth()` | GET | `/blackboard/health` | `BlackboardHealthV1` |
| `getBlackboardSnapshot()` | GET | `/blackboard/snapshot` | `BlackboardSnapshotV1` |
| `getBlackboardReplicas()` | GET | `/blackboard/replicas` | `{schema_version, replicas: ReplicaStatusV1[], divergent_replicas, note}` |
| `getBlackboardReplica(id)` | GET | `/blackboard/replicas/{replica_id}` | `ReplicaStatusV1` |
| `listBlackboardRecords({record_type,key_prefix,limit,offset})` | GET | `/blackboard/records?...` | `BlackboardRecordListingV1` (items/total/limit/offset/truncated etc.) |
| `getBlackboardRecord(key)` | GET | `/blackboard/records/{record_key}` | `ReadResultV1` (200 if CONSISTENT/DEGRADED else 404/409/503/403 as thrown) |
| `getBlackboardRecordVersion(key,version)` | GET | `/blackboard/records/{record_key}/versions/{version}` | `ReadResultV1` |

`POST /blackboard/records` (restricted dev write) intentionally has **no user-facing button** — dashboard is observer, not authoring console.

All requests go through `ApiClient.request<T>(method, path, schema, body?)` with Zod validation and typed errors (`ContractValidationError`/`BackendConflictError`/`TransportError`).

---

## 6. Event types consumed

Same `EventEnvelopeV1` + same broker ring + same per-replay `sequence_number` namespace:

```
BLACKBOARD_WRITE_PROPOSED
BLACKBOARD_REPLICA_ACK
BLACKBOARD_WRITE_COMMITTED
BLACKBOARD_WRITE_PARTIAL
BLACKBOARD_WRITE_ABORTED
BLACKBOARD_WRITE_REJECTED
BLACKBOARD_STALE_WRITE
BLACKBOARD_CONFLICT
BLACKBOARD_QUORUM_FAILED
BLACKBOARD_STORAGE_FAILED
BLACKBOARD_READ
BLACKBOARD_READ_INCONSISTENT
BLACKBOARD_REPLICA_STATUS
```

`EVENT_TYPE_VALUES` extended 17 → 30 in `contracts.ts`; `isBlackboardEvent()` helper and `BLACKBOARD_EVENT_TYPES` set added. `ReplaySocket` and `EventEnvelopeV1Schema` now accept them, so live activity receives them without synthetic generation.

---

## 7. Blackboard overview

`BlackboardOverview` renders `health + snapshot` verbatim:

* `status` (`ok`/`degraded`/`offline`) with tone (`tone-committed`/`tone-partial`/`tone-failed`)
* `replicas_available / replicas_total`, `divergent_replicas.length`
* counters: `committed`, `committed_with_divergence`, `partial_commit`, `rejected_stale|conflict|schema|integrity|authorization`, `failed_quorum`, `failed_storage`, `read_consistent|degraded|not_found|insufficient_quorum|inconsistent|unavailable|authorization_rejected` — `N/A` if absent (no invented zeroes)
* `unverified_rows_excluded`
* `latencies` table (`write_global_ms`, `read_global_ms`, per-replica `replica[{id}].prepare|commit|abort` + `.unhealthy`) with `count/p50/p95/max/mean`
* `recent_rejections` capped list
* Two methodological footnotes reused everywhere:
  > Replica health describes Blackboard replication/storage state. Agent trust and L-ZTAF are not implemented yet.
  > Quorum-replicated Blackboard: two-of-three commit under the project's documented fault assumptions. This is not full Byzantine Fault Tolerance.

No `secure/trusted/compromised` labels unless backend literally provides them (it does not).

---

## 8. Replica visualization

`ReplicaCards` — when `GET /replicas` returns 3 entries, exactly 3 cards render (`data-testid="replica-card-replica_a|b|c"`). Each card shows only real fields:

* `replica_id`
* `health` (`HEALTHY|DIVERGED|UNAVAILABLE` — `replicaHealthLabel()` maps to tone but never to trust vocabulary)
* `available`
* `committed_record_count` / `pending_record_count`
* `storage_error_count` / `last_error`
* `divergence_history` (last 5, styled list)

`DIVERGED` uses amber left-border + `tone-partial`; `UNAVAILABLE` red + `tone-failed`; `PRESERVED_DIVERGENT_HEAD` string rendered verbatim both inside divergence history and as a supplemental banner:

> PRESERVED_DIVERGENT_HEAD — backend reports higher committed head preserved; not auto-converged.

Note banner `operational replication status only; no trust/...` displayed. No trust scores, no repair controls.

---

## 9. Record browser

`RecordBrowser` uses `GET /blackboard/records` exclusively:

* Filters wired to backend-supported query params only: `record_type` (6 enum values), `key_prefix`, `limit` (10/20/50/100), `offset` (Prev/Next). No client-side full-collection load.
* Displays `total` (`record-total`), `limit/offset` pagination, `responsive_replicas`, `unverified_rows_excluded` when >0.
* Rows show `record_key`, `record_type`, `record_version`, `author_id`, `content_hash` via `HashField`, `window_id`, `supporting_replicas`.
* Clicking a row opens `RecordDetailDrawer` for that `record_key`.
* Bounded honesty: when `truncated=true`, banner `Bounded Blackboard view — backend scan limit reached. Displayed totals cover the scanned scope only.` + `truncated_replicas` + `scanned_rows_per_replica` + qualified total `999 (scanned)` and footer `qualified`. When `truncated=false`, `View complete` note and authoritative totals. Snapshot has analogous `snapshot-truncated-warning` + `bounds.view_complete` inspectable.

---

## 10. Record detail / version

`RecordDetailDrawer` fetches via `GET /records/{key}` or `/versions/{version}` and renders `ReadResultV1`:

* Header: `Read outcome` (`read-outcome` with tone) + `Requested version`.
* If `OUTCOME` is not `CONSISTENT`/`DEGRADED_CONSISTENT` (`hasAuthoritativeRecord=false`), banner `read-no-authority` and **no payload/provenance rendered** — critical for `INSUFFICIENT_QUORUM`/`INCONSISTENT`:
  > INSUFFICIENT_QUORUM does not expose an authoritative record — even if one replica responded.
  > INCONSISTENT — the UI does not choose one replica value as truth.

* If authoritative: `record_id`, `record_type`, `record_version`, `author_id`, `source_component`, `logical_timestamp`, `window_id`, `content_hash` (`HashField`), version input, `payload` + `provenance` JSON (`record-payload`/`record-provenance`), `observations` table, `divergent_replicas`/`unavailable_replicas`, degraded note.

* Null semantics preserved verbatim: `behavior_supported=false` ⇒ `behavior_risk:null` stays `null` (never 0). Demonstrated in test via `... payload: {behavior_supported:false, behavior_risk:null}` → rendered ` "behavior_risk": null`.

* Error case (`404`/`409`/`503`) surfaces `BackendConflictError` message but no fabricated record.

---

## 11. Hash handling

`HashField` (`hash_helpers`):

* Compact: `shortenHash(hash)` → `a48c21…f92d` (first 6 + `…` + last 4) when length >12.
* Always preserves full hash via `title={hash}` tooltip, `aria-label`, copy button (`⧉` → `✓` for 1.4 s via `navigator.clipboard`), and `.sr-only` hidden span. Full value selectable/copyable. Never recomputed in React.

---

## 12. Operation trace — primary explainability

`OperationTrace` groups `BLACKBOARD_*` events by `payload.operation_id` **for presentation only** (`groupBlackboardEvents()`):

```
PROPOSED
↓ replica_a ACK_PREPARED · latency · hash · reason
  replica_b ACK_PREPARED
  replica_c ACK_PREPARED
↓ backend terminal result: COMMITTED / PARTIAL_COMMIT / REJECTED_STALE / ...
```

* `operationId` is backend-provided; grouping does not infer.
* `proposed` shows `record_key`/`record_version`/`record_type`/`content_hash`.
* `acks` sorted by `sequence_number`, each with `replica_id`/`ack_status`/`latency_ms`/`content_hash`/`reason`.
* `terminal` shows backend `outcome` via `writeOutcomeLabel()` (tone), `event_type`, `sequence_number`, `ack_count/required_quorum`, `commit_latency_ms`, `reason`, `replica_sync` (`k:v, …`). If `outcome=PARTIAL_COMMIT`, banner:
  > PARTIAL_COMMIT is degraded/indeterminate — exactly one replica committed. Not committed success; requires reconciliation.

* Selecting an operation highlights its row (`is-selected`) and shows lifecycle drawer. No second fetch — pure event grouping.

---

## 13. Partial-commit representation

* `WriteOutcome.PARTIAL_COMMIT` mapped to `BLACKBOARD_WRITE_PARTIAL` only — never `BLACKBOARD_WRITE_COMMITTED` (verified in `blackboard_service.py:73` and enforced in UI via `writeOutcomeLabel` which maps `PARTIAL_COMMIT` to distinct `tone-partial` and suffix ` — degraded, requires reconciliation`).
* Never rendered as `Committed`/`Success`/`Healthy Commit`/`Quorum Reached` (checked by tests: `label.toLowerCase()` does not contain `success`, not equal `COMMITTED`).
* Mandatory negative test: 3 `ACK_PREPARED` + terminal `PARTIAL_COMMIT` → drawer terminal shows `PARTIAL_COMMIT`, not inferred `COMMITTED`.

---

## 14. Read-consistency representation

`readOutcomeLabel()` discriminates:

* `CONSISTENT` (`tone-committed`, authoritative) — show record
* `DEGRADED_CONSISTENT` (`tone-partial`, authoritative + banner with divergent replicas)
* `NOT_FOUND` (no record but quorum agrees absent)
* `INSUFFICIENT_QUORUM` (`tone-failed`, no record — banner `INSUFFICIENT_QUORUM does not expose...`) — mandatory negative test: one replica contains value but outcome `INSUFFICIENT_QUORUM` → no payload
* `INCONSISTENT` (`tone-failed`, no record — banner `INCONSISTENT — the UI does not choose...`)
* `UNAVAILABLE` (`tone-failed`), `AUTHORIZATION_REJECTED` similarly

No `first response wins`.

---

## 15. Conflict / stale / quorum / storage / read-failure visibility

Distinct text + tone (not color-only):

* `STALE WRITE` → `BLACKBOARD_STALE_WRITE` / `REJECTED_STALE` (`tone-rejected`)
* `CONFLICT` → `BLACKBOARD_CONFLICT` / `REJECTED_CONFLICT` (`tone-conflict` orange)
* `QUORUM FAILURE` → `BLACKBOARD_QUORUM_FAILED` / `FAILED_QUORUM` (`tone-failed`)
* `STORAGE FAILURE` → `BLACKBOARD_STORAGE_FAILED` / `FAILED_STORAGE` (`tone-failed`)
* `PARTIAL COMMIT` → `BLACKBOARD_WRITE_PARTIAL` (`tone-partial`)
* `READ INCONSISTENCY` → `BLACKBOARD_READ_INCONSISTENT` (`tone-failed`)
* `INSUFFICIENT_QUORUM` / `UNAVAILABLE` similarly

Tables show backend `reason`, `current_version_at_replica`, `content_hash` where present; no manufactured explanations.

---

## 16. Latency presentation

`BlackboardOverview` latency section:

* Sources: `snapshot.latencies` (global `write_global_ms`/`read_global_ms` + per-replica `replica[{id}].prepare|commit|abort` and `.unhealthy` variants), derived from `BlackboardInstrumentation` (`instrumentation.py`). Also individual `latency_ms` on ACKs and `commit_latency_ms` on terminals shown in trace tables.
* Display: `count | p50 | p95 | max | mean` via `formatLatency()` (ms → s). Capped `latency_samples_limit=512` documented.
* Footer: `Operational instrumentation — not final research benchmark.` Resilience disclaimer: not a ~250 GB DataSense benchmark.

---

## 17. Provenance

* Record: `author_id` / `source_component` (`network_detector`/`behavior_profiler`/`device_abm`/`device_srep`/`api.development_write` — backend values only), `logical_timestamp`, `window_id`, `record_id`/`content_hash`, `provenance` JSON (whitelisted keys `session_trace` opaque digest, `source_mode`, `model_id`, etc.). `session_trace` never decoded.
* Snapshot: `provenance: {source_component, note}`.
* Event envelope: `provenance: {session_trace, source_mode}` per replay plus `source_component`, `entity_id`, `logical_timestamp`, `window_id`.

Ground-truth fields (`label*`, `is_attack` as ground truth, `attack_category`, `attack_name`, `targets`, `whole_network_target`, `scenario_name/id`) intentionally never rendered; `attack_probability`/`predicted_class` shown only when backend legitimately supplies them.

---

## 18. Bounded / truncated semantics

Backend reports `truncated`, `truncated_replicas`, `scanned_rows_per_replica`, `scan_bounds`, `bounds.view_complete` (`blackboard_v1.py`, `coordinator.committed_view`).

* **Listing / snapshot:** if `truncated=true`, `BlackboardView` and `RecordBrowser` render a `banner-warning`:
  > Bounded Blackboard view — backend scan limit reached. Displayed totals cover the scanned scope only.

  with `truncated_replicas` and `scanned_rows_per_replica`. Totals labeled `999 (scanned)` and footer `qualified`. If `truncated=false` and `bounds.view_complete=true`, note `View complete — scanned scope covers all responsive replicas.` and authoritative totals. No inference of completeness from small dataset.

* **Bounds inspectable:** `<details>` `Research projection bounds (inspectable)` shows `bounds` JSON plus per-replica scan metadata.

* **Tests:** complete response (`truncated=false`) shows no warning + `view-complete-note`; truncated response shows `truncated-warning` + qualified totals.

---

## 19. WebSocket / REST relationship

* **REST authoritative** — health/snapshot/replicas/records are current state; `useBlackboard` owns them and `refreshAll()`/`refreshSnapshot()` are the only writers. Disconnect does not clear them.
* **WebSocket chronological** — `useReplayEvents` → single `ReplaySocket` per replay, `sequence_number` monotonic (strictly increasing, duplicates dropped, terminal stops reconnect, bounded backoff). `LiveActivity` and `OperationTrace` consume `state.events` filtered to `BLACKBOARD_*` and sorted by `sequence_number` (not arrival). No second Blackboard socket.
* **Disconnect:** `connectionState` (`OPEN`/`RECONNECTING`/`CLOSED`) shown; on `!isLive`, banner `WebSocket ... — REST snapshot/records remain authoritative and are not cleared.` Preserves state.
* **Gap/overflow:** broker `gap_notice` → `state.gapDetected`; `EVENT_BUFFER_LIMIT=1500` overflow → `state.eventHistoryTruncated` and `BlackboardView` gap banners:
  > Subscriber gap / overflow notice — some live events were missed. REST snapshot/records remain authoritative; no missing events were fabricated.

  Missing events never synthesized.

* **Refresh strategy:** initial `refreshAll()` on mount; conservative bounded refresh after relevant terminal events (`BLACKBOARD_WRITE_COMMITTED|PARTIAL|ABORTED|REJECTED|STALE|CONFLICT|QUORUM_FAILED|STORAGE_FAILED` or `REPLICA_STATUS`) via `useEffect` keyed to the newest relevant event's `sequence_number` + `event_id` with a `useRef` last-trigger guard. This remains correct when the bounded `state.events` ring (1500) saturates and `length` stays constant while an old event drops and a new terminal arrives. Duplicate renders with the same `sequence_number`/`event_id` do not loop. No aggressive poll, no reload of universe on each ACK. The redundant `eventsVersion` length workaround was removed.

---

## 20. Frontend memory bounds

* Global `state.events` ring: `EVENT_BUFFER_LIMIT=1500` (`replayReducer`), oldest dropped + `eventHistoryTruncated=true` once exceeded — reused for Blackboard events (no second unbounded array).
* `BlackboardView` keeps no history beyond that; `LiveActivity` caps visible window `maxVisible=120` (More/Head buttons) for render performance.
* `useBlackboard` listing stays paginated (`limit`+`offset`), snapshot caps `recent_records` (100) / `latest_by_key` (500) per backend, counters/latencies/rejections bounded per `BlackboardSettings`/`instrumentation`.
* No accumulation of every ACK from arbitrarily long experiments.

---

## 21. NOT-BFT disclaimer

Every overview instance includes:

> Quorum-replicated Blackboard: two-of-three commit under the project's documented fault assumptions. This is not full Byzantine Fault Tolerance.

Footer repeats it. Never phrased as `BFT Blackboard`, `PBFT`, or `Byzantine consensus`.

---

## 22. DEVICE_ONLY SREP boundary

`Header` badge `SREP MODE: DEVICE_ONLY` (`data-testid="srep-mode-badge"`) and `SrepPanel` badge `mode ?? "DEVICE_ONLY"` (`z.literal("DEVICE_ONLY")` in `contracts.ts`) preserved on Device View. Blackboard state never mixed into SREP. Tests assert `SREP MODE: DEVICE_ONLY` visible even after Blackboard tab navigation. No `DUAL_GRAPH`.

---

## 23. Limitations

* Not BFT (§0 of stage4a): agreeing fabricated majority would be believed.
* Single `ReplaySocket`/`ReplayController` per process; partition tolerance out of scope.
* `PRESERVED_DIVERGENT_HEAD` preserved but not auto-converged; repair is explicit operational only (no UI repair controls by design).
* `BlackboardView` truncated warnings are backend-driven; completeness claim requires `bounds.view_complete=true` / `truncated=false`.
* Dev write endpoint is testing convenience, not exposed in UI.
* `SYSTEM_RECORD` currently has no automatic writer — substrate generic.
* Float hashing interpreter-deterministic, not cross-language.
* Background REST is REST-only — no WS-derived latency mutation.

No Stage-6+ functionality present: orchestrators, proposal voting, five-agent runtime, trust/access controller, watchdog/recovery, attack-injection controls, ALLOW/MONITOR/BLOCK decisions.

---

## 24. Tests

`frontend/src/test/blackboard.test.tsx` — 64 tests (micro-closure); total Vitest 160 post-stage (10 Stage-3 + 64 new = 11 files, 158 → 160 after closure).

Coverage map (matches prompt §32):

* **A. API/types** — health/snapshot/listing/detail/version/replica/truncation + query-param/encode checks
* **B. Overview** — healthy/degraded/offline + sparse counters → `N/A` + NOT-BFT footer
* **C. Replica cards** — exactly 3 cards, HEALTHY/DIVERGED/UNAVAILABLE, divergence, PRESERVED_DIVERGENT_HEAD verbatim, no trust score
* **D. Record browser** — pagination Next/Prev offset, record_type/key_prefix filters, HashField full hash via title/sr-only/copy, author/source, null semantics (drawer `behavior_risk:null`)
* **E. Bounded view** — complete vs truncated warnings, qualified vs authoritative totals, snapshot truncated path
* **F. Write outcomes** — COMMITTED/PARTIAL_COMMIT/FAILED_QUORUM/FAILED_STORAGE/REJECTED_STALE|CONFLICT distinct, PARTIAL never as committed, OperationTrace terminal check
* **G. Read outcomes** — CONSISTENT/DEGRADED/INSUFFICIENT/INCONSISTENT/UNAVAILABLE, degraded banner, negative INSUFFICIENT/INCONSISTENT no payload
* **H. Live events** — sequence ordering (2<5<9), all 13 types recognized, proposed/ack/committed shapes
* **I. Operation trace** — operation_id grouping, backend terminal displayed, ACK count ≠ outcome + the two **mandatory negative architecture tests** (3 ACKs but PARTIAL_COMMIT; 1 replica but INSUFFICIENT)
* **J. WebSocket** — disconnect/gap banners, REST preserved, no fabricated history
* **K. Regression** — device view / SREP DEVICE_ONLY / placeholder disabled / nav tabs
* **L. Ground-truth leakage** — forbidden keys absent, tainted snapshot not rendered
* Plus hash/helpers + EVENT_TYPE_VALUES 30 acceptance

Run with `cd frontend && npm test` / `npm run type-check` / `npm run build`. All 160 pass, type-check green, build ✓ (see `tests.md` for exact outputs).

---

## 25. File inventory

**Created:**

* `frontend/src/utils/blackboardHelpers.ts`
* `frontend/src/hooks/useBlackboard.ts`
* `frontend/src/components/blackboard/BlackboardView.tsx`
* `frontend/src/components/blackboard/BlackboardOverview.tsx`
* `frontend/src/components/blackboard/ReplicaCards.tsx`
* `frontend/src/components/blackboard/RecordBrowser.tsx`
* `frontend/src/components/blackboard/RecordDetailDrawer.tsx`
* `frontend/src/components/blackboard/LiveActivity.tsx`
* `frontend/src/components/blackboard/OperationTrace.tsx`
* `frontend/src/components/blackboard/HashField.tsx`
* `frontend/src/test/blackboard.test.tsx`
* `docs/stage5_react_blackboard.md` (this file)

**Modified:**

* `frontend/src/api/contracts.ts` — Blackboard schemas + EVENT_TYPE 17→30 + {is}BlackboardEvent
* `frontend/src/api/client.ts` — 7 typed Blackboard methods
* `frontend/src/pages/DashboardPage.tsx` — segmented Device View / Blackboard nav
* `frontend/src/styles/dashboard.css` — tone + hash + replica-grid helpers

**Unmodified (Stage-4 frozen):**

* `backend/app/**` (including `blackboard*` contracts/events/api/service/coordinator)
* `blackboard/**`, `pipeline/**`, `agents/**`, `simulation/**`, `srep/**`, `data/raw/**`

---

## 26. Running

```bash
cd frontend
npm run type-check   # tsc -b tsconfig.app.json --noEmit
npm test             # vitest run  (160 tests)
npm run build        # tsc -b tsconfig.app.json && vite build
```

Backend regression (unchanged):

```bash
python -m pytest tests/unit/blackboard -q -ra
python -m pytest tests/integration/backend/blackboard -q -ra
python -m pytest tests -q -ra
```

All Stage-4 Blackboard tests remain green (134 core + 30 integration + 408 total).

---

## 27. Remaining caveats

See §23. No orchestrator/L-ZTAF/watchdog/Byzantine controls were added by intention. Blackboard UI is read-only observe; bounded views are honest. `session_trace` stays opaque. Frontend type-checks against exact Python transport shapes — drift would be caught by Zod validation and type-check.
