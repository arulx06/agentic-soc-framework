import { afterEach, describe, expect, it, vi } from "vitest";
import {
  MessageRejectionV1Schema,
  ORCHESTRATION_FORBIDDEN_KEYS,
  OrchestrationCountersV1Schema,
  OrchestrationDecisionListingBoundsV1Schema,
  OrchestrationDecisionListingV1Schema,
  OrchestrationDecisionV1Schema,
  OrchestrationEventEnvelopeV1Schema,
  OrchestrationEventPayloadSchemas,
  OrchestrationHealthV1Schema,
  OrchestrationInstrumentationBoundsV1Schema,
  OrchestrationInstrumentationV1Schema,
  OrchestrationLatenciesV1Schema,
  OrchestrationLatencySummaryV1Schema,
  OrchestrationNoQuorumPayloadV1Schema,
  OrchestrationOutcomeSchema,
  OrchestrationOutcomeValues,
  OrchestrationQuorumReachedPayloadV1Schema,
  OrchestrationRequestReceivedPayloadV1Schema,
  OrchestratorDelayedPayloadV1Schema,
  OrchestratorHealthSchema,
  OrchestratorHealthValues,
  OrchestratorListingV1Schema,
  OrchestratorOmissionPayloadV1Schema,
  OrchestratorProposalEventPayloadV1Schema,
  OrchestratorRecentOutcomeV1Schema,
  OrchestratorStatusEventPayloadV1Schema,
  OrchestratorStatusV1Schema,
  OrchestratorTimeoutPayloadV1Schema,
  OrchestratorVoteEventPayloadV1Schema,
  ProposalSummaryV1Schema,
  VoteSummaryV1Schema,
  VoteValueSchema,
  VoteValueValues,
  hasForbiddenOrchestrationKey,
} from "../api/contracts";
import { ApiClient } from "../api/client";
import { ContractValidationError } from "../api/validation";
import clientSource from "../api/client.ts?raw";
import orchestrationHookSource from "../hooks/useOrchestration.ts?raw";
import decisionBrowserSource from "../components/orchestration/DecisionBrowser.tsx?raw";
import decisionDetailSource from "../components/orchestration/DecisionDetailPanel.tsx?raw";
import decisionResultSource from "../components/orchestration/decisionResult.tsx?raw";
import decisionTraceSource from "../components/orchestration/DecisionTrace.tsx?raw";
import digestFieldSource from "../components/orchestration/DigestField.tsx?raw";
import liveActivitySource from "../components/orchestration/LiveOrchestrationActivity.tsx?raw";
import overviewSource from "../components/orchestration/OrchestrationOverview.tsx?raw";
import orchestratorCardsSource from "../components/orchestration/OrchestratorCards.tsx?raw";
import orchestrationViewSource from "../components/orchestration/OrchestrationView.tsx?raw";

const ORCHESTRATOR_IDS = [
  "orchestrator_a",
  "orchestrator_b",
  "orchestrator_c",
] as const;

const EXPECTED_FORBIDDEN_KEYS = [
  "label",
  "label1",
  "label2",
  "label3",
  "label4",
  "label_full",
  "is_attack",
  "attack",
  "attack_category",
  "attack_name",
  "attack_names",
  "target",
  "targets",
  "target_device",
  "whole_network_target",
  "ground_truth",
  "scenario_id",
  "scenario_name",
  "scenario_ids",
  "scenario_names",
  "filename",
] as const;

function makeCounters(overrides: Record<string, unknown> = {}) {
  return {
    rounds_started: 4,
    decisions_reached: 1,
    no_quorum: 1,
    timed_out: 1,
    insufficient_responses: 1,
    proposals_received: 8,
    proposals_rejected: 1,
    votes_received: 7,
    votes_rejected: 1,
    authentication_failures: 1,
    duplicate_messages: 1,
    conflicting_votes: 1,
    orchestrator_timeouts: 1,
    orchestrator_delays: 1,
    orchestrator_omissions: 1,
    orchestrator_disagreements: 1,
    ...overrides,
  };
}

function makePopulatedLatency(overrides: Record<string, unknown> = {}) {
  return {
    count: 3,
    mean_ms: 4.25,
    p50_ms: 4,
    p95_ms: 7.5,
    max_ms: 8,
    ...overrides,
  };
}

function makeLatencies(populated = false) {
  const value = populated ? makePopulatedLatency() : { count: 0 };
  return {
    proposal_ms: value,
    vote_ms: value,
    quorum_ms: value,
    decision_ms: value,
  };
}

