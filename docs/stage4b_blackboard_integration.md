# Stage 4B — Blackboard Pipeline, Event and API Integration

Status: implemented on branch `feat/blackboard` (uncommitted). Builds on the
verified Stage-4A core (`docs/stage4a_blackboard_core.md`) and preserves its
corrected semantics exactly.

Explicit non-goals (nothing below exists after this stage): **NOT full
Byzantine Fault Tolerance** · **NOT orchestrator adjudication / votes** ·
**NOT the five-agent workflow** · **NOT L-ZTAF / authentication** · **NOT an
Agent Trust Graph** · **NOT DUAL_GRAPH SREP** · **NOT an Attack Injection
Engine** · **NOT React Blackboard UI**. SREP remains `DEVICE_ONLY`.

---

## 0. Additive Stage-4A core changes made for Stage 4B (audit record)

The verified Stage-4A quorum core was NOT redesigned, but it was NOT left
byte-identical either. The following additive changes to the `blackboard/`
package were made specifically so the API/instrumentation layer could be
built without duplicating core state. All are backwards-compatible
(defaults preserve previous behaviour) and are covered by the Stage-4A
suite:

* `blackboard/storage.py`
  - added `ReplicaDatabase.iter_committed_rows(key_prefix, limit, offset)`:
    bounded, deterministic committed-row projection for listing/snapshot
    support (never exposes pending rows);
  - extended `count_committed()` with an optional `key_prefix` filter;
  - chunked scanning relies on these primitives.
* `blackboard/coordinator.py`
  - `propose()` gained an OPTIONAL `phase_listener(phase, info)` callback
    (`"PROPOSED"` once, `"PREPARED"` per replica ack) so real replica ACKs
    could become events without any synthetic generation. Listener
    exceptions are counted (`listener_errors`) and isolated: prepare
    semantics, commit quorum, PARTIAL_COMMIT handling and persistence are
    identical with, without, or crashing listeners (regression-tested);
  - added `head_version(record_key)` operational hint used by the Gateway
    adapter's optimistic versioning (safety still comes from per-replica CAS);
  - added `committed_view(...)` merged quorum-filtered listing with explicit
    chunked scanning, named bounds and honest `truncated` indicators (§9).
* No other `blackboard/` file was modified during Stage 4B. The earlier
  corrective-pass changes (PARTIAL_COMMIT/INSUFFICIENT_QUORUM contracts,
  instrumentation invariant backstop, read-policy rewrite) are part of the
  preserved Stage-4A-corrective state, not new 4B edits.

## 1. Finding Gateway integration

The FindingGateway remains the single authoritative validation boundary.
Integration is a pure subscription:

```
finding produced
      ↓
FindingGateway.submit()          (validation + ABM apply — unchanged)
      ├─ rejected → nothing (observers never fire)
      └─ accepted → observers(finding)            [Stage-4B seam]
                        ↓
        BlackboardService.record_finding()
                        ↓
        typed record proposal → 3-replica lifecycle
```

`build_runtime()` gained an optional `finding_observers=()` parameter and
`ScientificRuntime.gateway` exposure; `ReplayController(blackboard=...)`
wires one observer per run. The ABM path itself is untouched: observers run
AFTER gateway validation/ABM application inside `submit()`, so double
processing is structurally impossible (proven by the mandatory
non-interference test).

## 2. Typed records produced automatically

| Source | Record type | Key | Author |
| --- | --- | --- | --- |
| accepted NetworkFinding | NETWORK_FINDING_RECORD | `finding/network/{replay_id}/{entity}` | `network_detector` |
| accepted BehaviorFinding | BEHAVIOR_FINDING_RECORD | `finding/behavior/{replay_id}/{entity}` | `behavior_profiler` |
| completed-run device state | DEVICE_STATE_RECORD | `device_state/{replay_id}/{entity}` | `device_abm` |
| completed-run SREP | DEVICE_ONLY_SREP_RECORD | `srep_snapshot/{replay_id}` | `device_srep` |

