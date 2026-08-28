/** Stage-7 orchestration component, hook, stream, and dashboard regressions. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  EventEnvelopeV1,
  OrchestrationDecisionListingV1,
  OrchestrationDecisionV1,
  OrchestrationEventEnvelopeV1,
  OrchestrationEventPayload,
  OrchestrationEventType,
  OrchestrationHealthV1,
  OrchestratorStatusV1,
  ProposalSummaryV1,
  VoteSummaryV1,
} from "../api/contracts";
import { OrchestrationEventEnvelopeV1Schema } from "../api/contracts";
import { ApiClient } from "../api/client";
import { ReplayProvider } from "../state/ReplayContext";
import { useOrchestration } from "../hooks/useOrchestration";
import { OrchestrationOverview } from "../components/orchestration/OrchestrationOverview";
import { OrchestratorCards } from "../components/orchestration/OrchestratorCards";
import { DecisionBrowser } from "../components/orchestration/DecisionBrowser";
import { DecisionDetailPanel } from "../components/orchestration/DecisionDetailPanel";
import { DecisionTrace } from "../components/orchestration/DecisionTrace";
import { DigestField } from "../components/orchestration/DigestField";
import { LiveOrchestrationActivity } from "../components/orchestration/LiveOrchestrationActivity";
import { authoritativeRoute } from "../components/orchestration/decisionResult";
import { DashboardPage } from "../pages/DashboardPage";

const REQUEST_DIGEST = "request-digest-000000000000000000000000000000000001";
const PROPOSAL_DIGEST = "proposal-digest-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const OTHER_PROPOSAL_DIGEST = "proposal-digest-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
const PROPOSAL_HASH = "proposal-message-hash-11111111111111111111111111111111";
const VOTE_HASH = "vote-message-hash-2222222222222222222222222222222222";

function makeHealth(overrides: Partial<OrchestrationHealthV1> = {}): OrchestrationHealthV1 {
  const base: OrchestrationHealthV1 = {
    schema_version: "orchestration_health_v1",
    status: "ok",
    orchestrators_available: 3,
    orchestrators_total: 3,
    required_quorum: 2,
    event_namespace: "orchestration-ops",
    decision_history_persistent: false,
    instrumentation: {
      counters: {
        rounds_started: 11,
        decisions_reached: 5,
        no_quorum: 2,
        timed_out: 1,
        insufficient_responses: 1,
        proposals_received: 24,
        proposals_rejected: 3,
        votes_received: 19,
        votes_rejected: 2,
        authentication_failures: 4,
        duplicate_messages: 1,
        conflicting_votes: 2,
        orchestrator_timeouts: 1,
        orchestrator_delays: 2,
        orchestrator_omissions: 3,
        orchestrator_disagreements: 4,
      },
      latencies: {
        proposal_ms: { count: 2, mean_ms: 3.25, p50_ms: 3, p95_ms: 4, max_ms: 4.5 },
        vote_ms: { count: 0 },
        quorum_ms: { count: 1, mean_ms: 8, p50_ms: 8, p95_ms: 8, max_ms: 8 },
        decision_ms: { count: 1, mean_ms: 9, p50_ms: 9, p95_ms: 9, max_ms: 9 },
      },
      recent_rejections: [],
      bounds: { latency_samples: 256, recent_rejections: 40 },
    },
  };
  return { ...base, ...overrides };
}

function makeStatus(overrides: Partial<OrchestratorStatusV1> = {}): OrchestratorStatusV1 {
  return {
    schema_version: "orchestrator_status_v1",
    orchestrator_id: "orchestrator_a",
    health: "HEALTHY",
    available: true,
    messages_proposed: 8,
    votes_issued: 7,
    authentication_failures_observed: 2,
    timeouts: 1,
    omissions: 0,
    last_error: null,
    recent_outcomes: [{ kind: "PROPOSAL", request_id: "request-1", route_id: "route-opaque-a" }],
    recent_outcomes_limit: 20,
    ...overrides,
  };
}

function makeProposal(overrides: Partial<ProposalSummaryV1> = {}): ProposalSummaryV1 {
  return {
    orchestrator_id: "orchestrator_a",
    message_id: "proposal-message-a",
    proposed_route_id: "route-opaque-a",
    proposal_digest: PROPOSAL_DIGEST,
    message_hash: PROPOSAL_HASH,
    authentication_verified: true,
    policy_id: "opaque-route-policy",
    policy_version: "v7",
    rationale_code: "POLICY_MATCH",
    latency_ms: 3.5,
    ...overrides,
  };
}

function makeVote(overrides: Partial<VoteSummaryV1> = {}): VoteSummaryV1 {
  return {
    orchestrator_id: "orchestrator_a",
    message_id: "vote-message-a",
    selected_proposal_digest: PROPOSAL_DIGEST,
    vote: "APPROVE",
    message_hash: VOTE_HASH,
    authentication_verified: true,
    reason_code: "SUPPORTED_PROPOSAL",
    latency_ms: 2.25,
    ...overrides,
  };
}

function makeDecision(overrides: Partial<OrchestrationDecisionV1> = {}): OrchestrationDecisionV1 {
  const base: OrchestrationDecisionV1 = {
    schema_version: "orchestration_decision_v1",
    decision_id: "decision-1",
    request_id: "request-1",
    request_version: 1,
    round_id: "round-1",
    request_digest: REQUEST_DIGEST,
    outcome: "DECIDED",
    selected_route_id: "route-opaque-a",
    selected_proposal_digest: PROPOSAL_DIGEST,
    required_quorum: 2,
    proposal_summaries: [makeProposal()],
    vote_summaries: [makeVote(), makeVote({ orchestrator_id: "orchestrator_b", message_id: "vote-message-b", message_hash: `${VOTE_HASH}-b` })],
    rejections: [],
    supporting_orchestrators: ["orchestrator_a", "orchestrator_b"],
    disagreeing_orchestrators: [],
    timed_out_orchestrators: [],
    delayed_orchestrators: [],
    omitted_orchestrators: [],
    unavailable_orchestrators: [],
    quorum_formed: true,
    quorum_latency_ms: 8.5,
    decision_latency_ms: 10.75,
    reason: "Backend selected an opaque route",
    logical_timestamp: "2026-08-28T10:00:00Z",
    window_id: 7,
    completed_at_utc: "2026-08-28T10:00:01Z",
    provenance: { source_component: "backend.orchestration", policy_revision: "v7" },
  };
  const next = { ...base, ...overrides };
  if (next.outcome !== "DECIDED") {
    next.selected_route_id = overrides.selected_route_id ?? null;
    next.selected_proposal_digest = overrides.selected_proposal_digest ?? null;
    next.quorum_formed = overrides.quorum_formed ?? false;
    next.quorum_latency_ms = overrides.quorum_latency_ms ?? null;
  }
  return next;
}

function makeListing(overrides: Partial<OrchestrationDecisionListingV1> = {}): OrchestrationDecisionListingV1 {
  return {
    schema_version: "orchestration_decision_listing_v1",
    decisions: [makeDecision()],
    total_retained: 1,
    limit: 20,
    offset: 0,
    history_complete: false,
    bounds: { history_limit: 500, max_page_limit: 100 },
    ...overrides,
  };
}

function makeEvent(
  eventType: OrchestrationEventType,
  payload: OrchestrationEventPayload,
  sequenceNumber: number,
  overrides: Partial<EventEnvelopeV1> = {}
): OrchestrationEventEnvelopeV1 {
  return OrchestrationEventEnvelopeV1Schema.parse({
    schema_version: "simulation_event_v1",
    replay_id: "orchestration-ops",
    event_id: `orchestration-event-${sequenceNumber}`,
    sequence_number: sequenceNumber,
    event_type: eventType,
    logical_timestamp: "2026-08-28T10:00:00Z",
    window_id: null,
    source_component: "backend.orchestration",
    entity_id: null,
    payload,
    provenance: { transport: "backend-event" },
    ...overrides,
  });
}

function proposalEvent(orchestratorId: string, sequenceNumber: number, digest = PROPOSAL_DIGEST) {
  return makeEvent("ORCHESTRATOR_PROPOSAL", {
    ...makeProposal({
      orchestrator_id: orchestratorId,
      message_id: `proposal-${orchestratorId}-${sequenceNumber}`,
      proposal_digest: digest,
      message_hash: `proposal-hash-${orchestratorId}-${sequenceNumber}`,
    }),
    request_id: "request-1",
    round_id: "round-1",
  }, sequenceNumber, { entity_id: orchestratorId });
}

function voteEvent(orchestratorId: string, sequenceNumber: number, digest = PROPOSAL_DIGEST) {
  return makeEvent("ORCHESTRATOR_VOTE", {
    ...makeVote({
      orchestrator_id: orchestratorId,
      message_id: `vote-${orchestratorId}-${sequenceNumber}`,
      selected_proposal_digest: digest,
      message_hash: `vote-hash-${orchestratorId}-${sequenceNumber}`,
    }),
    request_id: "request-1",
    round_id: "round-1",
  }, sequenceNumber, { entity_id: orchestratorId });
}

function requestEvent(sequenceNumber: number) {
  return makeEvent("ORCHESTRATION_REQUEST_RECEIVED", {
    request_id: "request-1",
    request_version: 1,
    round_id: "round-1",
    request_digest: REQUEST_DIGEST,
    candidate_route_ids: ["route-opaque-a", "route-opaque-b"],
    decision_kind: "OPAQUE_ROUTE",
    source_component: "gateway",
    caller_principal: "replay-service",
  }, sequenceNumber);
}

function makeClient(): ApiClient {
  const client = new ApiClient("http://stage7.test/api/v1");
  vi.spyOn(client, "getOrchestrationHealth").mockResolvedValue(makeHealth());
  vi.spyOn(client, "getOrchestrationReplicas").mockResolvedValue({
    schema_version: "orchestrator_listing_v1",
    replicas: [
      makeStatus(),
      makeStatus({ orchestrator_id: "orchestrator_b" }),
      makeStatus({ orchestrator_id: "orchestrator_c" }),
    ],
    note: "Operational participation evidence only.",
  });
  vi.spyOn(client, "listOrchestrationDecisions").mockResolvedValue(makeListing());
  vi.spyOn(client, "getOrchestrationDecision").mockResolvedValue(makeDecision());
  vi.spyOn(client, "getOrchestrationReplica").mockResolvedValue(makeStatus());
  return client;
}

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readonly url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  message(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent);
  }

  error() {
    this.onerror?.(new Event("error"));
  }

  serverClose(code = 1006) {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code } as CloseEvent);
  }

  close() {
    if (this.readyState === MockWebSocket.CLOSED) return;
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code: 1000 } as CloseEvent);
  }
}

function OrchestrationHarness() {
  const state = useOrchestration();
  return (
    <div>
      <span data-testid="hook-connection">{state.connectionState}</span>
      <span data-testid="hook-health">{state.health?.status ?? "none"}</span>
      <span data-testid="hook-replicas">{state.replicas.map((item) => item.orchestrator_id).join(",")}</span>
      <span data-testid="hook-decisions">{state.decisions.map((item) => item.decision_id).join(",")}</span>
      <span data-testid="hook-event-count">{state.events.length}</span>
      <span data-testid="hook-event-sequences">{state.events.map((item) => item.sequence_number).join(",")}</span>
      <span data-testid="hook-incomplete">{String(state.localHistoryIncomplete)}</span>
      <span data-testid="hook-gap">{String(state.gapDetected)}</span>
      <span data-testid="hook-error">{state.error ?? "none"}</span>
    </div>
  );
}

function renderHook(client = makeClient()) {
  const result = render(<ReplayProvider client={client}><OrchestrationHarness /></ReplayProvider>);
  return { ...result, client, socket: () => MockWebSocket.instances.at(-1)! };
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Stage-7 overview and actual orchestrators", () => {
  it("renders exactly the three backend orchestrator cards and operational evidence only", () => {
    const statuses = [
      makeStatus({ orchestrator_id: "orchestrator_a", health: "HEALTHY" }),
      makeStatus({ orchestrator_id: "orchestrator_b", health: "DEGRADED", authentication_failures_observed: 6 }),
      makeStatus({ orchestrator_id: "orchestrator_c", health: "UNAVAILABLE", available: false }),
    ];
    const { container } = render(<OrchestratorCards replicas={statuses} note="Operational participation evidence only." />);
    expect(container.querySelectorAll("article.orchestrator-card")).toHaveLength(3);
    for (const id of ["orchestrator_a", "orchestrator_b", "orchestrator_c"]) {
      expect(screen.getByText(id)).toBeInTheDocument();
    }
    expect(screen.getByText("HEALTHY")).toBeInTheDocument();
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
    expect(screen.getByText("UNAVAILABLE")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getAllByText("Auth failures observed")).toHaveLength(3);
    const text = container.textContent?.toLowerCase() ?? "";
    expect(text).not.toContain("replica_a");
    expect(text).not.toContain("replica_b");
    expect(text).not.toContain("replica_c");
    expect(text).not.toContain("trust");
    expect(text).not.toContain("malicious");
  });

  it("shows healthy, degraded, offline/unavailable, counters, and authentication failures as backend facts", () => {
    const { rerender } = render(<OrchestrationOverview health={makeHealth()} loading={false} error={null} onRefresh={vi.fn()} />);
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
    expect(screen.getByText("authentication failures").parentElement).toHaveTextContent("4");
    expect(screen.getByText("orchestrator disagreements").parentElement).toHaveTextContent("4");
    rerender(<OrchestrationOverview health={makeHealth({ status: "degraded", orchestrators_available: 2 })} loading={false} error={null} onRefresh={vi.fn()} />);
    expect(screen.getByText("degraded")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    rerender(<OrchestrationOverview health={makeHealth({ status: "offline", orchestrators_available: 0 })} loading={false} error={null} onRefresh={vi.fn()} />);
    expect(screen.getByText("offline")).toBeInTheDocument();
    expect(screen.getByText("0 / 3")).toBeInTheDocument();
  });

  it("renders backend unavailability without inventing health or counters", () => {
    render(<OrchestrationOverview health={null} loading={false} error="Cannot reach Stage-7 backend" onRefresh={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Orchestration unavailable: Cannot reach Stage-7 backend");
    expect(screen.queryByText("Service status")).not.toBeInTheDocument();
  });
});

describe("Authoritative outcomes and stale-route regressions", () => {
  it("shows all five backend outcomes and a selected route only for DECIDED", () => {
    const decisions: OrchestrationDecisionV1[] = [
      makeDecision({ decision_id: "d-decided", outcome: "DECIDED", selected_route_id: "route-only-decided" }),
      makeDecision({ decision_id: "d-no-quorum", outcome: "NO_QUORUM" }),
      makeDecision({ decision_id: "d-timeout", outcome: "TIMED_OUT" }),
      makeDecision({ decision_id: "d-insufficient", outcome: "INSUFFICIENT_RESPONSES" }),
      makeDecision({ decision_id: "d-rejected", outcome: "REJECTED_REQUEST" }),
    ];
    render(<DecisionBrowser listing={makeListing({ decisions, total_retained: 5 })} filters={{ limit: 20, offset: 0 }} loading={false} setFilters={vi.fn()} onSelect={vi.fn()} />);
    const table = screen.getByRole("table", { name: "Orchestration decisions" });
    for (const outcome of ["DECIDED", "NO_QUORUM", "TIMED_OUT", "INSUFFICIENT_RESPONSES", "REJECTED_REQUEST"]) {
      expect(within(table).getByText(outcome)).toBeInTheDocument();
    }
    expect(screen.getByText("route-only-decided")).toBeInTheDocument();
    expect(screen.getAllByText("No route selected")).toHaveLength(4);
  });

  it("never leaks a stale selected route from a non-DECIDED object", () => {
    const stale = makeDecision({ outcome: "NO_QUORUM" }) as OrchestrationDecisionV1 & { selected_route_id: string };
    stale.selected_route_id = "stale-route-must-not-display";
    expect(authoritativeRoute(stale)).toBeNull();
    render(<DecisionBrowser listing={makeListing({ decisions: [stale] })} filters={{ limit: 20, offset: 0 }} loading={false} setFilters={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText("No route selected")).toBeInTheDocument();
    expect(screen.queryByText("stale-route-must-not-display")).not.toBeInTheDocument();
  });

  it("matching APPROVE events cannot override authoritative NO_QUORUM with a null route", () => {
    const decision = makeDecision({ outcome: "NO_QUORUM", reason: "Backend did not form quorum" });
    render(<><LiveOrchestrationActivity events={[voteEvent("orchestrator_a", 1), voteEvent("orchestrator_b", 2)]} selectedTraceKey={null} onSelectTrace={vi.fn()} /><DecisionDetailPanel decision={decision} loading={false} error={null} onClose={vi.fn()} /></>);
    const activity = screen.getByRole("heading", { name: /Live activity/ }).closest("section")!;
    expect(within(activity).getAllByText(/APPROVE/)).toHaveLength(2);
    expect(screen.getByLabelText("Authoritative terminal result")).toHaveTextContent("NO_QUORUM");
    expect(screen.getByLabelText("Authoritative terminal result")).toHaveTextContent("No route selected");
  });

  it("matching proposal events cannot override authoritative TIMED_OUT with a null route", () => {
    const decision = makeDecision({ outcome: "TIMED_OUT", reason: "Backend round budget expired" });
    render(<><LiveOrchestrationActivity events={[proposalEvent("orchestrator_a", 1), proposalEvent("orchestrator_b", 2)]} selectedTraceKey={null} onSelectTrace={vi.fn()} /><DecisionDetailPanel decision={decision} loading={false} error={null} onClose={vi.fn()} /></>);
    expect(screen.getAllByText(/proposed route-opaque-a/)).toHaveLength(2);
    expect(screen.getByLabelText("Authoritative terminal result")).toHaveTextContent("TIMED_OUT");
    expect(screen.getByLabelText("Authoritative terminal result")).toHaveTextContent("No route selected");
  });

  it("a QUORUM_REACHED event without a final REST decision creates no final result", () => {
    const event = makeEvent("ORCHESTRATION_QUORUM_REACHED", {
      request_id: "request-1",
      round_id: "round-1",
      proposal_digest: PROPOSAL_DIGEST,
      supporting_orchestrators: ["orchestrator_a", "orchestrator_b"],
      required_quorum: 2,
      quorum_latency_ms: 8,
    }, 5);
    render(<><LiveOrchestrationActivity events={[event]} selectedTraceKey={null} onSelectTrace={vi.fn()} /><DecisionTrace events={[event]} selectedTraceKey={null} onSelectTrace={vi.fn()} incomplete={false} /></>);
    expect(screen.getByText(/Backend quorum-reached fact/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Authoritative terminal result")).not.toBeInTheDocument();
    expect(screen.queryByText("route-opaque-a")).not.toBeInTheDocument();
  });

  it("matching votes cannot override authoritative INSUFFICIENT_RESPONSES", () => {
    const decision = makeDecision({ outcome: "INSUFFICIENT_RESPONSES", reason: "Backend response threshold not met" });
    render(<><LiveOrchestrationActivity events={[voteEvent("orchestrator_a", 1), voteEvent("orchestrator_b", 2)]} selectedTraceKey={null} onSelectTrace={vi.fn()} /><DecisionDetailPanel decision={decision} loading={false} error={null} onClose={vi.fn()} /></>);
    expect(screen.getByLabelText("Authoritative terminal result")).toHaveTextContent("INSUFFICIENT_RESPONSES");
    expect(screen.getByLabelText("Authoritative terminal result")).toHaveTextContent("No route selected");
  });
});

describe("Exact hashes and decision evidence", () => {
  it("exposes the exact digest for inspection and copies the exact value", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<DigestField value={PROPOSAL_DIGEST} label="proposal digest" />);
    expect(screen.getByTitle(PROPOSAL_DIGEST)).toHaveTextContent(`${PROPOSAL_DIGEST.slice(0, 12)}...${PROPOSAL_DIGEST.slice(-8)}`);
    await user.click(screen.getByLabelText("Inspect full proposal digest"));
    expect(screen.getByText(PROPOSAL_DIGEST, { selector: "code" })).toBeInTheDocument();
    await user.click(screen.getByLabelText(`Copy proposal digest: ${PROPOSAL_DIGEST}`));
    expect(writeText).toHaveBeenCalledWith(PROPOSAL_DIGEST);
    expect(screen.getByRole("button", { name: `Copy proposal digest: ${PROPOSAL_DIGEST}` })).toHaveTextContent("Copied");
  });

  it("displays exact proposal/vote hashes, authentication, rejection, participation, and provenance facts", () => {
    const decision = makeDecision({
      proposal_summaries: [makeProposal()],
      vote_summaries: [makeVote({ authentication_verified: false, reason_code: "AUTH_EVIDENCE_REJECTED" })],
      rejections: [{
        schema_version: "orchestrator_message_rejection_v1",
        phase: "VOTE",
        reason_code: "INVALID_AUTHENTICATION_TAG",
        orchestrator_id: "orchestrator_c",
        message_id: "vote-rejected-c",
        detail: "Backend rejected message authentication evidence",
      }],
      supporting_orchestrators: ["orchestrator_a"],
      disagreeing_orchestrators: ["orchestrator_b"],
      timed_out_orchestrators: ["orchestrator_c"],
      delayed_orchestrators: ["orchestrator_d"],
      omitted_orchestrators: ["orchestrator_e"],
      unavailable_orchestrators: ["orchestrator_f"],
      provenance: { source_component: "backend.orchestration", correlation: "trace-authoritative-7" },
    });
    render(<DecisionDetailPanel decision={decision} loading={false} error={null} onClose={vi.fn()} />);
    expect(screen.getAllByText("route-opaque-a")).toHaveLength(2);
    const proposalSection = screen.getByRole("heading", { name: /Exact proposal summaries/ }).parentElement!;
    const voteSection = screen.getByRole("heading", { name: /Exact vote summaries/ }).parentElement!;
    expect(proposalSection).toHaveTextContent("opaque-route-policy@v7");
    expect(proposalSection).toHaveTextContent("POLICY_MATCH");
    expect(voteSection).toHaveTextContent("AUTH_EVIDENCE_REJECTED");
    expect(screen.getByText("INVALID_AUTHENTICATION_TAG")).toBeInTheDocument();
    expect(screen.getByText("Backend rejected message authentication evidence")).toBeInTheDocument();
    expect(screen.getAllByText("false")).toHaveLength(1);
    for (const label of ["Supporting", "Disagreeing", "Timed out", "Delayed after round close", "Omitted messages", "Operationally unavailable"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    for (const participant of ["orchestrator_a", "orchestrator_b", "orchestrator_c", "orchestrator_d", "orchestrator_e", "orchestrator_f"]) {
      expect(screen.getAllByText(participant).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText(PROPOSAL_DIGEST, { selector: "code" }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(PROPOSAL_HASH, { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText(VOTE_HASH, { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText(/trace-authoritative-7/)).toBeInTheDocument();
  });
});

describe("Chronology, trace fidelity, and distinct operational evidence", () => {
  it("orders B/A/C arrival by numeric sequence without scientific or lexicographic comparison", () => {
    const events = [proposalEvent("B", 10), proposalEvent("A", 2), proposalEvent("C", 1000000)];
    render(<LiveOrchestrationActivity events={events} selectedTraceKey={null} onSelectTrace={vi.fn()} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getAllByRole("cell")[0].textContent)).toEqual(["2", "10", "1000000"]);
    expect(rows.map((row) => within(row).getAllByRole("cell")[3].textContent)).toEqual(["A", "B", "C"]);
    expect(screen.queryByText("1e+6")).not.toBeInTheDocument();
  });

  it("does not synthesize a missing event or lifecycle stage in a trace", async () => {
    const events = [requestEvent(1), voteEvent("orchestrator_a", 3)];
    render(<DecisionTrace events={events} selectedTraceKey="request-1:round-1" onSelectTrace={vi.fn()} incomplete={true} />);
    expect(screen.getByRole("alert")).toHaveTextContent("reported gap or local eviction");
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.queryByText("#2")).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("keeps timeout, delay, omission, unavailable, and disagreement concepts distinct", () => {
    const events: OrchestrationEventEnvelopeV1[] = [
      makeEvent("ORCHESTRATOR_TIMEOUT", { request_id: "request-1", round_id: "round-1", orchestrator_id: "orchestrator_a", phase: "ROUND", budget_ms: 100, reason: "NO_USABLE_RESPONSE_BEFORE_TERMINAL_ROUND" }, 1),
      makeEvent("ORCHESTRATOR_DELAYED", { request_id: "request-1", round_id: "round-1", orchestrator_id: "orchestrator_b", phase: "VOTE", reason: "ROUND_CLOSED_AFTER_QUORUM_BEFORE_RESPONSE" }, 2),
      makeEvent("ORCHESTRATOR_OMISSION", { request_id: "request-1", round_id: "round-1", orchestrator_id: "orchestrator_c", phase: "ROUND", reason: "NO_MESSAGE_PRODUCED" }, 3),
      makeEvent("ORCHESTRATOR_STATUS", { request_id: "request-1", round_id: "round-1", orchestrator_id: "orchestrator_d", health: "UNAVAILABLE", available: false, reason: "OPERATIONALLY_UNAVAILABLE" }, 4),
    ];
    render(<><LiveOrchestrationActivity events={events} selectedTraceKey={null} onSelectTrace={vi.fn()} /><DecisionDetailPanel decision={makeDecision({ disagreeing_orchestrators: ["orchestrator_e"] })} loading={false} error={null} onClose={vi.fn()} /></>);
    expect(screen.getByText(/NO_USABLE_RESPONSE_BEFORE_TERMINAL_ROUND/)).toBeInTheDocument();
    expect(screen.getByText(/ROUND_CLOSED_AFTER_QUORUM_BEFORE_RESPONSE/)).toBeInTheDocument();
    expect(screen.getByText(/NO_MESSAGE_PRODUCED/)).toBeInTheDocument();
    expect(screen.getByText(/UNAVAILABLE.*OPERATIONALLY_UNAVAILABLE/)).toBeInTheDocument();
    expect(screen.getByText("Disagreeing").parentElement).toHaveTextContent("orchestrator_e");
  });
});

describe("Bounded retained history and pagination", () => {
  it("uses explicit history_complete warning wording, exposes bounds, and paginates", async () => {
    const user = userEvent.setup();
    const setFilters = vi.fn();
    render(<DecisionBrowser listing={makeListing({ total_retained: 45 })} filters={{ limit: 20, offset: 0 }} loading={false} setFilters={setFilters} onSelect={vi.fn()} />);
    const warning = screen.getByRole("note");
    expect(warning).toHaveTextContent("Bounded, non-durable backend history");
    expect(warning).toHaveTextContent("history_complete=false");
    expect(warning).toHaveTextContent("not an all-time audit count");
    await user.click(screen.getByText("Inspect bounds"));
    expect(screen.getByText(/"history_limit":500/)).toBeInTheDocument();
    expect(screen.getByText("1-1 of 45 retained matches")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(setFilters).toHaveBeenCalledWith(expect.objectContaining({ offset: 20 }));
  });
});

describe("useOrchestration REST and WebSocket behavior", () => {
  it("does not report reconnecting until an unexpected close schedules a retry", async () => {
    vi.useFakeTimers();
    const view = renderHook();
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByTestId("hook-health")).toHaveTextContent("ok");
    expect(screen.getByTestId("hook-replicas")).toHaveTextContent("orchestrator_a,orchestrator_b,orchestrator_c");
    expect(screen.getByTestId("hook-decisions")).toHaveTextContent("decision-1");
    act(() => view.socket().open());
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("OPEN");
    act(() => view.socket().error());
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("OPEN");
    act(() => view.socket().serverClose());
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("RECONNECTING");
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("follows close through the actual retry timer, replacement open, and REST refresh", async () => {
    vi.useFakeTimers();
    const view = renderHook();
    await act(async () => { await Promise.resolve(); });
    const initialSocket = view.socket();
    act(() => initialSocket.open());
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("OPEN");
    expect(screen.getByTestId("hook-health")).toHaveTextContent("ok");
    expect(screen.getByTestId("hook-replicas")).toHaveTextContent("orchestrator_a,orchestrator_b,orchestrator_c");
    expect(screen.getByTestId("hook-decisions")).toHaveTextContent("decision-1");
    const healthCallsBeforeReconnect = vi.mocked(view.client.getOrchestrationHealth).mock.calls.length;

    act(() => initialSocket.serverClose());
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("RECONNECTING");
    expect(screen.getByTestId("hook-health")).toHaveTextContent("ok");
    expect(screen.getByTestId("hook-decisions")).toHaveTextContent("decision-1");
    expect(screen.getByTestId("hook-event-count")).toHaveTextContent("0");
    expect(vi.getTimerCount()).toBe(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(MockWebSocket.instances).toHaveLength(2);
    const replacementSocket = view.socket();
    expect(replacementSocket).not.toBe(initialSocket);
    expect(replacementSocket.url).toBe("ws://localhost:8000/api/v1/replays/orchestration-ops/events");

    await act(async () => {
      replacementSocket.open();
      await Promise.resolve();
    });
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("OPEN");
    expect(vi.mocked(view.client.getOrchestrationHealth).mock.calls.length).toBeGreaterThan(healthCallsBeforeReconnect);
    expect(screen.getByTestId("hook-health")).toHaveTextContent("ok");
    expect(screen.getByTestId("hook-event-count")).toHaveTextContent("0");

    view.unmount();
    expect(MockWebSocket.instances.filter((socket) => socket.readyState !== MockWebSocket.CLOSED)).toHaveLength(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("reports DISCONNECTED only after the bounded retry lifecycle is exhausted", async () => {
    vi.useFakeTimers();
    const view = renderHook();
    await act(async () => { await Promise.resolve(); });
    act(() => {
      view.socket().open();
      view.socket().serverClose();
    });
    expect(screen.getByTestId("hook-connection")).toHaveTextContent("RECONNECTING");

    for (const delay of [1000, 2000, 4000, 8000, 10_000, 10_000]) {
      await act(async () => { await vi.advanceTimersByTimeAsync(delay); });
      act(() => view.socket().serverClose());
    }

    expect(screen.getByTestId("hook-connection")).toHaveTextContent("DISCONNECTED");
    expect(screen.getByTestId("hook-health")).toHaveTextContent("ok");
    expect(screen.getByTestId("hook-decisions")).toHaveTextContent("decision-1");
    expect(screen.getByTestId("hook-event-count")).toHaveTextContent("0");
    expect(vi.getTimerCount()).toBe(0);
    view.unmount();
    expect(MockWebSocket.instances.filter((socket) => socket.readyState !== MockWebSocket.CLOSED)).toHaveLength(0);
  });

  it("uses the fixed orchestration namespace and rejects another replay namespace", async () => {
    const view = renderHook();
    await waitFor(() => expect(screen.getByTestId("hook-health")).toHaveTextContent("ok"));
    expect(view.socket().url).toBe("ws://localhost:8000/api/v1/replays/orchestration-ops/events");
    act(() => {
      view.socket().open();
      view.socket().message({ ...requestEvent(1), replay_id: "scientific-replay-1" });
    });
    expect(screen.getByTestId("hook-event-count")).toHaveTextContent("0");
    expect(OrchestrationEventEnvelopeV1Schema.safeParse({ ...requestEvent(1), replay_id: "scientific-replay-1" }).success).toBe(false);
  });

  it("marks an explicit gap, refreshes REST, preserves loaded REST facts, and fabricates nothing", async () => {
    const view = renderHook();
    await waitFor(() => expect(screen.getByTestId("hook-health")).toHaveTextContent("ok"));
    const healthCalls = vi.mocked(view.client.getOrchestrationHealth).mock.calls.length;
    act(() => {
      view.socket().open();
      view.socket().message(requestEvent(1));
      view.socket().message({ gap_notice: true });
    });
    await waitFor(() => expect(vi.mocked(view.client.getOrchestrationHealth).mock.calls.length).toBeGreaterThan(healthCalls));
    expect(screen.getByTestId("hook-gap")).toHaveTextContent("true");
    expect(screen.getByTestId("hook-health")).toHaveTextContent("ok");
    expect(screen.getByTestId("hook-replicas")).toHaveTextContent("orchestrator_a");
    expect(screen.getByTestId("hook-event-sequences")).toHaveTextContent("1");
  });

  it("caps local events at 500, evicts the oldest, and marks history incomplete", async () => {
    const view = renderHook();
    await waitFor(() => expect(screen.getByTestId("hook-health")).toHaveTextContent("ok"));
    act(() => {
      view.socket().open();
      for (let sequence = 1; sequence <= 501; sequence += 1) {
        view.socket().message(requestEvent(sequence));
      }
    });
    expect(screen.getByTestId("hook-event-count")).toHaveTextContent("500");
    const sequences = screen.getByTestId("hook-event-sequences").textContent?.split(",").map(Number) ?? [];
    expect(sequences[0]).toBe(2);
    expect(sequences.at(-1)).toBe(501);
    expect(sequences).not.toContain(1);
    expect(screen.getByTestId("hook-incomplete")).toHaveTextContent("true");
  });

  it("rejects malformed orchestration events and drops duplicate/backward sequences", async () => {
    const view = renderHook();
    await waitFor(() => expect(screen.getByTestId("hook-health")).toHaveTextContent("ok"));
    const malformed = {
      ...requestEvent(1),
      event_type: "ORCHESTRATOR_PROPOSAL",
      payload: { request_id: "request-1", round_id: "round-1" },
    };
    act(() => {
      view.socket().open();
      view.socket().message(malformed);
    });
    expect(screen.getByTestId("hook-error")).toHaveTextContent("Malformed orchestration event rejected by the Stage-7 contract");
    act(() => {
      view.socket().message(requestEvent(2));
      view.socket().message({ ...requestEvent(2), event_id: "duplicate-sequence-two" });
      view.socket().message(requestEvent(1));
      view.socket().message(requestEvent(3));
    });
    expect(screen.getByTestId("hook-event-count")).toHaveTextContent("2");
    expect(screen.getByTestId("hook-event-sequences")).toHaveTextContent("2,3");
  });

  it("cleans sockets and reconnect timers so repeated mount/unmount leaves only one active socket", async () => {
    vi.useFakeTimers();
    const first = renderHook();
    await act(async () => { await Promise.resolve(); });
    act(() => first.socket().serverClose());
    first.unmount();
    expect(vi.getTimerCount()).toBe(0);

    const second = renderHook();
    await act(async () => { await Promise.resolve(); });
    second.unmount();
    const third = renderHook();
    await act(async () => { await Promise.resolve(); });
    const active = MockWebSocket.instances.filter((socket) => socket.readyState !== MockWebSocket.CLOSED);
    expect(active).toHaveLength(1);
    expect(active[0]).toBe(third.socket());
    third.unmount();
    expect(MockWebSocket.instances.filter((socket) => socket.readyState !== MockWebSocket.CLOSED)).toHaveLength(0);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("Dashboard navigation regression", () => {
  it("keeps Device, Blackboard, and Orchestration navigation plus replay/security placeholders", async () => {
    const user = userEvent.setup();
    const client = makeClient();
    vi.spyOn(client, "getSessions").mockResolvedValue({
      sessions: [{
        session_id: "session-1",
        session_trace: "trace-1",
        feature_store_available: true,
        raw_available: true,
        network_available: true,
        behavior_available: true,
        communication_available: true,
        schema_compatible: true,
        window_count: 13,
        duration_seconds: 65,
        supported_source_modes: ["feature_store"],
      }],
      default_session: "session-1",
    });
    vi.spyOn(client, "getHealth").mockResolvedValue({ service: "dashboard", api_version: "v1", contract_versions: {}, active_replay: null, active_replay_starting: false, artifact_readiness: {}, scientific_ready: true });
    vi.spyOn(client, "listSnapshots").mockResolvedValue({ snapshots: [] });
    vi.spyOn(client, "getBlackboardHealth").mockRejectedValue(new Error("not needed for navigation"));
    vi.spyOn(client, "getBlackboardSnapshot").mockRejectedValue(new Error("not needed for navigation"));
    vi.spyOn(client, "getBlackboardReplicas").mockRejectedValue(new Error("not needed for navigation"));
    vi.spyOn(client, "listBlackboardRecords").mockRejectedValue(new Error("not needed for navigation"));

    render(<ReplayProvider client={client}><DashboardPage /></ReplayProvider>);
    expect(screen.getByTestId("srep-mode-badge")).toHaveTextContent("SREP MODE: DEVICE_ONLY");
    const placeholder = screen.getByLabelText("Agent Trust Graph placeholder");
    expect(placeholder).toHaveAttribute("aria-disabled", "true");
    expect(placeholder).toHaveTextContent("Not yet implemented");
    for (const control of ["Create", "Play", "Pause", "Step", "Restart", "Save snapshot"]) {
      expect(screen.getByRole("button", { name: control })).toBeInTheDocument();
    }
    expect(screen.getByRole("tab", { name: "Device View" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("tab", { name: "Blackboard" }));
    expect(screen.getByRole("tabpanel", { name: "Blackboard" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Orchestration" }));
    expect(screen.getByRole("tabpanel", { name: "Orchestration" })).toBeInTheDocument();
    expect(await screen.findByTestId("orchestration-view")).toBeInTheDocument();
    expect(screen.getByText("Three-orchestrator adjudication")).toBeInTheDocument();
  });
});