function makeRejection(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "orchestrator_message_rejection_v1",
    phase: "PROPOSAL",
    reason_code: "AUTHENTICATION_FAILED",
    orchestrator_id: "orchestrator_a",
    message_id: "message-1",
    detail: "backend rejection detail",
    ...overrides,
  };
}

function makeInstrumentation(overrides: Record<string, unknown> = {}) {
  return {
    counters: makeCounters(),
    latencies: makeLatencies(),
    recent_rejections: [],
    bounds: { latency_samples: 256, recent_rejections: 64 },
    ...overrides,
  };
}

function makeHealth(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "orchestration_health_v1",
    status: "ok",
    orchestrators_available: 3,
    orchestrators_total: 3,
    required_quorum: 2,
    event_namespace: "orchestration-ops",
    decision_history_persistent: false,
    instrumentation: makeInstrumentation(),
    ...overrides,
  };
}

function makeProposal(overrides: Record<string, unknown> = {}) {
  return {
    orchestrator_id: "orchestrator_a",
    message_id: "proposal-message-a",
    proposed_route_id: "route_alpha",
    proposal_digest: "proposal-digest-alpha",
    message_hash: "proposal-message-hash-a",
    authentication_verified: true,
    policy_id: "opaque-route-policy",
    policy_version: "1",
    rationale_code: "LOWEST_PRIORITY",
    latency_ms: 1.25,
    ...overrides,
  };
}

function makeVote(overrides: Record<string, unknown> = {}) {
  return {
    orchestrator_id: "orchestrator_a",
    message_id: "vote-message-a",
    selected_proposal_digest: "proposal-digest-alpha",
    vote: "APPROVE",
    message_hash: "vote-message-hash-a",
    authentication_verified: true,
    reason_code: "SUPPORTS_PROPOSAL",
    latency_ms: 2.5,
    ...overrides,
  };
}

function makeDecision(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "orchestration_decision_v1",
    decision_id: "decision/alpha 1",
    request_id: "request-1",
    request_version: 1,
    round_id: "round-1",
    request_digest: "request-digest-1",
    outcome: "DECIDED",
    selected_route_id: "route_alpha",
    selected_proposal_digest: "proposal-digest-alpha",
    required_quorum: 2,
    proposal_summaries: [makeProposal()],
    vote_summaries: [makeVote()],
    rejections: [makeRejection()],
    supporting_orchestrators: ["orchestrator_a", "orchestrator_b"],
    disagreeing_orchestrators: ["orchestrator_c"],
    timed_out_orchestrators: [],
    delayed_orchestrators: [],
    omitted_orchestrators: [],
    unavailable_orchestrators: [],
    quorum_formed: true,
    quorum_latency_ms: 4.5,
    decision_latency_ms: 7.25,
    reason: "backend selected a quorum-supported route",
    logical_timestamp: "2026-08-28T00:00:00Z",
    window_id: 7,
    completed_at_utc: "2026-08-28T00:00:01Z",
    provenance: {
      source_component: "backend.orchestration",
      session_trace: "opaque:scenario_id=words-are-not-keys",
    },
    ...overrides,
  };
}

function makeNonDecision(outcome: (typeof OrchestrationOutcomeValues)[number]) {
  return makeDecision({
    outcome,
    selected_route_id: null,
    selected_proposal_digest: null,
    supporting_orchestrators: [],
    quorum_formed: false,
    quorum_latency_ms: null,
  });
}

function makeDecisionListing(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "orchestration_decision_listing_v1",
    decisions: [makeDecision()],
    total_retained: 1,
    limit: 20,
    offset: 0,
    history_complete: false,
    bounds: { history_limit: 500, max_page_limit: 200 },
    ...overrides,
  };
}

function makeReplica(
  orchestratorId: (typeof ORCHESTRATOR_IDS)[number] = "orchestrator_a",
  overrides: Record<string, unknown> = {}
) {
  return {
    schema_version: "orchestrator_status_v1",
    orchestrator_id: orchestratorId,
    health: "HEALTHY",
    available: true,
    messages_proposed: 2,
    votes_issued: 2,
    authentication_failures_observed: 0,
    timeouts: 0,
    omissions: 0,
    last_error: null,
    recent_outcomes: [
      { kind: "PROPOSAL", request_id: "request-1", route_id: "route_alpha" },
      {
        kind: "VOTE",
        request_id: "request-1",
        proposal_digest: "proposal-digest-alpha",
      },
    ],
    recent_outcomes_limit: 32,
    ...overrides,
  };
}

