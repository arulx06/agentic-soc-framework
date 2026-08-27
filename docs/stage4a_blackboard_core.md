# Stage 4A — Replicated Blackboard Core

Status: implemented on branch `feat/blackboard` (uncommitted at delivery).
Scope: **core replicated Blackboard backend only**. Integration with the
Finding Gateway, Stage-3 event stream, FastAPI surface and React dashboard
is deliberately deferred to Stage 4B.

---

## 0. Fault-model banner

> ## THIS IS NOT FULL BYZANTINE FAULT TOLERANCE.
>
> The Blackboard is a **quorum-replicated coordination substrate** with a
> **two-of-three compatible-acknowledgement commit policy** operating under
> explicit **authenticated, fail-stop replica assumptions**.
>
> It is **not** PBFT, not Byzantine consensus, and implements no BFT
> protocol. No such claim appears anywhere in code or documentation, and
> none may be made in the thesis for this mechanism.

### What Stage 4A tolerates

| Failure | Behaviour |
| --- | --- |
| Replica crash / process restart | Committed state survives (per-replica SQLite); pending state never becomes committed |
| One replica unreachable during prepare | Other two may still form quorum; unavailable replica reported explicitly |
| One replica fails during the COMMIT phase | Two durable commits still form a **committed quorum** → `COMMITTED` with the missed replica marked `DIVERGENT_REQUIRES_RECONCILIATION`; if only ONE commit lands the outcome is explicitly `PARTIAL_COMMIT` (never `COMMITTED`), and zero commits is `FAILED_STORAGE` |
| Competing proposals (same key, same next version) | Deterministic compare-and-stage: one wins the slot, loser gets explicit `REJECT_CONFLICT`; committed history can never fork |
| Caller proposing against an older version | Explicit `REJECTED_STALE` with structured expected/current version |
| Storage error on one replica | Mapped to an explicit `STORAGE_ERROR` acknowledgement; never inferred from exception absence |

### What Stage 4A does NOT tolerate

* **Byzantine behaviour of a quorum**: two replicas returning fabricated
  acknowledgements with matching hashes will be believed. The design
  assumes replicas compute protocol steps honestly (`authenticated /
  fail-stop`). A three-way equivocation split is *detected*
  (`INCOMPATIBLE_PREPARED_ACKS`) and refuses to commit, but a colluding
  fake majority cannot be outvoted.
* **Network partitions** between coordinator and replicas: there is one
  coordinator process per deployment; partition tolerance is out of scope.
* **Semantic falsity** of committed content (see §15).

---

## 1. Architecture

```
blackboard/
    __init__.py        public surface + NOT-BFT banner
    settings.py        bounded-memory knobs, runtime paths, UTC helpers
    hashing.py         canonical JSON serialization, SHA-256 content hash
    contracts.py       versioned record/result/ack schemas, record-type
                       registry, ground-truth firewall, integrity binding
    storage.py         per-replica SQLite store (atomic transactions)
    replica.py         independent replica state machine + health
    authorization.py   injectable READ/WRITE authorization interface
    hooks.py           future fault-hook seams (identity default)
    instrumentation.py bounded counters / latency series / history rings
    coordinator.py     3-replica quorum lifecycle + consistent reads +
                       explicit repair + pure quorum combinator
```

Runtime layout (generated, gitignored):

```
runtime/blackboard/replica_a.db
runtime/blackboard/replica_b.db
runtime/blackboard/replica_c.db
```

The three stores are physically separate SQLite databases with separate
connections and locks. Independence is structural, not simulated by a
shared table carrying a `replica_id` column.

## 2. Record contract (`blackboard_record_v1`)

Immutable frozen pydantic model with exactly the logical fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | literal `"blackboard_record_v1"` |
| `record_id` | immutable identity of ONE concrete version: `{record_key}#v{record_version}#{content_hash[:12]}` |
| `record_key` | identity of ONE logical item (charset `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$`) |
| `record_type` | registry enum (below) |
| `record_version` | monotonically increasing version, ≥ 1 |
| `logical_timestamp` / `window_id` | replay-logical time (optional, validated ISO-8601-with-offset / non-negative) |
| `author_id` / `source_component` | provenance-of-authorship identifiers |
| `payload` / `provenance` | content dicts (firewall-checked) |
| `content_hash` | canonical SHA-256 over the hashed projection (§4) |

Identity semantics are strict:

* `record_key` = identity of the logical item;
* `record_version` = which generation of that item;
* `record_id` = the immutable concrete (item, version, content) triple.

