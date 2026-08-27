# Stage 6: Three-Orchestrator Quorum Adjudication

## Purpose

Stage 6 adds a backend control-plane substrate that obtains independent opaque
route proposals and votes from exactly three orchestrators, then selects a route
only when two distinct authenticated orchestrators approve the same semantic
proposal. A selected route is an adjudicated routing decision only. It does not
execute a specialist agent and is not an `ALLOW`, `MONITOR`, or `BLOCK` action.

> **THIS IS NOT FULL BYZANTINE FAULT TOLERANCE.**

The implementation provides two-of-three quorum adjudication under explicit
authenticated orchestrator-message assumptions. It does not implement PBFT,
Byzantine consensus, or partition-wide distributed consensus.

## Architecture

The pure core is under `orchestration/`:

| Module | Responsibility |
|---|---|
| `contracts.py` | Frozen request, proposal, vote, rejection, summary, and decision contracts |
| `hashing.py` | Canonical JSON, request digest, semantic proposal digest, and full message hash |
| `authentication.py` | Per-sender HMAC-SHA256 signing and constant-time verification |
| `policy.py` | Mechanical Stage-6 opaque-route policy interface and default implementation |
| `replica.py` | Independent mutable orchestrator state machine |
| `coordinator.py` | Request-bound terminal rounds, two-phase collection, duplicate safety, and quorum |
| `hooks.py` | Identity/pass-through future evaluation seams |
| `instrumentation.py` | Thread-safe counters and bounded latency/rejection samples |
| `firewall.py` | Strict recursive evaluation-ground-truth rejection and request bounds |

`backend/app/services/orchestration_service.py` owns the three replicas,
coordinator, bounded decision history, event projection, and operational API
state. `backend/app/api/v1/endpoints/orchestration.py` is transport only.

## Two Different Replica Systems

Blackboard and orchestration are independent systems:

| System | Identities | Responsibility | Quorum evidence |
|---|---|---|---|
| Blackboard storage | `replica_a`, `replica_b`, `replica_c` | Replicated persistent records | Blackboard replication ACKs |
| Stage-6 orchestration | `orchestrator_a`, `orchestrator_b`, `orchestrator_c` | Opaque route proposals and adjudication | Authenticated orchestrator votes |

Blackboard ACKs are never orchestrator votes. Blackboard health is never used as
orchestrator agreement. Stage 6 does not write proposals or votes to Blackboard
and does not alter Stage-4 commit, read, repair, hashing, or persistence logic.

## Independent Orchestrators

`OrchestrationService` constructs exactly three separate
`OrchestratorReplica` objects in the fixed order above. Each owns a separate
lock, routing policy, hook instance, HMAC signer, sender sequence, availability,
counters, errors, and bounded recent-outcome deque. Shared immutable
configuration is allowed; mutable state is not aliased. Three single-worker
executors serialize work independently by orchestrator and bound worker count.

Operational health is only `HEALTHY`, `DEGRADED`, or `UNAVAILABLE`. It is not a
trust score, compromise classification, credential state, or Byzantine label.

## Request Contract And Digest

`OrchestrationRequestV1` has exact schema version
`orchestration_request_v1` and contains:

- opaque `request_id`, positive `request_version`, and opaque `round_id`;
- bounded `decision_kind` and one to 32 unique typed candidate routes;
- each candidate has a bounded opaque `route_id` and integer priority;
- optional logical timestamp, window, and opaque scope;
- source component and runtime-safe provenance.

The request digest is SHA-256 over canonical JSON. Mapping keys are sorted,
candidate routes are normalized by `route_id`, UTF-8 and compact separators are
fixed, and non-finite or non-JSON values are rejected. Candidate input order is
therefore non-semantic; candidate identifiers and priorities remain semantic.
Wall-clock receipt time, thread identity, and measured latency are not request
fields and cannot alter the digest. The canonical request is limited to 65,536
bytes, collections to 500 items, and nesting to 20 levels.

Reusing a request/version/round identity with different digest content is
rejected. A terminal round cannot produce another decision.

## Routing Policy Boundary

