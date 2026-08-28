# Stage 7: React Orchestration Explainability

Status: implemented as a read-only frontend over the verified Stage-6
orchestration contracts and operational event stream.

> **React does not implement orchestration quorum. The Python backend is authoritative.**
>
> **Two matching votes in the browser do not constitute a frontend decision.**
>
> **Stage-6 routes are opaque adjudication outputs and are not yet executed.**
>
> **Orchestration history is bounded and non-durable; the visible retained history is not an all-time audit archive.**
>
> **Three-replica two-of-three quorum adjudication under authenticated orchestrator-message assumptions is not full Byzantine Fault Tolerance.**

## 1. Purpose And Verified Dependency

Stage 7 exposes Stage-6 operational state, participants, retained decisions, and
live chronology for research inspection. It is an observer: it validates and
formats backend facts but does not author requests, count votes into quorum,
select routes, verify HMACs, execute routes, or enforce network policy.

The dependency is the implemented Stage-6 surface documented in
`docs/stage6_orchestrator_quorum.md`: `orchestrator_a`, `orchestrator_b`, and
`orchestrator_c`; strict versioned health/status/decision contracts; bounded
in-memory decision history; and the fixed `orchestration-ops` event namespace.
Stage 7 mirrors those Python projections with strict Zod schemas in
`frontend/src/api/contracts.ts`. Contract drift, extra fields, foreign event
namespaces, malformed event payloads, and invalid outcome/route combinations are
rejected rather than interpreted by components.

## 2. Frontend Architecture And Navigation

`DashboardPage` remains the application shell and provides three tabs:

```text
Device View | Blackboard | Orchestration
```

Device View remains the default. Blackboard remains the independent Stage-5
storage view. Selecting Orchestration mounts `OrchestrationView`; leaving it
unmounts that view and closes its socket and reconnect timers.

| File | Stage-7 responsibility |
|---|---|
| `frontend/src/api/contracts.ts` | Strict Stage-6 REST and ten-event Zod contracts, outcome enums, and recursive metadata firewall |
| `frontend/src/api/client.ts` | Five typed orchestration GET methods through the shared validated client |
| `frontend/src/hooks/useOrchestration.ts` | REST state, filters, stale-request guards, fixed operational socket, event ring, reconnect/gap refresh |
| `frontend/src/components/orchestration/OrchestrationView.tsx` | Read-only composition root, notices, security/scope limits |
| `OrchestrationOverview.tsx` | Service facts, counters, aggregate operational latency, bounds |
| `OrchestratorCards.tsx` | Actual orchestrator operational status and bounded recent outcomes |
| `DecisionBrowser.tsx` / `DecisionDetailPanel.tsx` | Retained terminal decisions, filters, pagination, exact summaries, rejections, provenance |
| `LiveOrchestrationActivity.tsx` / `DecisionTrace.tsx` | Backend-sequenced chronology and request/round presentation grouping |
| `DigestField.tsx` / `decisionResult.tsx` | Exact digest inspection/copy and the terminal selected-route display rule |

The shared `ReplayContext` supplies one `ApiClient`. Stage-7 state is local to
`useOrchestration`; it is deliberately not merged into scientific replay state
or Blackboard state.

## 3. Exact Read Surface

With `VITE_API_BASE_URL` defaulting to `http://localhost:8000/api/v1`, Stage 7
consumes exactly these five orchestration GET forms:

| Client method | Method and path | Use |
|---|---|---|
| `getOrchestrationHealth()` | `GET /orchestration/health` | Service availability, required quorum, namespace, persistence flag, instrumentation |
| `getOrchestrationReplicas()` | `GET /orchestration/replicas` | All operational orchestrator cards and backend note |
| `getOrchestrationReplica(id)` | `GET /orchestration/replicas/{orchestrator_id}` | Typed individual status capability exposed by the hook |
| `listOrchestrationDecisions(filters)` | `GET /orchestration/decisions?outcome=&request_id=&limit=&offset=` | Retained filtered/paginated terminal decisions |
| `getOrchestrationDecision(id)` | `GET /orchestration/decisions/{decision_id}` | Authoritative terminal detail |