function makeReplicaListing(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "orchestrator_listing_v1",
    replicas: ORCHESTRATOR_IDS.map((id, index) =>
      makeReplica(id, {
        health: OrchestratorHealthValues[index],
        available: index !== 2,
      })
    ),
    note: "operational orchestrators, not Blackboard replicas",
    ...overrides,
  };
}

const eventPayloads = {
  ORCHESTRATION_REQUEST_RECEIVED: {
    request_id: "request-1",
    request_version: 1,
    round_id: "round-1",
    request_digest: "request-digest-1",
    candidate_route_ids: ["route_alpha", "route_beta"],
    decision_kind: "OPAQUE_ROUTE",
    source_component: "backend.caller",
    caller_principal: "researcher",
  },
  ORCHESTRATOR_PROPOSAL: {
    ...makeProposal(),
    request_id: "request-1",
    round_id: "round-1",
  },
  ORCHESTRATOR_VOTE: {
    ...makeVote(),
    request_id: "request-1",
    round_id: "round-1",
  },
  ORCHESTRATOR_TIMEOUT: {
    request_id: "request-1",
    round_id: "round-1",
    orchestrator_id: "orchestrator_c",
    phase: "ROUND",
    budget_ms: 50,
    reason: "NO_USABLE_RESPONSE_BEFORE_TERMINAL_ROUND",
  },
  ORCHESTRATOR_DELAYED: {
    request_id: "request-1",
    round_id: "round-1",
    orchestrator_id: "orchestrator_c",
    phase: "VOTE",
    reason: "ROUND_CLOSED_AFTER_QUORUM_BEFORE_RESPONSE",
  },
  ORCHESTRATOR_OMISSION: {
    request_id: "request-1",
    round_id: "round-1",
    orchestrator_id: "orchestrator_c",
    phase: "ROUND",
    reason: "NO_MESSAGE_PRODUCED",
  },
  ORCHESTRATOR_STATUS: {
    request_id: "request-1",
    round_id: "round-1",
    orchestrator_id: "orchestrator_c",
    health: "UNAVAILABLE",
    available: false,
    reason: "OPERATIONALLY_UNAVAILABLE",
  },
  ORCHESTRATION_QUORUM_REACHED: {
    request_id: "request-1",
    round_id: "round-1",
    proposal_digest: "proposal-digest-alpha",
    supporting_orchestrators: ["orchestrator_a", "orchestrator_b"],
    required_quorum: 2,
    quorum_latency_ms: 4.5,
  },
  ORCHESTRATION_NO_QUORUM: {
    request_id: "request-1",
    round_id: "round-1",
    outcome: "NO_QUORUM",
    reason: "backend found no quorum",
    required_quorum: 2,
  },
  ORCHESTRATION_DECISION: makeDecision(),
} as const;

type EventType = keyof typeof eventPayloads;