There is no mutable object whose identity changes as it is overwritten.
Operational stamps (`committed_at_utc`, `operation_id`, latencies) live in
storage/results only — never on the record, never in the hash.

Every construction, validation and storage load re-verifies that
`content_hash` matches a recomputation over the hashed projection AND that
`record_id` matches its derivation (`RecordIntegrityError` otherwise).
Post-construction mutation of the payload dict is therefore detectable;
frozen pydantic plus integrity binding give value-object semantics.

## 3. Record-type registry

Stage 4A registers only categories grounded in existing backend
capabilities:

```
NETWORK_FINDING_RECORD        BEHAVIOR_FINDING_RECORD
DEVICE_STATE_RECORD           DEVICE_RISK_SNAPSHOT_RECORD
DEVICE_ONLY_SREP_RECORD       SYSTEM_RECORD
```

Unknown types are rejected at draft construction. Deliberately absent
(future stages must extend the registry explicitly): threat intelligence,
orchestrator votes, trust/access decisions, agent trust, watchdog,
recovery, attack injection, ALLOW/MONITOR/BLOCK.

## 4. Ground-truth firewall

Records reuse the Stage-3 recursive checker
(`backend.app.contracts.common.find_ground_truth_violations`) over payload
and provenance — top-level fields, nested dicts, lists of dicts, Pydantic
models and object `__dict__`s — and extend it with Blackboard-specific
forbidden keys:

```
scenario_id  scenario_name  scenario_ids  scenario_names  filename
```

Rationale: a DataSense scenario name itself encodes category/target
(`attack_recon_host-disc-udp-ping_soil-sensor`), so raw scenario identity
must never enter a record. Runtime correlation uses the existing opaque
non-reversible digest (`session_trace`, defined in `pipeline/findings.py`).
Legitimate model-output vocabulary (`attack_probability`,
`predicted_class='attack'`) remains allowed exactly as in Stage 3; no
existing leakage protection was weakened.

Violations raise with the offending paths; replicas independently re-check
the firewall at PREPARE (defence in depth).

## 5. Canonical serialization and hashing

`blackboard/hashing.py` defines determinism:

* `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` → UTF-8 bytes;
* dictionary insertion order, object identity, thread scheduling and
  formatting options cannot influence output;
* `NaN`/`Infinity` and non-JSON-serializable values are rejected;
* list order is preserved and therefore semantic (documented).

`content_hash = SHA-256(canonical_json({exactly HASHED_FIELDS}))` where
`HASHED_FIELDS` = schema_version, record_key, record_type, record_version,
logical_timestamp, window_id, author_id, source_component, payload,
provenance. Replica-local operational fields (operation ids, ack latency,
health, wall-clock stamps) are excluded structurally. Tests prove:
same logical content ⇒ same hash under key reordering; any protected-field
mutation ⇒ different hash; operational context changes ⇒ identical hash.

Limitation: floats use CPython shortest-round-trip repr (deterministic for
a given interpreter class); cross-language stability should quantize.

## 6. Version rules

Optimistic concurrency (compare-and-stage):

```
new key:                 head absent ≡ head 0 → only version 1 acceptable
existing committed N:    only version N+1 acceptable
proposed ≤ N:            REJECT_STALE (structured: key, expected,
                         current_version_at_replica, reason)
proposed > N+1:          REJECT_SCHEMA ("expected_version ahead")
```

Heads advance only inside the commit transaction. There is no wall-clock
last-write-wins anywhere.

## 7. Stale writes

A stale proposal (e.g. current=5, expected=3) is rejected before any
staging occurs; every rejecting ack carries `current_version_at_replica`;
the global result is `REJECTED_STALE` with reason text containing the
current version. Committed state and heads remain byte-identical (tested).

## 8. Conflicts

A conflict is competing content for the SAME next version, distinct from
staleness:

* **Within a replica slot**, `pending_prepares` holds a lease keyed
  `(record_key, record_version)` inside `BEGIN IMMEDIATE` transactions.
  A different-content proposal while a live lease exists →
  `REJECT_CONFLICT`. Identical-content restaging is idempotent. An expired
  lease (`pending_lease_seconds`, default 300 s) may be taken over
  (`PREPARED_LEASE_TAKEOVER`).
* **Across replicas**, prepared acknowledgements group by the full
  compatibility identity `(record_id, record_key, record_version,
  content_hash)`; incompatible groups are never merged (§10).
* Committed history is fork-free: `PRIMARY KEY (record_key,
  record_version)` plus the head CAS make two committed values for one
  slot impossible.