Path segments and query parameters are encoded by `ApiClient`. Every successful
response is schema-validated. The Stage-6 backend also has
`POST /orchestration/requests`, but Stage 7 has no client method, form, button,
or action console for it. No orchestration POST, PUT, PATCH, or DELETE is
exposed by this UI.

## 4. Socket Ownership And Namespace Isolation

`useOrchestration` is the fixed owner of one `ReplaySocket` while the
Orchestration tab is mounted. It always constructs that socket with replay ID
`orchestration-ops`, producing:

```text
ws://localhost:8000/api/v1/replays/orchestration-ops/events
```

The existing `ReplaySocket` transport is reused, but this is not the active
scientific replay socket owned by `useReplayEvents`. The backend gives
`orchestration-ops` its own monotonic sequence counter and replay-scoped broker
history. Operational publication therefore cannot increment or contaminate a
scientific replay sequence. The frontend contract additionally requires
`replay_id === "orchestration-ops"`; a scientific replay envelope is rejected.

## 5. REST Authority And WebSocket Chronology

REST owns current health, participant status, retained decision listings, and
terminal decision detail. WebSocket events are chronological observations only.
The live table sorts numerically by backend `sequence_number`; it does not sort
by orchestrator ID, arrival label, timestamp, or scientific value. The ten
accepted event facts are:

```text
ORCHESTRATION_REQUEST_RECEIVED
ORCHESTRATOR_PROPOSAL
ORCHESTRATOR_VOTE
ORCHESTRATOR_TIMEOUT
ORCHESTRATOR_DELAYED
ORCHESTRATOR_OMISSION
ORCHESTRATOR_STATUS
ORCHESTRATION_QUORUM_REACHED
ORCHESTRATION_NO_QUORUM
ORCHESTRATION_DECISION
```

An observed `ORCHESTRATION_DECISION` triggers a REST refresh. A quorum event is
displayed only as a backend-published fact; it does not create a frontend result.
Likewise, proposal counts, vote counts, and supporter array lengths are not used
to derive quorum or route selection.

Stage-6 publication chronology is request, observed-order proposals,
observed-order votes, timeout/delay/omission/status facts, quorum or no-quorum,
then final decision. Stage 7 preserves the sequence numbers it receives but
does not claim that its local stream contains every published fact.

## 6. Bounded History, Disconnects, And Gaps

The Stage-7 event ring is a dedicated FIFO capped by
`ORCHESTRATION_CLIENT_EVENT_LIMIT = 500`. On event 501, the oldest retained
event is evicted before the new event is appended; every later accepted event
continues oldest-first eviction. The array never exceeds 500, and
`localHistoryIncomplete` becomes sticky after the first eviction. Duplicate or
backward sequence numbers are dropped before insertion. The live activity view
initially renders the latest 120 matching events and can reveal 100 more at a
time; this does not expand the 500-event retention bound.

Backend REST decision history is separately bounded in memory (current default
`ORCHESTRATION_DECISION_HISTORY_LIMIT = 256`) and lost on process restart. The
listing contract requires `history_complete=false`, returns its actual
`history_limit` and `max_page_limit`, and reports `total_retained` only for the
retained matching scope. Pagination cannot recover decisions already evicted.
REST is authoritative for retained terminal state, not a complete all-time
archive or durable audit.

`ReplaySocket` preserves its last accepted sequence across native WebSocket
reconnects, drops duplicates/backward delivery, and attempts at most six
reconnects with bounded exponential delays (1, 2, 4, 8, 10, 10 seconds). Stage 7
does not clear already-loaded REST state or local events on error, close, gap,
or reconnect. It refreshes REST on an explicit server `gap_notice` and after a
successful reconnect. The sticky gap warning and local-eviction warning preserve
uncertainty; no missing event or lifecycle stage is fabricated.

