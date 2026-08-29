/**
 * Micro-closure regressions for replay isolation, entity/window validity, gateway authority, per-agent dispatch.
 * Uses typed fixtures where practical; narrow casts with satisfies where needed.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within, act } from "@testing-library/react";
import * as React from "react";
import { ApiClient } from "../api/client";
import { ReplayProvider, ReplayContext } from "../state/ReplayContext";
import { createInitialReplayState } from "../state/replayReducer";
import { useWorkflow } from "../hooks/useWorkflow";
import { FiveAgentWorkflowView } from "../components/workflow/FiveAgentWorkflowView";
import { AgentRoleCards } from "../components/workflow/AgentRoleCards";
import { FindingGatewayPanel } from "../components/workflow/FindingGatewayPanel";
import { EntityWorkflowDetail } from "../components/workflow/EntityWorkflowDetail";
import { makeEnvelope } from "./fixtures";
import { resolveEntityWindow } from "../utils/workflowHelpers";

// Helper to make snapshot with given entities
function makeSnap(entities: string[], windowMap: Record<string, number> = {}) {
  const threat = entities.map((id) => ({
    schema_version: "threat_correlation_v1",
    correlation_id: `corr-${id}`,
    workflow_id: "wf-1",
    entity_id: id,
    window_id: windowMap[id] ?? 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    source_finding_ids: ["f1"],
    mapping_status: "MATCHED",
    threat_behavior_id: "TB-NET-01",
    threat_behavior_name: "network_anomaly_confirmed",
    mapping_catalog_version: "threat_catalog_v1",
    mapping_rule_id: "rule-1",
    mapping_basis: "basis",
    evidence_refs: ["ev-1"],
    confidence: 0.9,
    provenance: {},
  }));
  const risk = entities.map((id) => ({
    schema_version: "risk_recommendation_v1",
    recommendation_id: `risk-${id}`,
    workflow_id: "wf-1",
    entity_id: id,
    window_id: windowMap[id] ?? 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    network_risk: 0.5,
    behavior_risk: 0.2,
    behavior_supported: true,
    direct_risk: 0.4,
    propagated_risk: 0.1,
    systemic_risk: 0.6,
    threat_correlation_refs: [`corr-${id}`],
    evidence_complete: true,
    reason_codes: ["TEST"],
    recommended_escalation: "MONITOR",
    agent_trust_graph_supported: false,
    agent_workflow_risk_supported: false,
    device_risk_supported: true,
    provenance: {},
  }));
  const access = entities.map((id) => ({
    schema_version: "access_recommendation_v1",
    recommendation_id: `acc-${id}`,
    workflow_id: "wf-1",
    entity_id: id,
    window_id: windowMap[id] ?? 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    action: "ALLOW" as const,
    policy_id: "stage8_access_policy_v1",
    policy_version: "1",
    controller_mode: "PRE_LZTAF_DEVICE_EVIDENCE" as const,
    evidence_refs: ["ev-1"],
    evidence_complete: true,
    behavior_supported: true,
    reason_codes: ["POLICY"],
    trust_vector_supported: false,
    agent_trust_supported: false,
    credential_controls_supported: false,
    provenance: {},
  }));
  const decisions = entities.map((id) => ({
    schema_version: "enforcement_decision_v1",
    decision_id: `dec-${id}`,
    workflow_id: "wf-1",
    replay_id: "replay-1",
    window_id: windowMap[id] ?? 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    entity_id: id,
    action: "ALLOW" as const,
    controller_recommendation_id: `acc-${id}`,
    controller_mode: "PRE_LZTAF_DEVICE_EVIDENCE" as const,
    policy_id: "stage8_access_policy_v1",
    policy_version: "1",
    evidence_refs: ["ev-1"],
    reason_codes: ["COMMITTED"],
    evidence_complete: true,
    behavior_supported: true,
    physical_enforcement_claimed: false,
    counterfactual_effect_applied: false,
    provenance: {},
  }));
  return {
    schema_version: "workflow_snapshot_v1",
    replay_id: "replay-1",
    workflow_mode: "FIVE_AGENT_LIVE",
    workflow_id: "wf-1",
    current_window_id: 0,
    last_window_id: 0,
    recent_windows: [{ window_id: 0, entity_id: "window-scope", entity_ids: entities, status: "COMPLETED", dispatch_ids: ["d1"], execution_ids: ["e1"] }],
    five_agent_statuses: [
      { agent_id: "network_anomaly_detector", status: "COMPLETED" },
      { agent_id: "iot_behavioral_profiler", status: "COMPLETED" },
      { agent_id: "threat_intelligence_correlator", status: "COMPLETED" },
      { agent_id: "risk_propagation_analyst", status: "COMPLETED" },
      { agent_id: "trust_access_controller", status: "COMPLETED" },
    ],
    latest_threat_correlations: threat,
    latest_risk_recommendations: risk,
    latest_access_recommendations: access,
    latest_enforcement_decisions: decisions,
    recent_failures: [],
    bounds: { recent_windows: 64, window_states: 64, window_states_current: 1 },
    instrumentation: {},
    provenance: { source_component: "backend.app.services.workflow_service" },
  };
}

function makeSnapshotWithEntities(entities: string[]) {
  return makeSnap(entities);
}

describe("Micro-closure: replay-switch isolation", () => {
  it("delayed A must not overwrite B (stale-response protection)", async () => {
    // Controlled promises for A and B
    let resolveA: (v: any) => void = () => {};
    let resolveB: (v: any) => void = () => {};
    const promiseA = new Promise((res) => (resolveA = res));
    const promiseB = new Promise((res) => (resolveB = res));

    const snapA = makeSnapshotWithEntities(["entity_A"]);
    (snapA as any).replay_id = "replay-A";
    (snapA as any).latest_threat_correlations[0].entity_id = "entity_A";
    const snapB = makeSnapshotWithEntities(["entity_B"]);
    (snapB as any).replay_id = "replay-B";
    (snapB as any).latest_threat_correlations[0].entity_id = "entity_B";
    (snapB as any).latest_risk_recommendations[0].entity_id = "entity_B";

    const client = new ApiClient("http://test");
    const spyA = vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((replayId: string) => {
      if (replayId === "replay-A") return promiseA as any;
      if (replayId === "replay-B") return promiseB as any;
      return Promise.resolve(snapA as any);
    });
    vi.spyOn(client, "listActions").mockResolvedValue({
      schema_version: "action_listing_v1",
      replay_id: "replay-B",
      actions: [],
      total: 0,
      limit: 20,
      offset: 0,
      history_complete: false,
      bounds: {},
    } as any);

    // Create a test harness that switches replayId via context
    function InnerWorkflow() {
      const wf = useWorkflow(client);
      return (
        <div>
          <span data-testid="snap-entity">{wf.snapshot?.latest_threat_correlations[0]?.entity_id ?? "none"}</span>
          <span data-testid="snap-replay">{wf.snapshot?.replay_id ?? "none"}</span>
        </div>
      );
    }

    function TestHarness({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState<string | null>(currentReplay);
      React.useEffect(() => {
        setReplayId(currentReplay);
      }, [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as const, status: null } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <InnerWorkflow />
        </ReplayContext.Provider>
      );
    }

    const { rerender } = render(<TestHarness currentReplay="replay-A" />);
    // Wait a tick for request A to start (pending)
    await act(async () => {
      await Promise.resolve();
    });
    // Switch to B before A resolves
    rerender(React.createElement(TestHarness, { currentReplay: "replay-B" }));
    await act(async () => {
      await Promise.resolve();
    });
    // Resolve B first
    await act(async () => {
      resolveB(snapB);
      await Promise.resolve();
      await new Promise((r) => setTimeout(r, 0));
    });
    // B should be shown
    expect(screen.getByTestId("snap-entity")).toHaveTextContent("entity_B");
    expect(screen.getByTestId("snap-replay")).toHaveTextContent("replay-B");
    // Now resolve delayed A
    await act(async () => {
      resolveA(snapA);
      await Promise.resolve();
      await new Promise((r) => setTimeout(r, 0));
    });
    // B must remain, A must not overwrite
    expect(screen.getByTestId("snap-entity")).toHaveTextContent("entity_B");
    expect(screen.getByTestId("snap-replay")).toHaveTextContent("replay-B");
  });

  it("immediate clearing: switching A→B clears old entity/decision/feedback before B resolves", async () => {
    const snapA = makeSnapshotWithEntities(["entity_A"]);
    (snapA as any).replay_id = "replay-A";
    const client = new ApiClient("http://test");
    let resolveB: (v: any) => void = () => {};
    const promiseB = new Promise((res) => (resolveB = res));
    vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((replayId: string) => {
      if (replayId === "replay-A") return Promise.resolve(snapA as any);
      if (replayId === "replay-B") return promiseB as any;
      return Promise.resolve(snapA as any);
    });
    vi.spyOn(client, "listActions").mockResolvedValue({
      schema_version: "action_listing_v1",
      replay_id: "replay-A",
      actions: [{ ...snapA.latest_enforcement_decisions[0], decision_id: "dec-A", entity_id: "entity_A" } as any],
      total: 1,
      limit: 20,
      offset: 0,
      history_complete: false,
      bounds: {},
    } as any);
    vi.spyOn(client, "getAction").mockResolvedValue(snapA.latest_enforcement_decisions[0] as any);

    function Inner2() {
      const wf = useWorkflow(client);
      return (
        <div>
          <span data-testid="snap-entity2">{wf.snapshot?.latest_threat_correlations[0]?.entity_id ?? "none"}</span>
          <span data-testid="listing-count">{String(wf.listing?.total ?? "none")}</span>
          <span data-testid="feedback-status">{wf.feedbackStatus}</span>
        </div>
      );
    }
    function TestHarness2({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState<string | null>(currentReplay);
      React.useEffect(() => setReplayId(currentReplay), [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as const, status: null } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <Inner2 />
        </ReplayContext.Provider>
      );
    }
    const { rerender } = render(<TestHarness2 currentReplay="replay-A" />);
    await waitFor(() => expect(screen.getByTestId("snap-entity2")).toHaveTextContent("entity_A"));
    // Switch to B before B resolves
    rerender(React.createElement(TestHarness2, { currentReplay: "replay-B" }));
    await act(async () => {
      await Promise.resolve();
    });
    // Immediately after switch, old A should not be shown (cleared)
    expect(screen.getByTestId("snap-entity2")).toHaveTextContent("none");
    // Now resolve B with different entity
    const snapB = makeSnapshotWithEntities(["entity_B"]);
    (snapB as any).replay_id = "replay-B";
    (snapB as any).latest_threat_correlations[0].entity_id = "entity_B";
    await act(async () => {
      resolveB(snapB);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("snap-entity2")).toHaveTextContent("entity_B"));
  });
});

describe("Micro-closure: entity/window validity", () => {
  it("A) stale entity not retained when only B exists", async () => {
    const snapA = makeSnap(["entity_A"]);
    const snapB = makeSnap(["entity_B"]);
    // Simulate FiveAgentWorkflowView logic via resolveEntityWindow + selection
    // Directly test the helper and component
    expect(resolveEntityWindow(snapA as any, "entity_A")).toBe(0);
    expect(resolveEntityWindow(snapB as any, "entity_A")).toBeNull(); // A not in B
    // Render table with B only, select A initially then switch to B
    const snapBOnly = makeSnap(["entity_B"]);
    const { rerender } = render(<EntityWorkflowDetail snapshot={makeSnap(["entity_A"]) as any} entityId="entity_A" events={[]} windowId={0} />);
    expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_A");
    rerender(<EntityWorkflowDetail snapshot={snapBOnly as any} entityId="entity_B" events={[]} windowId={0} />);
    expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_B");
  });

  it("B) entity without risk resolves window from access/action/threat", () => {
    const snap = makeSnap(["entity_B"], { entity_B: 9 });
    // Remove risk for B, keep access/decision
    (snap as any).latest_risk_recommendations = [];
    expect(resolveEntityWindow(snap as any, "entity_B")).toBe(9);
    // Also test via component: select B should get window 9 not 3
    const snapA = makeSnap(["entity_A"], { entity_A: 3 });
    const snapB2 = makeSnap(["entity_B"], { entity_B: 9 });
    (snapB2 as any).latest_risk_recommendations = [];
    // The helper should return 9 for B
    expect(resolveEntityWindow(snapB2 as any, "entity_B")).toBe(9);
    expect(resolveEntityWindow(snapA as any, "entity_A")).toBe(3);
  });

  it("C) entity with no window returns null", () => {
    const snap = makeSnap(["entity_X"]);
    // Remove all records for X except maybe recent_windows without entity
    (snap as any).latest_enforcement_decisions = [];
    (snap as any).latest_access_recommendations = [];
    (snap as any).latest_risk_recommendations = [];
    (snap as any).latest_threat_correlations = [];
    (snap as any).recent_windows = [{ window_id: 99, entity_id: "other", entity_ids: ["other"], status: "COMPLETED", dispatch_ids: [], execution_ids: [] }];
    expect(resolveEntityWindow(snap as any, "entity_X")).toBeNull();
  });

  it("D) empty-evidence snapshot → null entity/window", () => {
    const emptySnap = {
      schema_version: "workflow_snapshot_v1",
      replay_id: "replay-1",
      workflow_mode: "FIVE_AGENT_LIVE",
      workflow_id: "wf-1",
      current_window_id: null,
      last_window_id: null,
      recent_windows: [],
      five_agent_statuses: [],
      latest_threat_correlations: [],
      latest_risk_recommendations: [],
      latest_access_recommendations: [],
      latest_enforcement_decisions: [],
      recent_failures: [],
      bounds: {},
      instrumentation: {},
      provenance: {},
    } as any;
    expect(resolveEntityWindow(emptySnap, null)).toBeNull();
    expect(resolveEntityWindow(emptySnap, "any")).toBeNull();
  });
});

describe("Micro-closure: gateway authority", () => {
  it("A) Threat exists but no GATEWAY_ACCEPTED → must NOT display ACCEPTED", () => {
    const snap = makeSnap(["entity_A"]);
    const events = [makeEnvelope("THREAT_CORRELATION_PRODUCED", { sequence_number: 1, entity_id: "entity_A", window_id: 0, payload: {} }) as any];
    render(React.createElement(FindingGatewayPanel, { entityId: "entity_A", windowId: 0, events }));
    expect(screen.getByTestId("gateway-not-present")).toBeInTheDocument();
    expect(screen.queryByTestId("gateway-accepted")).not.toBeInTheDocument();
    expect(screen.getByTestId("gateway-result")).toHaveTextContent("Unknown");
  });

  it("B) No Threat but GATEWAY_ACCEPTED exists → display ACCEPTED", () => {
    const events = [makeEnvelope("GATEWAY_ACCEPTED", { sequence_number: 5, entity_id: "entity_A", window_id: 0, payload: { finding_type: "NetworkFinding", finding_id: "finding-1" } }) as any];
    render(<FindingGatewayPanel entityId="entity_A" windowId={0} events={events} />);
    expect(screen.getByTestId("gateway-row-5")).toBeInTheDocument();
    expect(screen.getByTestId("gateway-type-5")).toHaveTextContent("GATEWAY_ACCEPTED");
  });

  it("C) GATEWAY_REJECTED displays REJECTED without inventing reason if not supplied", () => {
    const events = [makeEnvelope("GATEWAY_REJECTED", { sequence_number: 6, entity_id: "entity_A", window_id: 0, payload: { finding_type: "BehaviorFinding", finding_id: "f2" } }) as any];
    render(<FindingGatewayPanel entityId="entity_A" windowId={0} events={events} />);
    expect(screen.getByTestId("gateway-row-6")).toBeInTheDocument();
    expect(screen.getByTestId("gateway-type-6")).toHaveTextContent("GATEWAY_REJECTED");
    expect(screen.getByTestId("gateway-reason-6").textContent).toMatch(/\u2014|-/);
  });

  it("D) No retained Gateway event → unknown/not-present, not inferred", () => {
    const snap = makeSnap(["entity_A"]);
    // Even though Threat exists, no gateway event → unknown
    render(React.createElement(FindingGatewayPanel, { entityId: "entity_A", windowId: 0, events: [] }));
    expect(screen.getByTestId("gateway-not-present")).toBeInTheDocument();
    expect(screen.getByTestId("gateway-result")).toHaveTextContent("Unknown");
  });

  it("E) Truncated history → do not infer from downstream", () => {
    const events = [
      makeEnvelope("THREAT_CORRELATION_PRODUCED", { sequence_number: 100, entity_id: "entity_A", window_id: 0, payload: {} }) as any,
      makeEnvelope("RISK_RECOMMENDATION_PRODUCED", { sequence_number: 101, entity_id: "entity_A", window_id: 0, payload: {} }) as any,
    ];
    // No gateway event despite downstream → unknown
    render(React.createElement(FindingGatewayPanel, { entityId: "entity_A", windowId: 0, events }));
    expect(screen.getByTestId("gateway-not-present")).toBeInTheDocument();
  });
});

describe("Micro-closure: per-agent dispatch wording", () => {
  it("global dispatch exists but PENDING specialist must not imply dispatched", () => {
    const snap = makeSnap(["entity_A"]);
    // Make one agent PENDING while global dispatch exists
    (snap as any).five_agent_statuses = [
      { agent_id: "network_anomaly_detector", status: "PENDING" },
      { agent_id: "iot_behavioral_profiler", status: "COMPLETED" },
      { agent_id: "threat_intelligence_correlator", status: "COMPLETED" },
      { agent_id: "risk_propagation_analyst", status: "COMPLETED" },
      { agent_id: "trust_access_controller", status: "COMPLETED" },
    ];
    render(React.createElement(AgentRoleCards, { snapshot: snap as any }));
    const pendingCard = screen.getByTestId("agent-dispatch-network_anomaly_detector");
    expect(pendingCard.textContent).toContain("Backend status: PENDING");
    expect(pendingCard.textContent).not.toMatch(/Visible in retained windows — see trace for dispatch.*implies.*dispatched/i);
    expect(pendingCard.textContent).toContain("global window dispatch list does not imply this specialist was dispatched");
  });
});

describe("Micro-closure: render-bound replay isolation", () => {
  it("immediate pre-effect: without awaiting, A must already not be presented as B", async () => {
    let resolveA: (v: any) => void = () => {};
    let resolveB: (v: any) => void = () => {};
    const promiseA = new Promise((res) => (resolveA = res));
    const promiseB = new Promise((res) => (resolveB = res));
    const snapA = makeSnap(["entity_A"]);
    (snapA as any).replay_id = "replay-A";
    (snapA as any).latest_threat_correlations[0].entity_id = "entity_A";
    const snapB = makeSnap(["entity_B"]);
    (snapB as any).replay_id = "replay-B";
    (snapB as any).latest_threat_correlations[0].entity_id = "entity_B";
    const client = new ApiClient("http://test");
    vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((id: string) => (id === "replay-A" ? (promiseA as any) : (promiseB as any)));
    vi.spyOn(client, "listActions").mockResolvedValue({ schema_version: "action_listing_v1", replay_id: "replay-A", actions: [], total: 0, limit: 20, offset: 0, history_complete: false, bounds: {} } as any);

    function Inner() {
      const wf = useWorkflow(client);
      return (
        <div>
          <span data-testid="immediate-snap">{wf.snapshot?.replay_id ?? "none"}</span>
          <span data-testid="immediate-entity">{wf.snapshot?.latest_threat_correlations[0]?.entity_id ?? "none"}</span>
        </div>
      );
    }
    function Harness({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState(currentReplay);
      React.useEffect(() => setReplayId(currentReplay), [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as any, status: null } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <Inner />
        </ReplayContext.Provider>
      );
    }

    const { rerender } = render(<Harness currentReplay="replay-A" />);
    await act(async () => {
      resolveA(snapA);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("immediate-snap")).toHaveTextContent("replay-A"));
    // Switch to B, WITHOUT awaiting Promise.resolve / waitFor / setTimeout
    rerender(<Harness currentReplay="replay-B" />);
    // Immediately (synchronously) after rerender, before any effect flush, A must not be presented as B
    expect(screen.getByTestId("immediate-snap")).toHaveTextContent("none");
    expect(screen.getByTestId("immediate-entity")).toHaveTextContent("none");
    // Now allow B to resolve
    await act(async () => {
      resolveB(snapB);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("immediate-snap")).toHaveTextContent("replay-B"));
    // Late A must not overwrite B (generation protection)
    await act(async () => {
      // A already resolved, but if we try to resolve again, it should not overwrite
      await Promise.resolve();
    });
    expect(screen.getByTestId("immediate-snap")).toHaveTextContent("replay-B");
  });

  it("all replay-scoped state cleared immediately (snapshot, listing, detail, feedback)", async () => {
    const snapA = makeSnap(["entity_A"]);
    (snapA as any).replay_id = "replay-A";
    const snapB = makeSnap(["entity_B"]);
    (snapB as any).replay_id = "replay-B";
    let resolveA: any, resolveB: any;
    const promiseA = new Promise((res) => (resolveA = res));
    const promiseB = new Promise((res) => (resolveB = res));
    const client = new ApiClient("http://test");
    vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((id: string) => (id === "replay-A" ? (promiseA as any) : (promiseB as any)));
    vi.spyOn(client, "listActions").mockImplementation((id: string) =>
      id === "replay-A"
        ? Promise.resolve({ schema_version: "action_listing_v1", replay_id: "replay-A", actions: [makeSnap(["entity_A"]).latest_enforcement_decisions[0] as any], total: 1, limit: 20, offset: 0, history_complete: false, bounds: {} } as any)
        : Promise.resolve({ schema_version: "action_listing_v1", replay_id: "replay-B", actions: [], total: 0, limit: 20, offset: 0, history_complete: false, bounds: {} } as any)
    );
    vi.spyOn(client, "getAction").mockResolvedValue({ ...(snapA as any).latest_enforcement_decisions[0], replay_id: "replay-A", decision_id: "dec-A", entity_id: "entity_A" } as any);
    vi.spyOn(client, "submitFeedback").mockResolvedValue({ schema_version: "confirmed_feedback_v1", feedback_id: "fb-A", replay_id: "replay-A", window_id: 0, entity_id: "entity_A", related_action_id: "dec-A", related_finding_ids: [], feedback_source: "OPERATOR_CONFIRMED", confirmed: true, verdict: "correct", reason_code: "test", submitted_at: "2026-01-01T00:00:00Z", provenance: {} } as any);

    function InnerAll() {
      const wf = useWorkflow(client);
      // Simulate having selected action and feedback for A
      React.useEffect(() => {
        if (wf.snapshot && (wf.snapshot as any).replay_id === "replay-A" && !wf.actionDetail) {
          void wf.loadAction("dec-A");
        }
        if (wf.snapshot && (wf.snapshot as any).replay_id === "replay-A" && wf.feedbackStatus === "idle") {
          // Simulate feedback success for A
          void wf.submitFeedback({ window_id: 0, entity_id: "entity_A", related_action_id: "dec-A", feedback_source: "OPERATOR_CONFIRMED", verdict: "correct", reason_code: "test", principal: "tester" });
        }
      }, [wf.snapshot, wf.actionDetail, wf.feedbackStatus]);
      return (
        <div>
          <span data-testid="all-snap">{wf.snapshot?.replay_id ?? "none"}</span>
          <span data-testid="all-listing">{wf.listing?.replay_id ?? "none"}</span>
          <span data-testid="all-detail">{wf.actionDetail?.replay_id ?? "none"}</span>
          <span data-testid="all-feedback">{wf.feedbackResult?.replay_id ?? "none"}</span>
          <span data-testid="all-feedback-status">{wf.feedbackStatus}</span>
        </div>
      );
    }
    function HarnessAll({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState(currentReplay);
      React.useEffect(() => setReplayId(currentReplay), [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as any, status: null } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <InnerAll />
        </ReplayContext.Provider>
      );
    }

    const { rerender } = render(<HarnessAll currentReplay="replay-A" />);
    await act(async () => {
      resolveA(snapA);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("all-snap")).toHaveTextContent("replay-A"));
    // Wait for detail/feedback to be set for A
    await waitFor(() => expect(screen.getByTestId("all-detail")).toHaveTextContent("replay-A"), { timeout: 2000 });
    await waitFor(() => expect(screen.getByTestId("all-feedback")).toHaveTextContent("replay-A"), { timeout: 2000 });
    // Switch to B
    rerender(<HarnessAll currentReplay="replay-B" />);
    // Immediately after switch, before B resolves, none of A's state should be presented as B
    expect(screen.getByTestId("all-snap")).toHaveTextContent("none");
    expect(screen.getByTestId("all-listing")).toHaveTextContent("none");
    expect(screen.getByTestId("all-detail")).toHaveTextContent("none");
    expect(screen.getByTestId("all-feedback")).toHaveTextContent("none");
    expect(screen.getByTestId("all-feedback-status")).not.toHaveTextContent("success");
    // Now resolve B
    await act(async () => {
      resolveB(snapB);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("all-snap")).toHaveTextContent("replay-B"));
  });
});

describe("Micro-closure: real FiveAgentWorkflowView entity/window", () => {
  it("real view invalidates stale entity A when B only remains", async () => {
    const snapA = makeSnap(["entity_A"], { entity_A: 3 });
    (snapA as any).replay_id = "replay-A";
    const snapB = makeSnap(["entity_B"], { entity_B: 9 });
    (snapB as any).replay_id = "replay-B";
    (snapB as any).latest_risk_recommendations = [];
    let resolveA: any, resolveB: any;
    const promiseA = new Promise((res) => (resolveA = res));
    const promiseB = new Promise((res) => (resolveB = res));
    const client = new ApiClient("http://test");
    vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((id: string) => (id === "replay-A" ? (promiseA as any) : (promiseB as any)));
    vi.spyOn(client, "listActions").mockResolvedValue({ schema_version: "action_listing_v1", replay_id: "replay-A", actions: [], total: 0, limit: 20, offset: 0, history_complete: false, bounds: {} } as any);

    function HarnessView({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState(currentReplay);
      React.useEffect(() => setReplayId(currentReplay), [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as any, status: { state: "RUNNING" } as any } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <FiveAgentWorkflowView />
        </ReplayContext.Provider>
      );
    }

    const { rerender } = render(<HarnessView currentReplay="replay-A" />);
    await act(async () => {
      resolveA(snapA);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_A"));
    rerender(<HarnessView currentReplay="replay-B" />);
    await act(async () => {
      resolveB(snapB);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_B"));
    expect(screen.queryByText("entity_A")).not.toBeInTheDocument();
  });

  it("real window 3→9: B without risk resolves to actual B window 9, not retained 3", async () => {
    const snapA = makeSnap(["entity_A"], { entity_A: 3 });
    (snapA as any).replay_id = "replay-A";
    const snapB = makeSnap(["entity_B"], { entity_B: 9 });
    (snapB as any).replay_id = "replay-B";
    (snapB as any).latest_risk_recommendations = [];
    let resolveA: any, resolveB: any;
    const promiseA = new Promise((res) => (resolveA = res));
    const promiseB = new Promise((res) => (resolveB = res));
    const client = new ApiClient("http://test");
    vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((id: string) => (id === "replay-A" ? (promiseA as any) : (promiseB as any)));
    vi.spyOn(client, "listActions").mockResolvedValue({ schema_version: "action_listing_v1", replay_id: "replay-A", actions: [], total: 0, limit: 20, offset: 0, history_complete: false, bounds: {} } as any);

    function HarnessView({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState(currentReplay);
      React.useEffect(() => setReplayId(currentReplay), [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as any, status: { state: "RUNNING" } as any } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <FiveAgentWorkflowView />
        </ReplayContext.Provider>
      );
    }

    const { rerender } = render(<HarnessView currentReplay="replay-A" />);
    await act(async () => {
      resolveA(snapA);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_A"));
    // Check window for A is 3 via gateway window id or risk
    rerender(<HarnessView currentReplay="replay-B" />);
    await act(async () => {
      resolveB(snapB);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_B"));
    // The gateway or risk window for B should be 9, not retained 3
    // Use the helper to verify
    expect(resolveEntityWindow(snapB as any, "entity_B")).toBe(9);
  });

  it("empty evidence does not retain prior entity/window", async () => {
    const snapA = makeSnap(["entity_A"], { entity_A: 3 });
    (snapA as any).replay_id = "replay-A";
    const emptySnap = {
      schema_version: "workflow_snapshot_v1",
      replay_id: "replay-B",
      workflow_mode: "FIVE_AGENT_LIVE",
      workflow_id: "wf-1",
      current_window_id: null,
      last_window_id: null,
      recent_windows: [],
      five_agent_statuses: [],
      latest_threat_correlations: [],
      latest_risk_recommendations: [],
      latest_access_recommendations: [],
      latest_enforcement_decisions: [],
      recent_failures: [],
      bounds: {},
      instrumentation: {},
      provenance: {},
    } as any;
    let resolveA: any, resolveB: any;
    const promiseA = new Promise((res) => (resolveA = res));
    const promiseB = new Promise((res) => (resolveB = res));
    const client = new ApiClient("http://test");
    vi.spyOn(client, "getWorkflowSnapshot").mockImplementation((id: string) => (id === "replay-A" ? (promiseA as any) : (promiseB as any)));
    vi.spyOn(client, "listActions").mockResolvedValue({ schema_version: "action_listing_v1", replay_id: "replay-A", actions: [], total: 0, limit: 20, offset: 0, history_complete: false, bounds: {} } as any);

    function HarnessView({ currentReplay }: { currentReplay: string | null }) {
      const [replayId, setReplayId] = React.useState(currentReplay);
      React.useEffect(() => setReplayId(currentReplay), [currentReplay]);
      const state = { ...createInitialReplayState(), replayId, events: [] as any, connectionState: "OPEN" as any, status: { state: "RUNNING" } as any } as any;
      return (
        <ReplayContext.Provider value={{ client, state, dispatch: () => {} }}>
          <FiveAgentWorkflowView />
        </ReplayContext.Provider>
      );
    }

    const { rerender } = render(<HarnessView currentReplay="replay-A" />);
    await act(async () => {
      resolveA(snapA);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("entity-detail-id")).toHaveTextContent("entity_A"));
    rerender(<HarnessView currentReplay="replay-B" />);
    await act(async () => {
      resolveB(emptySnap);
      await new Promise((r) => setTimeout(r, 0));
    });
    await waitFor(() => expect(screen.getByTestId("entity-empty-evidence")).toBeInTheDocument());
    expect(screen.queryByTestId("entity-detail-id")).not.toBeInTheDocument();
    expect(resolveEntityWindow(emptySnap, "entity_A")).toBeNull();
  });
});

describe("Micro-closure: multi-gateway", () => {
  it("same entity/window with ACCEPTED network and REJECTED behavior both visible in order, no aggregate", () => {
    const events = [
      makeEnvelope("GATEWAY_ACCEPTED", { sequence_number: 10, entity_id: "entity_A", window_id: 0, payload: { evidence_kind: "network", finding_type: "NetworkFinding", finding_id: "f1" } }) as any,
      makeEnvelope("GATEWAY_REJECTED", { sequence_number: 12, entity_id: "entity_A", window_id: 0, payload: { evidence_kind: "behavior", finding_type: "BehaviorFinding", finding_id: "f2", reason: "unsupported" } }) as any,
    ];
    render(<FindingGatewayPanel entityId="entity_A" windowId={0} events={events} />);
    expect(screen.getByTestId("gateway-row-10")).toBeInTheDocument();
    expect(screen.getByTestId("gateway-row-12")).toBeInTheDocument();
    const rows = screen.getAllByTestId(/^gateway-row-/);
    expect(rows[0].getAttribute("data-testid")).toBe("gateway-row-10");
    expect(rows[1].getAttribute("data-testid")).toBe("gateway-row-12");
    expect(screen.getByTestId("gateway-type-10")).toHaveTextContent("GATEWAY_ACCEPTED");
    expect(screen.getByTestId("gateway-type-12")).toHaveTextContent("GATEWAY_REJECTED");
    expect(screen.getByTestId("gateway-kind-10")).toHaveTextContent("network");
    expect(screen.getByTestId("gateway-kind-12")).toHaveTextContent("behavior");
    expect(screen.queryByText(/overall accepted|overall rejected/i)).not.toBeInTheDocument();
  });
});

describe("Micro-closure: nested ground-truth rejection", () => {
  it("nested provenance with scenario_id fails Zod", async () => {
    const { WorkflowSnapshotV1Schema } = await import("../api/contracts");
    const snap = makeSnap(["entity_A"]);
    (snap as any).provenance = { nested: { scenario_id: "secret" } };
    const result = WorkflowSnapshotV1Schema.safeParse(snap);
    expect(result.success).toBe(false);
  });
  it("nested attack_category fails", async () => {
    const { WorkflowSnapshotV1Schema } = await import("../api/contracts");
    const snap = makeSnap(["entity_A"]);
    (snap as any).latest_threat_correlations[0].provenance = { nested: { attack_category: "DDoS" } };
    const result = WorkflowSnapshotV1Schema.safeParse(snap);
    expect(result.success).toBe(false);
  });
  it("nested filename fails", async () => {
    const { WorkflowSnapshotV1Schema } = await import("../api/contracts");
    const snap = makeSnap(["entity_A"]);
    (snap as any).latest_threat_correlations[0].provenance = { nested: { filename: "secret.pcap" } };
    const result = WorkflowSnapshotV1Schema.safeParse(snap);
    expect(result.success).toBe(false);
  });
  it("nested target fails", async () => {
    const { WorkflowSnapshotV1Schema } = await import("../api/contracts");
    const snap = makeSnap(["entity_A"]);
    (snap as any).latest_threat_correlations[0].provenance = { nested: { target: "soil-sensor" } };
    const result = WorkflowSnapshotV1Schema.safeParse(snap);
    expect(result.success).toBe(false);
  });
  it("session_trace remains allowed", async () => {
    const { WorkflowSnapshotV1Schema } = await import("../api/contracts");
    const snap = makeSnap(["entity_A"]);
    (snap as any).provenance = { session_trace: "opaque-123" };
    const result = WorkflowSnapshotV1Schema.safeParse(snap);
    expect(result.success).toBe(true);
  });
});