Global outcomes: `COMMITTED`, `PARTIAL_COMMIT`, `REJECTED_STALE`,
`REJECTED_CONFLICT`, `REJECTED_SCHEMA`, `REJECTED_AUTHORIZATION`,
`FAILED_QUORUM`, `FAILED_STORAGE`.

## 9. Prepare / commit / abort lifecycle

Naive "write thrice, count successes" is NOT used. Each write runs:

```
PROPOSE → authorize → validate/hash/size-check (REJECTED_SCHEMA path)
        → PREPARE on all healthy replicas
              (atomic CAS stage into pending_prepares; invisible to reads)
        → collect explicit ACKs
        → quorum?  yes → COMMIT each prepared member (atomic promote
                           pending→committed + head advance);
                      abort staging of incompatible losers;
                      best-effort abort of non-prepared members
                   no  → ABORT every prepared staging; FAILED_QUORUM
```

A prepared value is NEVER visible as committed: reads consult only the
committed table. Failed quorum leaves zero committed rows and zero pending
rows on honest members (tested), across restart (tested).

Writes within one coordinator serialize behind a lifecycle lock so
competing threads resolve deterministically; separate coordinators sharing
the stores are protected by the SQLite-level CAS.

## 10. Acknowledgements and the 2-of-3 policy

Every replica call returns an explicit `ReplicaAckV1`
(`schema_version="blackboard_ack_v1"`): operation_id, replica_id,
operation_kind, `ack_status`, reason, record_id/key/version/content_hash,
current_version_at_replica, logical_timestamp, latency_ms, observed_at_utc.
Statuses: `ACK_PREPARED`, `ACK_COMMITTED`, `ABORTED`, `REJECT_STALE`,
`REJECT_CONFLICT`, `REJECT_SCHEMA`, `REJECT_INTEGRITY`,
`REJECT_AUTHORIZATION`, `UNAVAILABLE`, `STORAGE_ERROR`. Status is never
inferred from absence of an exception.

Commit requires **≥ 2 compatible prepared ACKs** (agreement on
record_id, record_key, record_version, content_hash) to ENTER the commit
phase, and then **≥ 2 compatible ACK_COMMITTED acknowledgements to report
`COMMITTED`**: a prepared quorum is permission to attempt the commit, not
proof of durable two-replica state.

```
3 compatible prepares → 3 commits → COMMITTED
2 compatible prepares → 2 commits → COMMITTED;
    the third replica is reported according to its actual state
    (unavailable / not-prepared / aborted / divergent as applicable)
2 compatible prepares → 1 commit  → PARTIAL_COMMIT (NOT COMMITTED)
2 compatible prepares → 0 commits → FAILED_STORAGE
1 compatible prepare              → FAILED_QUORUM
0                                 → FAILED_QUORUM
incompatible split                → FAILED_QUORUM (INCOMPATIBLE_PREPARES)
```

The pure combinator `evaluate_quorum()` is unit-tested for every case
above; the largest compatible group wins ties deterministically
(sort by −size, then content_hash). The global result carries the
acknowledgements actually received.

**Readiness invariant:** `WriteOutcome.COMMITTED ⇒ at least two compatible
ACK_COMMITTED acknowledgements`. It is enforced in the coordinator outcome
logic, asserted as a hard backstop inside instrumentation for every result,
and guarded by a regression test spanning all success paths (healthy,
prepare-unavailable, one-commit-failure, hook-unavailable). Stage 4B's
future `BLACKBOARD_WRITE_COMMITTED` events may therefore be emitted only
from results satisfying this invariant.

## 11. Partial-commit handling

The commit phase is counted separately from the prepare phase:

* **≥ 2 durable commits** → `COMMITTED`; any prepared replica that missed
  its commit gets `replica_sync = DIVERGENT_REQUIRES_RECONCILIATION`,
  health `DIVERGED`, a divergence history entry, and is named in
  subsequent reads.
* **Exactly 1 durable commit** → `PARTIAL_COMMIT` — an explicit
  indeterminate, non-success outcome. The result preserves operation_id,
  full record identity, the successful commit replica(s), the failed commit
  replica(s), `replica_sync` states and a reconciliation reason. The single
  committed replica is NEVER erased merely to regain symmetry, and the
  outcome can never retroactively become `COMMITTED`.
* **0 durable commits** → `FAILED_STORAGE`; nothing committed anywhere;
  stranded staging remains invisible until lease expiry or explicit
  operational `abort()`.

After restart a partial-commit state stays partial: majority reads keep
returning the last quorum-committed value and name the ahead-replica as
divergent; the higher-version singleton is never served as authoritative.