function makeEvent(eventType: EventType, payload: unknown = eventPayloads[eventType]) {
  return {
    schema_version: "simulation_event_v1",
    replay_id: "orchestration-ops",
    event_id: `event-${eventType}`,
    sequence_number: 1,
    event_type: eventType,
    logical_timestamp: "2026-08-28T00:00:00Z",
    window_id: 7,
    source_component: "backend.orchestration",
    entity_id: "request-1",
    payload,
    provenance: { session_trace: "opaque-event-trace" },
  };
}

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Stage-6 orchestration enums and versioned contracts", () => {
  it("accepts exactly the five outcomes, three vote values, and three health values", () => {
    expect(OrchestrationOutcomeValues).toEqual([
      "DECIDED",
      "NO_QUORUM",
      "TIMED_OUT",
      "INSUFFICIENT_RESPONSES",
      "REJECTED_REQUEST",
    ]);
    expect(VoteValueValues).toEqual(["APPROVE", "REJECT", "ABSTAIN"]);
    expect(OrchestratorHealthValues).toEqual([
      "HEALTHY",
      "DEGRADED",
      "UNAVAILABLE",
    ]);

    for (const value of OrchestrationOutcomeValues) {
      expect(OrchestrationOutcomeSchema.safeParse(value).success).toBe(true);
    }
    for (const value of VoteValueValues) {
      expect(VoteValueSchema.safeParse(value).success).toBe(true);
    }
    for (const value of OrchestratorHealthValues) {
      expect(OrchestratorHealthSchema.safeParse(value).success).toBe(true);
    }
    expect(OrchestrationOutcomeSchema.safeParse("APPROVED").success).toBe(false);
    expect(VoteValueSchema.safeParse("YES").success).toBe(false);
    expect(OrchestratorHealthSchema.safeParse("OFFLINE").success).toBe(false);
  });

  it("enforces every exact schema_version literal", () => {
    const versioned = [
      [OrchestratorStatusV1Schema, makeReplica(), "orchestrator_status_v1"],
      [OrchestratorListingV1Schema, makeReplicaListing(), "orchestrator_listing_v1"],
      [MessageRejectionV1Schema, makeRejection(), "orchestrator_message_rejection_v1"],
      [OrchestrationHealthV1Schema, makeHealth(), "orchestration_health_v1"],
      [OrchestrationDecisionV1Schema, makeDecision(), "orchestration_decision_v1"],
      [
        OrchestrationDecisionListingV1Schema,
        makeDecisionListing(),
        "orchestration_decision_listing_v1",
      ],
    ] as const;

    for (const [schema, value, expectedVersion] of versioned) {
      const parsed = schema.safeParse(value);
      expect(parsed.success).toBe(true);
      if (parsed.success) expect(parsed.data.schema_version).toBe(expectedVersion);
      expect(
        schema.safeParse({ ...value, schema_version: `${expectedVersion}_next` }).success
      ).toBe(false);
    }
    expect(
      OrchestrationEventEnvelopeV1Schema.safeParse({
        ...makeEvent("ORCHESTRATION_REQUEST_RECEIVED"),
        schema_version: "simulation_event_v2",
      }).success
    ).toBe(false);
  });

  it("validates all five backend decision outcomes", () => {
    for (const outcome of OrchestrationOutcomeValues) {
      const decision =
        outcome === "DECIDED" ? makeDecision() : makeNonDecision(outcome);
      const parsed = OrchestrationDecisionV1Schema.safeParse(decision);
      expect(parsed.success, outcome).toBe(true);
      if (parsed.success) expect(parsed.data.outcome).toBe(outcome);
    }
  });

  it("requires a backend route and quorum for DECIDED", () => {
    expect(
      OrchestrationDecisionV1Schema.safeParse(makeDecision({ selected_route_id: null }))
        .success
    ).toBe(false);
    expect(
      OrchestrationDecisionV1Schema.safeParse(makeDecision({ selected_route_id: "" }))
        .success
    ).toBe(false);
    expect(
      OrchestrationDecisionV1Schema.safeParse(makeDecision({ quorum_formed: false }))
        .success
    ).toBe(false);
  });

  it("rejects a non-null route or digest for every non-decided outcome", () => {
    for (const outcome of OrchestrationOutcomeValues.filter(
      (value) => value !== "DECIDED"
    )) {
      expect(
        OrchestrationDecisionV1Schema.safeParse(
          makeNonDecision(outcome as (typeof OrchestrationOutcomeValues)[number])
        ).success,
        outcome
      ).toBe(true);
      expect(
        OrchestrationDecisionV1Schema.safeParse({
          ...makeNonDecision(outcome as (typeof OrchestrationOutcomeValues)[number]),
          selected_route_id: "route_alpha",
        }).success,
        `${outcome} route`
      ).toBe(false);
      expect(
        OrchestrationDecisionV1Schema.safeParse({
          ...makeNonDecision(outcome as (typeof OrchestrationOutcomeValues)[number]),
          selected_proposal_digest: "proposal-digest-alpha",
        }).success,
        `${outcome} digest`
      ).toBe(false);
    }
  });

  it("validates proposal, every vote, and every rejection phase as strict schemas", () => {
    expect(ProposalSummaryV1Schema.safeParse(makeProposal()).success).toBe(true);
    for (const vote of VoteValueValues) {
      expect(VoteSummaryV1Schema.safeParse(makeVote({ vote })).success).toBe(true);
    }
    for (const phase of ["PROPOSAL", "VOTE", "ROUND"] as const) {
      expect(MessageRejectionV1Schema.safeParse(makeRejection({ phase })).success).toBe(
        true
      );
    }
    expect(
      ProposalSummaryV1Schema.safeParse({ ...makeProposal(), private_key: "secret" })
        .success
    ).toBe(false);
    expect(VoteSummaryV1Schema.safeParse(makeVote({ latency_ms: -1 })).success).toBe(
      false
    );
    expect(
      MessageRejectionV1Schema.safeParse(makeRejection({ phase: "AUTH" })).success
    ).toBe(false);
  });
});