`RoutingPolicy.propose(request)` is injectable per replica. The production
`DeterministicPriorityPolicy` validates the already typed candidate set and
chooses minimum declared priority, then `route_id` as a deterministic tie-break.

This is a Stage-6 deterministic control-plane policy used to validate
replica/quorum mechanics. It is not AI reasoning, threat intelligence, risk
propagation analysis, trust/access control, or a scientific conclusion. Tests
inject fixed policies to create agreement and disagreement. Routes remain
opaque, for example `route_alpha`, `route_beta`, and `route_gamma`.

## Proposal Contract And Hashes

Every responsive orchestrator emits an immutable
`orchestrator_proposal_v1` message containing request/round binding, sender,
route, policy/rationale, sender sequence, timestamps, provenance, authentication
metadata, `proposal_digest`, and `message_hash`.

The two hashes have different meanings:

- `proposal_digest` hashes request identity/digest and selected route only. It
  deliberately excludes sender, message ID, timestamp, policy rationale, and
  sender sequence. Two senders supporting the same route for the same request
  therefore produce the same semantic digest.
- `message_hash` hashes the complete individual unsigned message plus its
  authentication algorithm/key identity header. Different senders or message
  metadata produce different message hashes.

Changing the route changes both semantic content and `proposal_digest`. A route
outside the declared candidate set cannot be accepted.

## Vote Contract

Every proposal-producing orchestrator can emit an immutable
`orchestrator_vote_v1` bound to the same request/version/round and request
digest. It identifies one accepted proposal digest and has explicit `APPROVE`,
`REJECT`, or `ABSTAIN` value, reason, sender sequence, full message hash,
provenance, and authentication metadata. Only `APPROVE` contributes to quorum.

Normal Stage-6 replicas approve the semantic proposal independently produced by
their own policy. One sender can contribute at most one effective vote per
round. A conflicting second vote is rejected and recorded as conflicting-vote
evidence; this is message-conflict detection, not a complete Byzantine detector.

## Internal Message Authentication

Each orchestrator receives an independent runtime key at service construction.
Production keys use `secrets.token_bytes(32)` and tests inject deterministic
test-only keys. No key is committed, persisted, logged, included in `repr`,
returned by REST, or published in events.

Proposals and votes are authenticated with HMAC-SHA256 over canonical message
content. Sender identity selects the verification key. Verification recomputes
the full message hash and uses `hmac.compare_digest` for the authentication tag.
Wrong key, sender mutation, route/digest mutation, and round mutation fail.

HMAC authenticates message origin and integrity under possession of the sender
key. It does not prove semantic truth. A compromised valid sender can emit a
false but authenticated message. Two colluding authenticated orchestrators can
form an incorrect majority. Key rotation, revocation, session re-admission,
agent trust, and per-operation Zero Trust policy are Stage-10 concerns and are
not implemented here.

## Quorum Rule

A final `DECIDED` result requires at least two `APPROVE` votes from distinct
known orchestrator IDs for the same accepted `proposal_digest`, all bound to the
same request/version/round and verified request digest. Duplicate retransmission
from one sender remains one vote.

- 3-0 agreement decides the common route.
- 2-1 agreement decides the majority route and records disagreement.
- Two agreeing responders can decide while one is unavailable, omitted, or
  sufficiently delayed.
- A three-way split produces `NO_QUORUM` and no route.
- One usable vote plus two deadline expiries produces `TIMED_OUT` and no route.
- Rejections and abstentions do not count as approvals.

There is no fallback. Response order, fastest sender, orchestrator A, lexical
route order, and the deterministic proposal policy cannot manufacture a final
winner without vote quorum.

## Round Lifecycle And Concurrency

A round is created, activated, and digest-checked atomically. The coordinator
uses one absolute deadline across both phases:

1. Submit one proposal operation to each operational orchestrator.
2. Validate each proposal as observed.
3. Submit that sender's vote only after its proposal is accepted.
4. Validate votes until quorum, exhaustion, or deadline.
5. Capture already-complete messages, classify missing participation, and make
   one terminal transition.
6. Build exactly one immutable decision.