Connection labels follow the transport lifecycle: `CONNECTING` is the initial
attempt, `OPEN` requires a native socket open, `RECONNECTING` requires
`ReplaySocket` to have scheduled a bounded retry, and `DISCONNECTED` means the
retry allowance is exhausted with no timer pending. A WebSocket `error` callback
alone does not establish that a retry exists. Optional generic
`onReconnectScheduled(attempt, delayMs)` and `onReconnectExhausted()` callbacks
expose this state without changing retry ownership, backoff, event sequencing,
terminal replay handling, or existing callback requirements.

There is no event-range REST endpoint and the socket supplies no frontend
backfill request. REST decision detail can recover a retained terminal result,
not missing chronology. A numerical sequence jump is not independently marked
as a gap by `ReplaySocket`; only an explicit server gap notice, local eviction,
or malformed-event error is visible. Therefore Stage 7 neither detects all
possible gaps nor backfills them.

## 7. Overview And Actual Orchestrators

The overview displays backend service status (`ok`, `degraded`, or `offline`),
available/total orchestrators, required quorum `2`, event namespace,
`decision_history_persistent=false`, instrumentation bounds, and counters for
round outcomes, accepted/rejected proposals and votes, authentication failures,
duplicates, conflicts, timeouts, delays, omissions, and disagreements.

Cards represent the actual Stage-6 orchestrators, not storage replicas. Each
shows `orchestrator_id`, operational health (`HEALTHY`, `DEGRADED`, or
`UNAVAILABLE`), availability, proposals emitted, votes issued, observed
authentication failures, timeout/omission counts, last error, and bounded recent
proposal/vote outcomes. These are operational facts, not trust, compromise,
credential, honesty, maliciousness, or Byzantine classifications.

Blackboard and orchestration remain separate systems:

| System | Identities | Evidence |
|---|---|---|
| Blackboard storage | `replica_a`, `replica_b`, `replica_c` | Replication/storage acknowledgements and records |
| Stage-6 orchestration | `orchestrator_a`, `orchestrator_b`, `orchestrator_c` | Authenticated opaque-route proposals and votes |

Blackboard ACKs and health are never counted as orchestration votes or agreement.
Stage 7 does not join, compare, or translate the two systems.

## 8. Proposals, Votes, Digests, And Summary Limits

Decision detail renders the exact summaries supplied by the backend. Proposal
summaries contain orchestrator/message IDs, proposed route, semantic
`proposal_digest`, per-message `message_hash`, backend authentication result,
policy ID/version, rationale code, and latency. Vote summaries contain
orchestrator/message IDs, `APPROVE|REJECT|ABSTAIN`, selected proposal digest,
per-message hash, backend authentication result, reason code, and latency.

These are projections, not complete signed messages. They omit sender sequence,
message timestamp, full authentication metadata/tag, and per-message provenance.
The card-level recent outcomes are even narrower. Consequently the UI can show
the backend's evidence summary but cannot independently reproduce authentication
or reconstruct omitted message fields.

`proposal_digest` identifies semantic support for one proposed route bound to
one request/version/round and request digest. It deliberately excludes sender
and message-specific metadata, so independent orchestrators proposing the same
route can share it. `message_hash` binds the complete individual unsigned
message plus authentication algorithm/key-identity header, so messages from
different senders normally differ even when their semantic proposal agrees.

`DigestField` shortens only the visual label and exposes/copies the exact full
backend value. React does not recompute request digests, proposal digests,
message hashes, authentication tags, or HMACs. No HMAC key, signing key, secret,
or tag is present in Stage-7 state or transport contracts.

## 9. Decision Browser And Terminal Rule

The browser filters by the five exact outcomes and optional `request_id`, and
paginates retained results with backend `limit`/`offset`:

```text
DECIDED
NO_QUORUM
TIMED_OUT
INSUFFICIENT_RESPONSES
REJECTED_REQUEST
```