Record policy (conservative/bounded): every accepted finding becomes one
versioned record; final device state + SREP are written ONCE per completed
replay; graph snapshots are never duplicated onto the Blackboard. Payloads
carry only genuine existing fields (e.g. `attack_probability`,
`predicted_class`, `deviation_score`, `profile_type`, `confidence`,
`source_model`) plus whitelisted provenance including opaque
`session_trace`. `behavior_supported=False` keeps `behavior_risk=None`
(never zero). Authors are limited to components that actually exist.

## 3. Run isolation & replay lifecycle

All automatic scientific keys embed `{replay_id}`: a new/restarted replay
starts fresh version namespaces and cannot read a previous run's records as
inputs; completed/failed runs leave their records inspectable but inert.
Blackboard process/persistence restart is separate — committed records
survive backend reconstruction (tested through the public API), while
replay restart never deletes persistent stores. Events emitted outside any
run use the bounded operational namespace `blackboard-ops` with its own
monotonic sequence.

## 4. Events

New `ReplayEventType` members (same `EventEnvelopeV1`, same broker ring,
same WebSocket, same per-replay sequence namespace):

```
BLACKBOARD_WRITE_PROPOSED   BLACKBOARD_REPLICA_ACK
BLACKBOARD_WRITE_COMMITTED  BLACKBOARD_WRITE_PARTIAL
BLACKBOARD_WRITE_ABORTED    BLACKBOARD_WRITE_REJECTED
BLACKBOARD_STALE_WRITE      BLACKBOARD_CONFLICT
BLACKBOARD_QUORUM_FAILED    BLACKBOARD_STORAGE_FAILED
BLACKBOARD_READ             BLACKBOARD_READ_INCONSISTENT
BLACKBOARD_REPLICA_STATUS
```

Corrected Stage-4A fidelity at the event layer:

* `BLACKBOARD_WRITE_COMMITTED` ⇔ `WriteOutcome.COMMITTED` ⇒ ≥ 2 compatible
  `ACK_COMMITTED` (invariant enforced in coordinator, instrumentation
  backstop, and regression tests);
* `PARTIAL_COMMIT` emits `BLACKBOARD_WRITE_PARTIAL` ONLY — never a
  committed event, and API bodies keep it distinct from success;
* `FAILED_QUORUM` additionally emits `BLACKBOARD_WRITE_ABORTED` when aborts
  actually ran; rejections map to STALE/CONFLICT/REJECTED variants.

ACK events carry real replica acknowledgements (operation_id, replica_id,
record identity fields, ack_status, reason, latency_ms) from the actual
prepare phase — no synthetic ACK generation exists. Committed payloads
expose operation_id, record identity, `ack_count`, `required_quorum`,
`acknowledgements[]`, author/source, logical_timestamp/window_id and
commit latency. Read events expose outcome + per-replica observations;
single-responder results appear only as `INSUFFICIENT_QUORUM` facts, never
as authoritative records.

Documented emission policy: the Gateway observer fires INSIDE
`submit()`, so for each finding `PROPOSED → 3 ACKs → terminal` precedes the
runner's `GATEWAY_ACCEPTED` marker in sequence order. All events share one
monotonic per-run sequence (no parallel counters).

## 5. Snapshot schema & API

`blackboard_snapshot_v1` (`backend/app/contracts/blackboard_v1.py`):
snapshot_id, generated_at_utc, `latest_by_key` (head per key, ≤500 keys),
bounded `recent_records`, `replica_statuses[]`, `divergent_replicas`,
counters (commits, **partial_commit**, rejections incl. stale/conflict,
quorum/storage failures, **read_insufficient_quorum**), bounded latencies,
recent rejections, `unverified_rows_excluded`, bounds metadata, provenance.
The projection itself passes the ground-truth firewall before serving.

Routes (extended existing app/router — no new server):

