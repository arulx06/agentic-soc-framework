// @ts-nocheck
import { describe, expect, it, vi, afterEach } from "vitest";
import {
  WorkflowSnapshotV1Schema,
  ActionListingV1Schema,
  EnforcementDecisionV1Schema,
  ThreatCorrelationV1Schema,
  RiskRecommendationV1Schema,
  AccessRecommendationV1Schema,
  ConfirmedFeedbackV1Schema,
  FeedbackRequestV1Schema,
  AGENT_IDS,
  WORKFLOW_FORBIDDEN_KEYS,
  hasForbiddenWorkflowKey,
} from "../api/contracts";
import { ApiClient } from "../api/client";
import { ContractValidationError } from "../api/validation";
import clientSource from "../api/client.ts?raw";
import workflowHookSource from "../hooks/useWorkflow.ts?raw";
import workflowViewSource from "../components/workflow/FiveAgentWorkflowView.tsx?raw";
import workflowHelpersSource from "../utils/workflowHelpers.ts?raw";
import agentCardsSource from "../components/workflow/AgentRoleCards.tsx?raw";
import enforcementSource from "../components/workflow/EnforcementDecisionPanel.tsx?raw";
import riskSource from "../components/workflow/RiskRecommendationPanel.tsx?raw";
import threatSource from "../components/workflow/ThreatCorrelationPanel.tsx?raw";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function makeThreat(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "threat_correlation_v1",
    correlation_id: "corr-1",
    workflow_id: "wf-1",
    entity_id: "soil-sensor",
    window_id: 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    source_finding_ids: ["finding-1"],
    mapping_status: "MATCHED",
    threat_behavior_id: "TB-NET-01",
    threat_behavior_name: "network_anomaly_confirmed",
    mapping_catalog_version: "threat_catalog_v1",
    mapping_rule_id: "rule_network_attack_high_confidence",
    mapping_basis: "predicted_class attack",
    evidence_refs: ["ev-1"],
    confidence: 0.9,
    provenance: { source_component: "agentic_workflow.threat_correlator" },
    ...overrides,
  };
}

function makeRisk(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "risk_recommendation_v1",
    recommendation_id: "risk-1",
    workflow_id: "wf-1",
    entity_id: "soil-sensor",
    window_id: 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    network_risk: 0.5,
    behavior_risk: 0.2,
    behavior_supported: true,
    direct_risk: 0.4,
    propagated_risk: 0.1,
    systemic_risk: 0.6,
    threat_correlation_refs: ["corr-1"],
    evidence_complete: true,
    reason_codes: ["TEST"],
    recommended_escalation: "MONITOR",
    agent_trust_graph_supported: false,
    agent_workflow_risk_supported: false,
    device_risk_supported: true,
    provenance: {},
    ...overrides,
  };
}

function makeAccess(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "access_recommendation_v1",
    recommendation_id: "acc-1",
    workflow_id: "wf-1",
    entity_id: "soil-sensor",
    window_id: 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    action: "ALLOW",
    policy_id: "stage8_access_policy_v1",
    policy_version: "1",
    controller_mode: "PRE_LZTAF_DEVICE_EVIDENCE",
    evidence_refs: ["ev-1"],
    evidence_complete: true,
    behavior_supported: true,
    reason_codes: ["POLICY_ALLOW"],
    trust_vector_supported: false,
    agent_trust_supported: false,
    credential_controls_supported: false,
    provenance: {},
    ...overrides,
  };
}

function makeDecision(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "enforcement_decision_v1",
    decision_id: "dec-1",
    workflow_id: "wf-1",
    replay_id: "replay-1",
    window_id: 0,
    logical_timestamp: "2026-01-01T00:00:00Z",
    entity_id: "soil-sensor",
    action: "ALLOW",
    controller_recommendation_id: "acc-1",
    controller_mode: "PRE_LZTAF_DEVICE_EVIDENCE",
    policy_id: "stage8_access_policy_v1",
    policy_version: "1",
    evidence_refs: ["ev-1"],
    reason_codes: ["COMMITTED"],
    evidence_complete: true,
    behavior_supported: true,
    source_agent: "trust_access_controller",
    source_component: "agentic_workflow.action_commit",
    physical_enforcement_claimed: false,
    counterfactual_effect_applied: false,
    provenance: {},
    ...overrides,
  };
}

function makeSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "workflow_snapshot_v1",
    replay_id: "replay-1",
    workflow_mode: "FIVE_AGENT_LIVE",
    workflow_id: "wf-1",
    current_window_id: 1,
    last_window_id: 1,
    recent_windows: [
      { window_id: 0, entity_id: "window-scope", entity_ids: ["soil-sensor"], status: "COMPLETED", dispatch_ids: ["d1"], execution_ids: ["e1"] },
      { window_id: 1, entity_id: "window-scope", entity_ids: ["soil-sensor"], status: "COMPLETED", dispatch_ids: ["d2"], execution_ids: ["e2"] },
    ],
    five_agent_statuses: AGENT_IDS.map((id) => ({ agent_id: id, status: "COMPLETED" })),
    latest_threat_correlations: [makeThreat()],
    latest_risk_recommendations: [makeRisk()],
    latest_access_recommendations: [makeAccess()],
    latest_enforcement_decisions: [makeDecision()],
    recent_failures: [],
    bounds: { recent_windows: 64, window_states: 64, window_states_current: 2 },
    instrumentation: { agent_executions: 10, threat_matched: 5 },
    provenance: { source_component: "backend.app.services.workflow_service" },
    ...overrides,
  };
}

function makeListing(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "action_listing_v1",
    replay_id: "replay-1",
    actions: [makeDecision(), makeDecision({ decision_id: "dec-2", entity_id: "entity_B", action: "BLOCK", window_id: 1 })],
    total: 2,
    limit: 20,
    offset: 0,
    history_complete: false,
    bounds: { history_limit: 64, max_page_limit: 200 },
    ...overrides,
  };
}