The selected-route rule is exact: `authoritativeRoute()` returns a route only
when the authoritative terminal decision has `outcome === "DECIDED"` and a
non-empty backend `selected_route_id`. Every other outcome displays "No route
selected", even if local events contain matching proposals, matching APPROVE
votes, a quorum-reached fact, or a stale non-null route. Strict Zod validation
also requires a backend quorum and selected route for `DECIDED`, and rejects a
selected route or selected proposal digest on every non-`DECIDED` outcome.

The detail drawer shows the terminal reason; request/version/round/digests;
backend quorum fact; quorum and decision latency; logical context; completion;
participation arrays; exact proposal/vote summaries; bounded rejection evidence;
and backend provenance. It remains read-only.

## 10. Trace And Failure Semantics

`DecisionTrace` groups only events carrying both backend `request_id` and
`round_id`, using the presentation key `request_id + ":" + round_id`. Events in
each trace remain in backend sequence order. The selector retains only the most
recent 60 locally groupable traces. It does not infer missing request, proposal,
vote, quorum, or decision stages, and it does not turn a trace into terminal
authority.

Stage 7 preserves the Stage-6 participation distinctions:

| Fact | Meaning |
|---|---|
| Supporting | Backend reports valid support for the selected semantic proposal |
| Disagreeing | A valid vote rejected, abstained, or approved another proposal |
| Timed out | Work remained incomplete at the absolute round deadline |
| Delayed | Work remained incomplete when an already-valid quorum closed the round before deadline |
| Omitted | A responsive invocation explicitly produced no usable message |
| Unavailable | The replica was operationally unavailable before use |
| Rejected evidence | Backend rejected a proposal, vote, or round fact with phase/reason/detail |

These fields are displayed separately. Proposal evidence can remain present when
the vote phase fails; absence of one kind is not rewritten as another.

## 11. Latency And Research Interpretation

The overview displays backend instrumentation for `proposal_ms`, `vote_ms`,
`quorum_ms`, and `decision_ms` as count, mean, p50, p95, and max. An empty series
has only `count=0`; unavailable aggregates display `N/A`, not invented zeroes.
Decision detail also shows backend proposal/vote item latencies and terminal
quorum/decision latency. These are bounded operational implementation metrics,
not final DataSense research benchmarks or scientific conclusions. React only
formats their units.

## 12. Provenance, Firewall, And Authentication

Decision and event provenance are rendered as backend JSON. The shared recursive
firewall rejects keys, case-insensitively and after trimming, from the Stage-6
forbidden set: `label`, `label1`-`label4`, `label_full`, `is_attack`, `attack`,
`attack_category`, `attack_name`, `attack_names`, `target`, `targets`,
`target_device`, `whole_network_target`, `ground_truth`, `scenario_id`,
`scenario_name`, `scenario_ids`, `scenario_names`, and `filename`. The check is
on object keys, not words embedded in opaque scalar values. `session_trace` is
transported and displayed opaquely; React never decodes it into scenario,
filename, target, label, or ground-truth meaning.

Internal Stage-6 proposal/vote authentication is backend HMAC-SHA256 under an
independent runtime key per orchestrator. A verified result means key possession
and message integrity under those runtime-key assumptions; it does not prove
semantic truth or sender honesty. Keys are not persisted, logged, returned by
REST, or emitted as events, and Stage 7 has no verification material.

`X-Orchestration-Principal` on the backend POST is only an application/audit
identity under current development assumptions, not HTTP authentication or
proof of origin/honesty. Stage-7 GETs add no authentication header, and the
operational socket is subscribable under the same development assumptions. This
UI must not be described as an access-control boundary.

## 13. Exact Safety Boundary

Stage 6 requires two `APPROVE` votes from distinct known orchestrators for the
same accepted `proposal_digest`, bound to the same request/version/round and
verified request digest. Duplicate retransmission by one sender remains one
vote. The Python coordinator, not React, applies this rule and returns one
terminal decision.