describe("orchestrator status, instrumentation, and bounded decision history", () => {
  it("accepts the three actual orchestrator IDs, all statuses, and both recent outcome shapes", () => {
    const listing = makeReplicaListing();
    const parsed = OrchestratorListingV1Schema.safeParse(listing);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.replicas.map((replica) => replica.orchestrator_id)).toEqual(
        ORCHESTRATOR_IDS
      );
      expect(parsed.data.replicas.map((replica) => replica.health)).toEqual(
        OrchestratorHealthValues
      );
      expect(parsed.data.replicas[0].recent_outcomes.map((item) => item.kind)).toEqual([
        "PROPOSAL",
        "VOTE",
      ]);
    }
    expect(
      OrchestratorRecentOutcomeV1Schema.safeParse({
        kind: "PROPOSAL",
        request_id: "request-1",
        route_id: "route_alpha",
      }).success
    ).toBe(true);
    expect(
      OrchestratorRecentOutcomeV1Schema.safeParse({
        kind: "VOTE",
        request_id: "request-1",
        proposal_digest: "digest",
      }).success
    ).toBe(true);
    expect(
      OrchestratorRecentOutcomeV1Schema.safeParse({
        kind: "VOTE",
        request_id: "request-1",
        route_id: "route_alpha",
      }).success
    ).toBe(false);
  });

  it("rejects malformed status/listing counters, limits, and extra fields", () => {
    expect(OrchestratorStatusV1Schema.safeParse(makeReplica()).success).toBe(true);
    expect(
      OrchestratorStatusV1Schema.safeParse(makeReplica("orchestrator_a", { timeouts: -1 }))
        .success
    ).toBe(false);
    expect(
      OrchestratorStatusV1Schema.safeParse(
        makeReplica("orchestrator_a", { recent_outcomes_limit: 0 })
      ).success
    ).toBe(false);
    expect(
      OrchestratorListingV1Schema.safeParse({ ...makeReplicaListing(), extra: true })
        .success
    ).toBe(false);
  });

  it("accepts an exact empty latency summary and complete empty instrumentation", () => {
    expect(OrchestrationLatencySummaryV1Schema.safeParse({ count: 0 }).success).toBe(
      true
    );
    expect(
      OrchestrationLatencySummaryV1Schema.safeParse({ count: 0, mean_ms: 0 }).success
    ).toBe(false);
    expect(OrchestrationCountersV1Schema.safeParse(makeCounters()).success).toBe(true);
    expect(OrchestrationLatenciesV1Schema.safeParse(makeLatencies()).success).toBe(true);
    expect(OrchestrationInstrumentationV1Schema.safeParse(makeInstrumentation()).success).toBe(
      true
    );
  });

  it("accepts populated latency/rejections and rejects malformed metrics and counters", () => {
    const populated = makeInstrumentation({
      latencies: makeLatencies(true),
      recent_rejections: [makeRejection()],
    });
    expect(OrchestrationInstrumentationV1Schema.safeParse(populated).success).toBe(true);
    expect(
      OrchestrationLatencySummaryV1Schema.safeParse(
        makePopulatedLatency({ count: 0 })
      ).success
    ).toBe(false);
    expect(
      OrchestrationLatencySummaryV1Schema.safeParse(
        makePopulatedLatency({ p95_ms: -0.1 })
      ).success
    ).toBe(false);
    expect(
      OrchestrationCountersV1Schema.safeParse(makeCounters({ rounds_started: 1.5 })).success
    ).toBe(false);
    expect(
      OrchestrationCountersV1Schema.safeParse({ ...makeCounters(), unknown_counter: 1 })
        .success
    ).toBe(false);
  });

  it("enforces positive instrumentation bounds and fixed health facts", () => {
    expect(
      OrchestrationInstrumentationBoundsV1Schema.safeParse({
        latency_samples: 1,
        recent_rejections: 1,
      }).success
    ).toBe(true);
    expect(
      OrchestrationInstrumentationBoundsV1Schema.safeParse({
        latency_samples: 0,
        recent_rejections: 1,
      }).success
    ).toBe(false);
    for (const status of ["ok", "degraded", "offline"] as const) {
      expect(OrchestrationHealthV1Schema.safeParse(makeHealth({ status })).success).toBe(
        true
      );
    }
    for (const invalid of [
      { orchestrators_total: 4 },
      { required_quorum: 3 },
      { event_namespace: "orchestration" },
      { decision_history_persistent: true },
      { status: "healthy" },
    ]) {
      expect(OrchestrationHealthV1Schema.safeParse(makeHealth(invalid)).success).toBe(
        false
      );
    }
  });

  it("requires history_complete=false and positive listing bounds", () => {
    expect(
      OrchestrationDecisionListingBoundsV1Schema.safeParse({
        history_limit: 1,
        max_page_limit: 1,
      }).success
    ).toBe(true);
    expect(OrchestrationDecisionListingV1Schema.safeParse(makeDecisionListing()).success).toBe(
      true
    );
    expect(
      OrchestrationDecisionListingV1Schema.safeParse(
        makeDecisionListing({ history_complete: true })
      ).success
    ).toBe(false);
    expect(
      OrchestrationDecisionListingV1Schema.safeParse(
        makeDecisionListing({ bounds: { history_limit: 0, max_page_limit: 200 } })
      ).success
    ).toBe(false);
    expect(
      OrchestrationDecisionListingV1Schema.safeParse(makeDecisionListing({ limit: 0 }))
        .success
    ).toBe(false);
  });
});