function makeFeedback(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "confirmed_feedback_v1",
    feedback_id: "fb-1",
    replay_id: "replay-1",
    window_id: 0,
    entity_id: "soil-sensor",
    related_action_id: "dec-1",
    related_finding_ids: [],
    feedback_source: "OPERATOR_CONFIRMED",
    confirmed: true,
    verdict: "correct",
    reason_code: "operator_review",
    note: null,
    submitted_at: "2026-01-01T00:00:00Z",
    provenance: {},
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Workflow contracts — parsing", () => {
  it("parses valid workflow_snapshot_v1 with all five statuses", () => {
    const parsed = WorkflowSnapshotV1Schema.safeParse(makeSnapshot());
    expect(parsed.success).toBe(true);
    expect(parsed.data?.five_agent_statuses).toHaveLength(5);
    expect(parsed.data?.workflow_mode).toBe("FIVE_AGENT_LIVE");
  });

  it("parses action_listing_v1 with history_complete=false and bounds", () => {
    const parsed = ActionListingV1Schema.safeParse(makeListing());
    expect(parsed.success).toBe(true);
    expect(parsed.data?.history_complete).toBe(false);
    expect(parsed.data?.bounds.history_limit).toBe(64);
    expect(parsed.data?.actions).toHaveLength(2);
  });

  it("parses action detail (EnforcementDecision) with required fields", () => {
    const parsed = EnforcementDecisionV1Schema.safeParse(makeDecision());
    expect(parsed.success).toBe(true);
    expect(parsed.data?.physical_enforcement_claimed).toBe(false);
    expect(parsed.data?.counterfactual_effect_applied).toBe(false);
  });

  it("parses threat correlation with nullable fields", () => {
    const unmapped = makeThreat({ mapping_status: "UNMAPPED", threat_behavior_id: null, threat_behavior_name: null, mapping_rule_id: null, mapping_basis: null, confidence: null });
    // Remove nulls where schema expects nullable optional
    const parsed = ThreatCorrelationV1Schema.safeParse({ ...unmapped, threat_behavior_id: null, threat_behavior_name: null, mapping_rule_id: null, mapping_basis: null });
    // For UNMAPPED, contract allows nulls
    expect(parsed.success).toBe(true);
    expect(parsed.data?.mapping_status).toBe("UNMAPPED");
  });

  it("parses risk with nullable behavior_risk when unsupported", () => {
    const risk = makeRisk({ behavior_supported: false, behavior_risk: null });
    const parsed = RiskRecommendationV1Schema.safeParse(risk);
    expect(parsed.success).toBe(true);
    expect(parsed.data?.behavior_risk).toBeNull();
    expect(parsed.data?.behavior_supported).toBe(false);
  });

  it("parses feedback request with provenance", () => {
    const req = {
      window_id: 0,
      entity_id: "soil-sensor",
      related_action_id: "dec-1",
      related_finding_ids: [],
      feedback_source: "OPERATOR_CONFIRMED",
      confirmed: true,
      verdict: "correct",
      reason_code: "operator_review",
      provenance: {},
    };
    expect(FeedbackRequestV1Schema.safeParse(req).success).toBe(true);
  });

  it("parses feedback response (ConfirmedFeedbackV1)", () => {
    const parsed = ConfirmedFeedbackV1Schema.safeParse(makeFeedback());
    expect(parsed.success).toBe(true);
    expect(parsed.data?.confirmed).toBe(true);
    expect(parsed.data?.feedback_source).toBe("OPERATOR_CONFIRMED");
  });

  it("rejects malformed workflow snapshot (wrong schema_version)", () => {
    const bad = { ...makeSnapshot(), schema_version: "workflow_snapshot_v2" };
    expect(WorkflowSnapshotV1Schema.safeParse(bad).success).toBe(false);
  });

  it("rejects action listing when history_complete is true (must be false)", () => {
    const bad = { ...makeListing(), history_complete: true };
    expect(ActionListingV1Schema.safeParse(bad).success).toBe(false);
  });

  it("rejects decision with physical_enforcement_claimed=true", () => {
    const bad = makeDecision({ physical_enforcement_claimed: true });
    expect(EnforcementDecisionV1Schema.safeParse(bad).success).toBe(false);
  });

  it("rejects feedback when confirmed is false", () => {
    const bad = makeFeedback({ confirmed: false });
    expect(ConfirmedFeedbackV1Schema.safeParse(bad).success).toBe(false);
  });

  it("rejects workflow snapshot with forbidden ground-truth key", () => {
    const bad = makeSnapshot({ provenance: { scenario_id: "secret" } });
    expect(WorkflowSnapshotV1Schema.safeParse(bad).success).toBe(false);
  });

  it("hasForbiddenWorkflowKey detects all expected keys", () => {
    for (const key of WORKFLOW_FORBIDDEN_KEYS) {
      expect(hasForbiddenWorkflowKey({ [key]: "value" })).toBe(true);
      expect(hasForbiddenWorkflowKey({ nested: { [key]: "value" } })).toBe(true);
    }
    expect(hasForbiddenWorkflowKey({ attack_probability: 0.9 })).toBe(false);
    expect(hasForbiddenWorkflowKey({ session_trace: "opaque" })).toBe(false);
  });
});

describe("Workflow action enums", () => {
  it.each(["ALLOW", "MONITOR", "BLOCK"] as const)("accepts action %s", (action) => {
    expect(EnforcementDecisionV1Schema.safeParse(makeDecision({ action })).success).toBe(true);
    expect(AccessRecommendationV1Schema.safeParse(makeAccess({ action })).success).toBe(true);
  });
  it("rejects unknown action", () => {
    expect(EnforcementDecisionV1Schema.safeParse(makeDecision({ action: "DENY" })).success).toBe(false);
  });
  it("requires PRE_LZTAF_DEVICE_EVIDENCE", () => {
    expect(EnforcementDecisionV1Schema.safeParse(makeDecision({ controller_mode: "PRE_LZTAF_DEVICE_EVIDENCE" })).success).toBe(true);
    expect(EnforcementDecisionV1Schema.safeParse(makeDecision({ controller_mode: "LZTAF" })).success).toBe(false);
  });
});