Three-replica, two-of-three quorum adjudication under authenticated
orchestrator-message assumptions is not full Byzantine Fault Tolerance. It is
not PBFT, Byzantine consensus, or partition-wide distributed consensus. One
unavailable, omitted, delayed, or disagreeing participant can be tolerated only
when two valid participants agree. Two colluding authenticated orchestrators, a
compromised valid key, an arbitrary malicious majority, and network partitions
are not tolerated. Coordination and key ownership are single-process, rounds are
serialized by the coordinator, and operational/history state is in memory.

A selected opaque route is adjudication only. Stage 7 does not execute a
specialist agent, write Blackboard, mutate ABM/graphs/SREP, or produce or enforce
`ALLOW`, `MONITOR`, or `BLOCK` actions.

## 14. Preserved And Future-Stage Boundaries

- SREP remains exactly `DEVICE_ONLY`; the header and SREP panel badges are
  unchanged and orchestration facts are not fed into SREP.
- The Agent Trust Graph remains an `aria-disabled="true"` placeholder. No trust
  score, Agent Trust state, or L-ZTAF conclusion is displayed.
- Stage 8 remains responsible for specialist/five-agent execution and any
  authoritative action path. Stage 7 performs none.
- Stage 10 remains responsible for L-ZTAF, credential rotation/revocation,
  session re-admission, per-operation authorization, and Agent Trust.
- Stage 14 remains responsible for the integrated Attack Injection Engine and
  controlled compromise/fault evaluation. Stage-6 pass-through hook seams do
  not constitute that engine.

## 15. Tests And Current Results

The Stage-7 suites are:

| File | Tests | Coverage focus |
|---|---:|---|
| `frontend/src/test/orchestrationContracts.test.ts` | 65 | Exact schemas/enums/events/firewall; five GET-only methods; malformed transport rejection; no crypto, hash recomputation, quorum derivation, route derivation, or execution control |
| `frontend/src/test/orchestration.test.tsx` | 24 | Overview/cards; all outcomes and stale-route negatives; hashes/evidence; chronology/traces/failure distinctions; bounds; actual close/retry/reopen, exhaustion, socket/gap/eviction; dashboard regression |
| `frontend/src/test/replaySocket.test.ts` micro-closure addition | 1 | Existing six-attempt backoff remains bounded and reports retry exhaustion exactly once |

Verified on 2026-08-28:

```text
cd frontend
npm test
  -> 13 files passed; 251 tests passed
  -> 90 Stage-7/closure tests (65 contract + 24 component/hook + 1 transport lifecycle)
npm run type-check
  -> 0 errors
```

The decisive negative regressions prove that matching proposal events, two
matching APPROVE events, or a quorum-reached event cannot override a
non-`DECIDED` REST result or create a selected route.

## 16. Remaining Limitations

- Both the 500-event browser ring and bounded backend broker/history can omit
  earlier facts; neither is a durable or complete audit archive.
- Explicit gap notices and local eviction are preserved, but not every possible
  transport gap is detectable and no event backfill exists.
- Reconnect ends after six attempts; REST refresh is event/gap/reconnect/manual
  driven rather than continuous polling.
- Leaving the Orchestration tab discards its local event ring and gap flags;
  remounting starts a new local observation window and REST hydration.
- The decision list/detail can lose an older item to backend eviction or process
  restart between requests.
- Decision/event projections expose summaries, not complete signed messages,
  keys, durable provenance custody, or independent browser-verifiable HMAC
  evidence.
- Trace grouping requires both request and round IDs and retains only 60 local
  groups; it cannot reconstruct missing chronology.
- Operational health and authentication evidence do not establish trust,
  honesty, compromise status, Byzantine safety, or scientific validity.
- No Stage-8 execution, Stage-10 trust/access control, or Stage-14 attack engine
  is implemented by this frontend.