Three orchestrator-specific single-worker executors prevent shared policy state
from concurrent re-entry and bound worker count. A slow third orchestrator does
not block a fast two-member quorum. Work still pending when quorum closes is
`delayed`, not falsely called a deadline timeout. Work pending after the
absolute deadline is `timed_out`. Late completion cannot enter the terminal
round, change the result, remove failure evidence, or create a second decision.
Concurrent rounds are serialized at the Stage-6 coordinator; this prioritizes
correctness and bounded work over throughput.

## Omission, Timeout, Delay, Unavailable, Disagreement

- **Omission:** a responsive invocation explicitly produced no usable message.
- **Timeout:** proposal or vote remained incomplete when the absolute deadline
  expired.
- **Delay:** work remained incomplete when an already-valid quorum closed the
  round before deadline.
- **Unavailable:** the replica was operationally marked unavailable before use.
- **Disagreement:** a valid vote rejected, abstained, or approved another
  semantic proposal.

These are separate decision fields and event facts, not a generic error.
Proposal evidence remains present when only the vote phase times out.

## Duplicate And Validation Safety

A bounded LRU-style cache tracks `(sender, message_id) -> message_hash`.
Identical retransmission is idempotent. Conflicting reuse of a message identity
is rejected. Per-round sender maps independently prevent multiple effective
proposals or votes. Validation records bounded structured evidence for unknown
senders, authentication/hash failure, wrong request/version/round/digest,
unknown routes/proposals, semantic digest mismatch, conflicts, and late messages.

## Final Decision

`OrchestrationDecisionV1` has exact schema version
`orchestration_decision_v1` and outcomes `DECIDED`, `NO_QUORUM`, `TIMED_OUT`,
`INSUFFICIENT_RESPONSES`, and `REJECTED_REQUEST`. It contains request identity
and digest, nullable selected route/digest, quorum requirement, observed-order
proposal/vote summaries with latency, bounded rejections, supporters,
disagreements, timeout/delay/omission/unavailable lists, quorum and decision
latency, reason, logical context, completion time, and provenance.

Only `DECIDED` may contain a selected route or proposal digest.

## Instrumentation And Memory Bounds

Instrumentation counters cover rounds, outcomes, proposals/votes accepted and
rejected, authentication failures, duplicates, conflicting votes, timeout,
delay, omission, and disagreement. Proposal, vote, quorum, and decision latency
series expose count, mean, p50, p95, and max. These are implementation metrics,
not final research metrics.

Explicit bounds cover decision history, round history, replay cache, per-round
rejections, per-replica recent outcomes, instrumentation rejection history,
latency samples, broker ring, and subscriber queues. API decision listing is
paginated and reports `history_complete=false`.

Decision and audit history is bounded in memory and is lost on process restart.
Stage 6 makes no durable all-time audit claim and does not misuse Blackboard as
orchestration persistence.

## Strict Ground-Truth Firewall

Requests, messages, decisions, and event projections recursively reject the
established forbidden keys plus scenario/file identity keys. The exact set is:

`label`, `label1`, `label2`, `label3`, `label4`, `label_full`, `is_attack`,
`attack`, `attack_category`, `attack_name`, `attack_names`, `target`, `targets`,
`target_device`, `whole_network_target`, `ground_truth`, `scenario_id`,
`scenario_name`, `scenario_ids`, `scenario_names`, and `filename`.

Opaque runtime IDs and traces are allowed; `session_trace` is never decoded.

## REST API And Caller Identity

The versioned surface is:

- `GET /api/v1/orchestration/health`
- `GET /api/v1/orchestration/replicas`
- `GET /api/v1/orchestration/replicas/{orchestrator_id}`
- `GET /api/v1/orchestration/decisions?outcome=&request_id=&limit=&offset=`
- `GET /api/v1/orchestration/decisions/{decision_id}`
- `POST /api/v1/orchestration/requests`

POST requires bounded `X-Orchestration-Principal`. The HTTP caller principal is
an application/audit identity under current development assumptions; HTTP
authentication is outside Stage 6. This is distinct from internal HMAC
authentication of orchestrator proposals and votes.

POST only adjudicates an opaque route. It does not execute an agent, write the
Blackboard, mutate ABM/graphs/SREP, or enforce network access.