describe("Workflow API client", () => {
  it("uses exact workflow GET path", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(makeSnapshot()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");
    await client.getWorkflowSnapshot("replay-1");
    const [url] = (fetchMock.mock.calls as unknown as Array<[string]>)[0];
    expect(url).toBe("http://backend/api/v1/replays/replay-1/workflow");
    const [, init] = (fetchMock.mock.calls as unknown as Array<[string, RequestInit]>)[0];
    expect(init.method).toBe("GET");
  });

  it("uses exact action list/detail paths and encodes", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(makeListing()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");
    await client.listActions("replay/a ?#", { entity_id: "entity/a", action: "BLOCK", limit: 10, offset: 20 });
    const [url] = (fetchMock.mock.calls as unknown as Array<[string]>)[0];
    expect(url).toContain("/replays/replay%2Fa%20%3F%23/actions");
    expect(url).toContain("entity_id=entity%2Fa");
    expect(url).toContain("action=BLOCK");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=20");
  });

  it("encodes decision_id in action detail", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(makeDecision()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");
    await client.getAction("replay-1", "dec/a ?#");
    const [url] = (fetchMock.mock.calls as unknown as Array<[string]>)[0];
    expect(url).toBe("http://backend/api/v1/replays/replay-1/actions/dec%2Fa%20%3F%23");
  });

  it("serializes pagination limit/offset", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(makeListing({ limit: 5, offset: 10 })));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");
    await client.listActions("replay-1", { limit: 5, offset: 10 });
    const [url] = (fetchMock.mock.calls as unknown as Array<[string]>)[0];
    expect(url).toContain("limit=5");
    expect(url).toContain("offset=10");
  });

  it("submits feedback POST with correct header and body", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(makeFeedback()));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");
    await client.submitFeedback("replay-1", {
      window_id: 0,
      entity_id: "soil-sensor",
      related_action_id: "dec-1",
      feedback_source: "OPERATOR_CONFIRMED",
      confirmed: true,
      verdict: "correct",
      reason_code: "operator_review",
      provenance: {},
    }, "operator-a");
    const [url, init] = (fetchMock.mock.calls as unknown as Array<[string, RequestInit]>)[0];
    expect(url).toBe("http://backend/api/v1/replays/replay-1/workflow/feedback");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["X-Feedback-Principal"]).toBe("operator-a");
    const body = JSON.parse(init.body as string);
    expect(body.confirmed).toBe(true);
    expect(body.feedback_source).toBe("OPERATOR_CONFIRMED");
    expect(body.verdict).toBe("correct");
  });

  it("rejects malformed workflow response", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ...makeSnapshot(), schema_version: "bad" }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("http://backend/api/v1");
    await expect(client.getWorkflowSnapshot("replay-1")).rejects.toBeInstanceOf(ContractValidationError);
  });

  it("uses feedback-principal convention (X-Feedback-Principal)", () => {
    expect(clientSource).toContain("X-Feedback-Principal");
    expect(clientSource).not.toContain("Authorization");
    expect(clientSource).not.toMatch(/X-Auth|Bearer/);
  });
});

describe("Workflow source boundaries (no browser calculations)", () => {
  it("does not calculate threat mapping, risk, action, quorum, trust, SREP", () => {
    const workflowSource = [workflowViewSource, workflowHelpersSource, agentCardsSource, enforcementSource, riskSource, threatSource, workflowHookSource].join("\n");
    // No risk recomputation
    expect(workflowSource).not.toMatch(/\b(risk|systemic|propagated)\s*=\s*.*\b(network|behavior)\b.*\+/i);
    // No action threshold logic
    expect(workflowSource).not.toMatch(/0\.4|0\.7/);
    expect(workflowSource).not.toMatch(/if\s*\(\s*systemic_risk\s*>=/i);
    // No quorum calculation
    expect(workflowSource).not.toMatch(/quorum_formed\s*=|supporting_orchestrators.*length/);
    // No trust calculation
    expect(workflowSource).not.toMatch(/trust\s*=\s*|trust_score/i);
    // No SREP calculation — frontend only displays DEVICE_ONLY (mentioning not to claim DUAL_GRAPH is allowed)
    expect(workflowSource).not.toMatch(/DUAL_GRAPH.*(?:enabled|active|true)/i);
    expect(workflowHelpersSource).not.toMatch(/calculate|recompute|derive.*risk/i);
  });

  it("does not hardcode ground-truth labels", () => {
    const src = [workflowViewSource, threatSource].join("\n");
    // Check that src does not assign attack families (e.g., predicted_class === "DDoS") — mentioning as disclaimer is allowed
    expect(src).not.toMatch(/predicted_class\s*===\s*["']DDoS["']/i);
    expect(src).not.toMatch(/attack_category\s*:\s*["']DDoS["']/i);
    expect(src).not.toContain("DATASENSE_GROUND_TRUTH");
  });
});