describe("orchestration event payload and envelope contracts", () => {
  it("registers exactly the ten operational event types", () => {
    expect(Object.keys(OrchestrationEventPayloadSchemas)).toEqual(
      Object.keys(eventPayloads)
    );
  });

  it.each(Object.keys(eventPayloads) as EventType[])(
    "validates %s with its actual payload and fixed namespace",
    (eventType) => {
      const payloadSchema = OrchestrationEventPayloadSchemas[eventType];
      expect(payloadSchema.safeParse(eventPayloads[eventType]).success).toBe(true);
      expect(
        payloadSchema.safeParse({ ...eventPayloads[eventType], unexpected: true }).success
      ).toBe(false);

      const parsed = OrchestrationEventEnvelopeV1Schema.safeParse(makeEvent(eventType));
      expect(parsed.success).toBe(true);
      if (parsed.success) {
        expect(parsed.data.event_type).toBe(eventType);
        expect(parsed.data.replay_id).toBe("orchestration-ops");
      }
    }
  );

  it("directly validates request/proposal/vote operational payload schemas", () => {
    expect(
      OrchestrationRequestReceivedPayloadV1Schema.safeParse(
        eventPayloads.ORCHESTRATION_REQUEST_RECEIVED
      ).success
    ).toBe(true);
    expect(
      OrchestratorProposalEventPayloadV1Schema.safeParse(
        eventPayloads.ORCHESTRATOR_PROPOSAL
      ).success
    ).toBe(true);
    expect(
      OrchestratorVoteEventPayloadV1Schema.safeParse(eventPayloads.ORCHESTRATOR_VOTE)
        .success
    ).toBe(true);
  });

  it("directly validates timeout, delayed, omission, and unavailable payload literals", () => {
    expect(
      OrchestratorTimeoutPayloadV1Schema.safeParse(eventPayloads.ORCHESTRATOR_TIMEOUT)
        .success
    ).toBe(true);
    expect(
      OrchestratorDelayedPayloadV1Schema.safeParse(eventPayloads.ORCHESTRATOR_DELAYED)
        .success
    ).toBe(true);
    expect(
      OrchestratorOmissionPayloadV1Schema.safeParse(eventPayloads.ORCHESTRATOR_OMISSION)
        .success
    ).toBe(true);
    expect(
      OrchestratorStatusEventPayloadV1Schema.safeParse(eventPayloads.ORCHESTRATOR_STATUS)
        .success
    ).toBe(true);
    expect(
      OrchestratorTimeoutPayloadV1Schema.safeParse({
        ...eventPayloads.ORCHESTRATOR_TIMEOUT,
        phase: "VOTE",
      }).success
    ).toBe(false);
    expect(
      OrchestratorStatusEventPayloadV1Schema.safeParse({
        ...eventPayloads.ORCHESTRATOR_STATUS,
        available: true,
      }).success
    ).toBe(false);
  });

  it("validates quorum/no-quorum payload bounds and every non-decision outcome", () => {
    expect(
      OrchestrationQuorumReachedPayloadV1Schema.safeParse(
        eventPayloads.ORCHESTRATION_QUORUM_REACHED
      ).success
    ).toBe(true);
    expect(
      OrchestrationQuorumReachedPayloadV1Schema.safeParse({
        ...eventPayloads.ORCHESTRATION_QUORUM_REACHED,
        required_quorum: 3,
      }).success
    ).toBe(false);
    for (const outcome of [
      "NO_QUORUM",
      "TIMED_OUT",
      "INSUFFICIENT_RESPONSES",
      "REJECTED_REQUEST",
    ] as const) {
      expect(
        OrchestrationNoQuorumPayloadV1Schema.safeParse({
          ...eventPayloads.ORCHESTRATION_NO_QUORUM,
          outcome,
        }).success
      ).toBe(true);
    }
    expect(
      OrchestrationNoQuorumPayloadV1Schema.safeParse({
        ...eventPayloads.ORCHESTRATION_NO_QUORUM,
        outcome: "DECIDED",
      }).success
    ).toBe(false);
  });

  it("rejects foreign namespaces, event/payload mismatches, and envelope extras", () => {
    expect(
      OrchestrationEventEnvelopeV1Schema.safeParse({
        ...makeEvent("ORCHESTRATION_REQUEST_RECEIVED"),
        replay_id: "replay-1",
      }).success
    ).toBe(false);
    expect(
      OrchestrationEventEnvelopeV1Schema.safeParse(
        makeEvent("ORCHESTRATOR_VOTE", eventPayloads.ORCHESTRATOR_PROPOSAL)
      ).success
    ).toBe(false);
    expect(
      OrchestrationEventEnvelopeV1Schema.safeParse({
        ...makeEvent("ORCHESTRATION_REQUEST_RECEIVED"),
        unexpected: true,
      }).success
    ).toBe(false);
  });
});