Repair is explicit and operational ONLY:
`resync_replicas_from_majority(principal, key)` copies the majority record
into lagging replicas via forward-only upserts and judges alignment on the
replica HEAD (not a single slot). A replica whose head holds newer
committed data than the majority keeps that data (`PRESERVED_DIVERGENT_HEAD`)
— repair refuses to roll commits back. Reads never repair silently.
Known limitation: when a partial-commit minority holds a higher version,
the substrate detects and reports the divergence but cannot converge the
majority onto it without operator intervention; automatic anti-entropy is
future work.

## 12. Read consistency

Coordinator reads query ALL replicas' committed state and compare
`(record_version, content_hash)` — never first-response-wins. Value AND
absence are both subject to quorum discipline (`quorum_size = 2`):

| Responses observed | Outcome |
| --- | --- |
| 3 replicas, identical value | `CONSISTENT` (record returned) |
| 2 identical + 1 unavailable | `DEGRADED_CONSISTENT` (record returned; unavailable named) |
| 2 identical + 1 divergent/lagging | `DEGRADED_CONSISTENT` (divergent named, health marked) |
| 2 responsive, disagreeing | `INCONSISTENT` — `record=None` |
| 3-way split | `INCONSISTENT` — `record=None` |
| 1 value + 2 unavailable | `INSUFFICIENT_QUORUM` — `record=None` |
| 1 responder only (any answer) | `INSUFFICIENT_QUORUM` — `record=None` |
| 3 agree record absent | `NOT_FOUND` |
| 2 agree absent + 1 unavailable | `NOT_FOUND` (degraded metadata) |
| 1 absent + 2 unavailable | `INSUFFICIENT_QUORUM` |
| 0 responsive | `UNAVAILABLE` |

A single responsive replica is reported in observations/debug metadata but
its value — or its absence — is never authoritative Blackboard state.
Health mutation happens only on conclusive `DEGRADED_CONSISTENT` outcomes
(minority/lagging replicas marked `DIVERGED`); inconclusive reads report
without blaming. Stored rows are re-verified on load (hash + byte-level
canonical drift), so tampered persistence surfaces as an integrity
observation rather than trusted data.

## 13. Persistence & restart

Per-replica SQLite (`journal_mode=WAL`, `synchronous=FULL`,
`busy_timeout=5000`), all transitions atomic via `BEGIN IMMEDIATE`.
Tables: `committed_records` (PK `(key, version)`, unique record_id),
`key_heads`, `pending_prepares` (leased), `meta`.

Restart tests prove: committed keys/versions/hashes/payloads identical
after destroying and rebuilding the coordinator; pending staging persists
but is never promoted (a conflicting challenger commits globally via the
other two replicas while the lease-holder stays explicitly behind until
repaired); aborted proposals stay absent; failed-quorum debris leaves no
committed rows.

## 14. Authorization interface (authentication is NOT implemented)

The Blackboard is evaluated under an **assumed authenticated /
fail-stop replica/principal model**. Stage 4A does not itself implement
credential authentication: principals are plain caller-supplied strings.
The `Authorizer` is an **authorization interface only** — it decides
READ/WRITE permission for an already-assumed identity and authenticates
nobody. In particular `AllowAllDevelopmentAuthorizer` is a deterministic
development convenience that grants everything to everyone; it performs no
verification of any kind and must never be described as authentication.
Rotating credentials, revocation, trust vectors, session-key management,
re-admission, authentication/session management are Stage-10 (L-ZTAF)
scope and intentionally absent here.

Injectable surface:
`Authorizer.decide(AuthzRequest(principal, operation, record_type,
record_key)) -> AuthorizationDecision(allowed, policy_id, reason)` around
READ and WRITE, plus the deny-closed `PrincipalPolicyAuthorizer` used in
tests. Denials produce `REJECTED_AUTHORIZATION` / `AUTHORIZATION_REJECTED`
and change no state.

## 15. Methodological distinction (documented, NOT implemented)

**Logical memory poisoning** — a future compromised-but-authenticated
author writes semantically false content through the legitimate API; all
replicas correctly store identical falsehood. Replication, hashing and
read-consistency cannot detect semantic falsity; they guarantee only that
replicas agree on whatever was authored. Stage 4A preserves this study
surface (records carry author_id/source_component/provenance).

**Replica corruption** — a future evaluation manipulates one storage
replica to return stale/altered/inconsistent state. Divergence marking,
integrity-on-load verification, majority reads and explicit resync exist
precisely so Stage 14 can study detection. Neither attack is implemented
or exercised outside test doubles.