```
GET  /api/v1/blackboard/health
GET  /api/v1/blackboard/snapshot
GET  /api/v1/blackboard/records?record_type=&key_prefix=&limit=&offset=
GET  /api/v1/blackboard/records/{record_key}              (latest)
GET  /api/v1/blackboard/records/{record_key}/versions/{version}
GET  /api/v1/blackboard/replicas                          (+ /{replica_id})
POST /api/v1/blackboard/records                           (RESTRICTED dev write)
```

Read outcomes map honestly: NOT_FOUND→404; INSUFFICIENT_QUORUM /
INCONSISTENT→409 (no record body); UNAVAILABLE→503; authorization→403.
Listing is paginated (default 50, max 200) with type/prefix filters; rows
backed by fewer than quorum replicas are excluded and counted
(`unverified_rows_excluded`), never served silently.

**Bounded-view honesty:** listing/snapshot scans iterate replicas in
configurable chunks up to a NAMED bound
(`committed_scan_max_rows`, default 10 000; `committed_scan_chunk_size`,
default 1 000 — both in `BlackboardSettings`). Whenever a responsive
replica holds more committed rows than its scanned scope, every affected
response carries `truncated: true` (+ `truncated_replicas`,
`scanned_rows_per_replica`, `scan_bounds`; snapshots additionally expose
`bounds.view_complete`). A truncated view is therefore always
distinguishable from a COMPLETE VIEW — totals describe only the scanned
scope and are never presented as the full universe. React (Stage 5) can
consume these flags directly.

Dev write restriction: only SYSTEM_RECORD under explicit
`X-Blackboard-Principal`; there is no way to create Finding-type records or
impersonate detector/profiler/gateway through HTTP. The Stage-4A
authorization hook runs BEFORE any replica prepare (403 without staging).

Replica status exposes operational facts only — health, availability,
storage error count/last error, committed/pending counts, divergence
history. **No trust scores, reliability dimensions or agent risk exist.**
Divergence — including the documented higher-version partial-commit
condition (`PRESERVED_DIVERGENT_HEAD`) — is reported verbatim; this stage
does not attempt automatic anti-entropy convergence.

## 6. Instrumentation

Backend counters surfaced via health/snapshot include
`partial_commit_count` (`partial_commit`),
`insufficient_quorum_read_count` (`read_insufficient_quorum`),
`quorum_failure_count` (`failed_quorum`),
`storage_failure_count` (`failed_storage`) plus commit/stale/conflict
counts and bounded latency series (per-replica prepare/commit, global
write/read). These are implementation instrumentation for later research —
explicitly NOT final performance results, and no dataset benchmarking was
run.

## 7. Verification summary

* Scientific non-interference (mandatory): identical full runner summary +
  SREP projection with integration disabled vs enabled on the bounded
  verified feature-store session; findings recorded = accepted counts;
  zero integration errors.
* No double processing: gateway control test shows ABM applied once while
  Blackboard recorded; equivalence test proves unchanged science.
* Leakage scans over every emitted event payload, snapshot projection and
  rejection history: recursive firewall clean; scenario identity absent;
  `session_trace` opaque digest remains the only session correlation.
* Chronology: single strictly-increasing sequence; PROPOSED→3 ACKs→COMMITTED
  ordering verified for sampled operations; BB-proposed precedes matching
  GATEWAY_ACCEPTED markers (documented policy).
* Persistence-through-API: committed record/version/hash survive full
  backend reconstruction; pending/aborted never appear committed.
* Direct/store compatibility: adapter-level proof that equivalent logical
  findings across modes yield equivalent records after excluding the
  operational `source_mode` provenance difference; live dual-mode science
  remains covered by existing replay-equivalence regressions.

## 8. Known limitations

1. Same as Stage-4A §21 (not BFT; single-process coordinator; partial-commit
   higher-version minority preserved but not auto-converged).
2. `blackboard-ops` events are visible only to clients of that namespace;
   browser dashboards receive BLACKBOARD_* events interleaved in their
   replay stream during runs.
3. Snapshot key cap (500 lexicographic) and listing page caps are research
   bounds, not scaling guarantees.
4. Dev-write endpoint is a testing convenience guarded by type/principal
   restrictions, not a security boundary (authentication is Stage 10).