describe("recursive orchestration metadata firewall", () => {
  it("exports the exact complete forbidden key set", () => {
    expect(ORCHESTRATION_FORBIDDEN_KEYS).toEqual(EXPECTED_FORBIDDEN_KEYS);
    expect(new Set(ORCHESTRATION_FORBIDDEN_KEYS).size).toBe(
      EXPECTED_FORBIDDEN_KEYS.length
    );
  });

  it.each(EXPECTED_FORBIDDEN_KEYS)("recursively rejects forbidden key %s", (key) => {
    const mixedCasePadded = `  ${key.toUpperCase()}  `;
    const provenance = {
      safe: [{ deeper: { [mixedCasePadded]: "evaluation metadata" } }],
    };
    expect(hasForbiddenOrchestrationKey(provenance)).toBe(true);
    expect(
      OrchestrationDecisionV1Schema.safeParse(makeDecision({ provenance })).success
    ).toBe(false);
    expect(
      OrchestrationEventEnvelopeV1Schema.safeParse({
        ...makeEvent("ORCHESTRATION_REQUEST_RECEIVED"),
        provenance,
      }).success
    ).toBe(false);
  });

  it("keeps session_trace opaque and does not inspect forbidden words in values", () => {
    const opaque = {
      session_trace: {
        arbitrary: ["scenario_id", "ground_truth", { token: "filename=secret.csv" }],
      },
    };
    expect(hasForbiddenOrchestrationKey(opaque)).toBe(false);
    const parsed = OrchestrationDecisionV1Schema.safeParse(
      makeDecision({ provenance: opaque })
    );
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data.provenance).toEqual(opaque);
  });
});