## 16. Future fault-hook seams

`hooks.py` exposes three seam points — `BLACKBOARD_WRITE`,
`BLACKBOARD_READ`, `REPLICA_WRITE` (with operation kinds PREPARE / COMMIT /
ABORT / EXTERNAL_UPSERT / READ).

Stated accurately:

* the **default production hook set is strict identity/pass-through** —
  `observe()` is a no-op and `intercept_record()` returns `None`; nothing
  is intercepted in production behaviour;
* the hook **interface permits externally supplied test/evaluation code**
  to intercept operations or substitute records at a single replica
  (`intercept_record()` explicitly supports this; raising
  `HookUnavailableError` simulates unavailability);
* **no attack family, mutation policy, activation scheduler, seed
  handling, success condition or Attack Injection Engine exists in
  Stage 4A** — those are Stage-14 constructs that would attach through
  this seam;
* production code never raises `HookUnavailableError` and never passes a
  substitution; it only maps externally raised ones to explicit
  acknowledgements.

## 17. Concurrency

* Coordinator lifecycle lock serializes propose-phase decisions per
  process (deterministic conflict resolution);
* per-replica locks + `BEGIN IMMEDIATE` CAS protect against concurrent
  coordinators sharing stores;
* committed slots are unique by `(key, version)` — two writers can never
  both own version N+1 (tested with thread pools and duelling
  coordinators; optimistic retry converges without lost updates or gaps).

## 18. Memory bounds (all configurable via `BlackboardSettings`)

| Structure | Bound (default) |
| --- | --- |
| Recent global operations ring | 256 trimmed summaries (no payloads) |
| Recent rejections ring | 64 |
| Latency samples per series | 512 |
| Per-replica divergence history | 16 entries |
| Record size | reject > 256 KiB canonical |
| Pending leases | expire after 300 s |

No unbounded list accumulates acknowledgements or history.

## 19. Instrumentation (implementation metrics only — NOT research metrics)

Counters: writes started/committed/committed-with-divergence/**partial
commits**/stale/conflict/schema/integrity/authorization rejections,
quorum failures, storage failures, aborts, resyncs, read outcomes
(consistent/degraded/not-found/**insufficient-quorum**/inconsistent/
unavailable/authz-denied). Latency series (p50/p95/max/mean over capped
samples): per-replica prepare & commit, global write, global read. Snapshot
exposed via `coordinator.instrumentation.snapshot()`. The instrumentation
layer additionally asserts the COMMITTED⇒committed-quorum invariant on
every recorded result. No dataset benchmarking is performed or claimed.

## 20. Test coverage map

`tests/unit/blackboard/` (124 tests): contracts/registry/firewall/
integrity (`test_contracts.py`), hashing determinism
(`test_hashing.py`), physical + state independence and exactly-three
(`test_replica_independence.py`), versions/stale/conflicts/leases
(`test_versioning.py`), quorum combinator + lifecycle + incompatible acks
(`test_quorum_lifecycle.py`), **commit-phase durability matrix + restart
after partial commit + COMMITTED⇒≥2-ACK_COMMITTED invariant**
(`test_commit_quorum.py`), partial commit + explicit repair
(`test_partial_commit_repair.py`), **quorum-disciplined read outcomes incl.
INSUFFICIENT_QUORUM** (`test_reads.py`), restart/persistence
(`test_persistence_restart.py`), authorization (`test_authorization.py`),
hook seams + identity default (`test_fault_hooks.py`), concurrency
(`test_concurrency.py`), bounds + instrumentation
(`test_bounded_history.py`).

## 21. Limitations

1. Not BFT (§0): an agreeing fabricated majority would be believed.
2. Single coordinator process; multi-coordinator safety relies on SQLite
   CAS/leases, not distributed consensus.
3. Sequential replica dispatch — latency, not correctness, trade-off.
4. Float serialization is interpreter-deterministic, not cross-language.
5. Lease expiry uses wall clock; a paused-clock host could delay takeover.
6. Repair covers single-key catch-up from a compatible majority and judges
   alignment per replica HEAD; full anti-entropy (multi-key scan) is
   future work. A partial-commit minority holding a higher version is
   preserved and reported but cannot be automatically converged (§11).
7. `SYSTEM_RECORD` currently has no internal writer — the substrate is
   generic until Stage 4B wires producers.
8. No automatic semantic-falsity detection (impossible at this layer).
9. Authentication is assumed, not implemented (§14); principals are
   unverified strings under the Stage-4A evaluation model.