## Events And Operational Namespace

Stage 6 extends the existing `ReplayEventType`, `EventEnvelopeV1`,
`ReplayController`, and bounded `EventBroker`; it does not create another event
framework. Explicit API requests publish to fixed `orchestration-ops`, which is
recognized by the existing WebSocket endpoint at:

`/api/v1/replays/orchestration-ops/events`

The namespace exists without a fake DataSense replay, has its own monotonic
sequence counter, is publicly subscribable under current development
assumptions, and cannot increment or contaminate a scientific replay sequence.

Event types are:

- `ORCHESTRATION_REQUEST_RECEIVED`
- `ORCHESTRATOR_PROPOSAL`
- `ORCHESTRATOR_VOTE`
- `ORCHESTRATOR_TIMEOUT`
- `ORCHESTRATOR_DELAYED`
- `ORCHESTRATOR_OMISSION`
- `ORCHESTRATOR_STATUS`
- `ORCHESTRATION_QUORUM_REACHED`
- `ORCHESTRATION_NO_QUORUM`
- `ORCHESTRATION_DECISION`

Publication chronology is request, observed-order proposal facts,
observed-order vote facts, timeout/delay/omission/status facts, quorum or
no-quorum fact, then final decision. Sequence numbers strictly increase in
publication order. Concurrent completion order is not forced into A/B/C order.
Missing proposals and votes are never fabricated. The bounded broker and
in-memory decision API are not a complete durable event archive.

## Fault-Hook Seams

`ORCHESTRATOR_MESSAGE` and `ORCHESTRATOR_VOTE` hook points exist for future
evaluation attachment. Production `OrchestratorHooks` is pass-through and has
no mutation, scheduler, attack family, random seed, or activation logic. Tests
inject local delays and omissions only to verify failure handling. This is not
the Stage-14 Attack Injection Engine.

## Legacy Scaffold Separation

Historical prototype modules remain under `agents/`, `srep/workflow_engine.py`,
`trust/`, and `security/`. The old Detection/Triage/Response workflow and its
title-case Allow/Monitor/Block strings are imported only by root prototype
`main.py`, not by `backend/`, `pipeline/`, `simulation/`, `blackboard/`, or
`srep/device_srep.py`.

These files are legacy pre-Stage-1 scaffolding. They are not part of the
verified DataSense replay path, are not evidence of the five-agent architecture,
are not authoritative enforcement, are not L-ZTAF, and are not an integrated
Attack Injection Engine. Stage 6 neither modifies nor imports them. No
authoritative Stage-8 enforcement implementation exists in the verified runtime.

## Stage Boundaries And Limitations

- Stage 7 orchestration UI is not implemented. The frontend change only accepts
  the new event enum values.
- Stage 8 specialist execution is not implemented. Selected routes are opaque.
- No authoritative `ALLOW`, `MONITOR`, or `BLOCK` path is implemented.
- Stage 10 L-ZTAF, rotating/revoked credentials, agent trust, and Agent Trust
  Graph are not implemented. SREP remains `DEVICE_ONLY`.
- Watchdog, drift, recovery, reload, rejoin, and recovery metrics are absent.
- No integrated Stage-14 Attack Injection Engine exists. Primitive historical
  security helpers remain outside the verified runtime.
- One unavailable, omitted, delayed, or disagreeing member can be tolerated
  when the other two authentically agree. Two colluding authenticated senders,
  forged output using a compromised valid key, arbitrary malicious majority,
  and network partitions are not tolerated.
- Coordination is single-process and history is non-durable.

## Tests

Focused tests are under `tests/unit/orchestration/` and
`tests/integration/backend/orchestration/`. They cover contracts, hashing,
semantic versus full hashes, HMAC tampering, replica independence, healthy and
degraded quorum matrices, no fallback, duplicate/conflicting messages,
wrong-round and unknown-route rejection, phase-specific timeouts, terminal late
messages, request identity conflicts, concurrency, observed completion order,
bounded state, nested leakage, REST, events, WebSocket subscription, and
scientific sequence isolation. Stage-4 and full backend/frontend regressions
remain mandatory; exact executed results are recorded in `tests.md`.