describe("Stage-7 read-only ApiClient", () => {
  it.each([
    ["health", (client: ApiClient) => client.getOrchestrationHealth(), makeHealth()],
    [
      "replica listing",
      (client: ApiClient) => client.getOrchestrationReplicas(),
      makeReplicaListing(),
    ],
    [
      "replica detail",
      (client: ApiClient) => client.getOrchestrationReplica("orchestrator_a"),
      makeReplica(),
    ],
    [
      "decision listing",
      (client: ApiClient) => client.listOrchestrationDecisions(),
      makeDecisionListing(),
    ],
    [
      "decision detail",
      (client: ApiClient) => client.getOrchestrationDecision("decision-1"),
      makeDecision({ decision_id: "decision-1" }),
    ],
  ] as const)("uses GET and validates the %s response", async (_name, invoke, body) => {
    const fetchMock = vi.fn(async () => jsonResponse(body));
    vi.stubGlobal("fetch", fetchMock);

    await invoke(new ApiClient("http://backend/api/v1"));

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = (
      fetchMock.mock.calls as unknown as Array<[string, RequestInit]>
    )[0];
    expect(init).toEqual({ method: "GET", headers: undefined, body: undefined });
  });

  it("uses exact GET paths and encodes replica and decision path segments", async () => {
    const responses = [makeHealth(), makeReplicaListing(), makeReplica(), makeDecision()];
    const fetchMock = vi.fn(async () => jsonResponse(responses.shift()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");

    await client.getOrchestrationHealth();
    await client.getOrchestrationReplicas();
    await client.getOrchestrationReplica("orchestrator/a ?#");
    await client.getOrchestrationDecision("decision/a ?#");

    const calls = fetchMock.mock.calls as unknown as Array<[string, RequestInit]>;
    expect(calls.map(([url]) => url)).toEqual([
      "http://backend/api/v1/orchestration/health",
      "http://backend/api/v1/orchestration/replicas",
      "http://backend/api/v1/orchestration/replicas/orchestrator%2Fa%20%3F%23",
      "http://backend/api/v1/orchestration/decisions/decision%2Fa%20%3F%23",
    ]);
    expect(calls.every(([, init]) => init.method === "GET")).toBe(true);
  });

  it("serializes outcome, encoded request filter, limit, and offset in order", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(makeDecisionListing()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");

    await client.listOrchestrationDecisions({
      outcome: "INSUFFICIENT_RESPONSES",
      request_id: "request/a + b?",
      limit: 50,
      offset: 100,
    });
    await client.listOrchestrationDecisions();

    const calls = fetchMock.mock.calls as unknown as Array<[string, RequestInit]>;
    expect(calls.map(([url]) => url)).toEqual([
      "http://backend/api/v1/orchestration/decisions?outcome=INSUFFICIENT_RESPONSES&request_id=request%2Fa+%2B+b%3F&limit=50&offset=100",
      "http://backend/api/v1/orchestration/decisions",
    ]);
  });

  it.each([
    ["health", (client: ApiClient) => client.getOrchestrationHealth(), makeHealth()],
    [
      "replica listing",
      (client: ApiClient) => client.getOrchestrationReplicas(),
      makeReplicaListing(),
    ],
    [
      "replica detail",
      (client: ApiClient) => client.getOrchestrationReplica("orchestrator_a"),
      makeReplica(),
    ],
    [
      "decision listing",
      (client: ApiClient) => client.listOrchestrationDecisions(),
      makeDecisionListing(),
    ],
    [
      "decision detail",
      (client: ApiClient) => client.getOrchestrationDecision("decision-1"),
      makeDecision(),
    ],
  ] as const)("rejects malformed/extra %s responses", async (_name, invoke, validBody) => {
    const invalidBodies = [
      { ...validBody, unexpected_backend_field: true },
      { schema_version: "malformed_orchestration_response" },
    ];
    const fetchMock = vi.fn(async () => jsonResponse(invalidBodies.shift()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");

    await expect(invoke(client)).rejects.toBeInstanceOf(ContractValidationError);
    await expect(invoke(client)).rejects.toBeInstanceOf(
      ContractValidationError
    );
  });
});

describe("Stage-7 source boundary", () => {
  const stage7Source = [
    orchestrationHookSource,
    decisionBrowserSource,
    decisionDetailSource,
    decisionResultSource,
    decisionTraceSource,
    digestFieldSource,
    liveActivitySource,
    overviewSource,
    orchestratorCardsSource,
    orchestrationViewSource,
  ].join("\n");
  const orchestrationClientSource = clientSource.slice(
    clientSource.indexOf("// ─── Orchestration")
  );

  it("has no crypto, HMAC/signing key, or digest/hash recomputation calls", () => {
    expect(stage7Source).not.toMatch(
      /from\s+["'][^"']*(?:crypto|hashing|authentication)[^"']*["']/i
    );
    expect(stage7Source).not.toMatch(
      /\b(?:crypto|createHmac|subtle\.digest|hmac|sha256|sign|verify)\s*\(/i
    );
    expect(stage7Source).not.toMatch(
      /\b(?:hmac|secret|signing|authentication)[A-Za-z_]*key\s*(?:=|:)/i
    );
    expect(stage7Source).not.toMatch(
      /\b(?:compute|calculate|derive|recompute)[A-Za-z_]*(?:digest|hash)\s*\(/i
    );
  });

  it("does not derive quorum or selected routes from proposal/vote collections", () => {
    expect(stage7Source).not.toMatch(/vote_summaries\s*\.\s*(?:filter|reduce|some)/);
    expect(stage7Source).not.toMatch(
      /supporting_orchestrators\s*\.\s*length\s*(?:>=|>|===?)\s*\d+/
    );
    expect(stage7Source).not.toMatch(
      /\b(?:compute|calculate|derive|infer)[A-Za-z_]*quorum\s*\(/i
    );
    expect(stage7Source).not.toMatch(/(?:quorum_formed|selected_route_id)\s*=/);
  });

  it("exposes only the five orchestration GET calls and no request execution control", () => {
    expect(orchestrationClientSource.match(/this\.request\(\s*"GET"/g)).toHaveLength(5);
    expect(orchestrationClientSource).not.toMatch(
      /this\.request\(\s*"(?:POST|PUT|PATCH|DELETE)"/
    );
    expect(orchestrationClientSource).not.toContain("/orchestration/requests");
    expect(stage7Source).not.toMatch(
      /\b(?:(?:execute|dispatch|apply|enforce|submit)[A-Za-z_]*(?:route|request)|authorOrchestrationRequest)\s*\(/i
    );
  });
});
