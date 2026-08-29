import type { WorkflowSnapshotV1 } from "../api/contracts";

/**
 * Workflow presentation helpers — frontend-only formatting, no scientific computation.
 * All risk/action/mapping values are backend-authoritative; these only format for display.
 */

export function formatRisk(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  if (Number.isNaN(value)) return "N/A";
  return value.toFixed(2);
}

export function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return "N/A";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function shortenHash(hash: string): string {
  if (!hash || hash.length <= 12) return hash;
  return `${hash.slice(0, 6)}…${hash.slice(-4)}`;
}

export function actionLabel(action: string): { label: string; tone: string } {
  switch (action) {
    case "ALLOW":
      return { label: "ALLOW", tone: "tone-allow" };
    case "MONITOR":
      return { label: "MONITOR", tone: "tone-monitor" };
    case "BLOCK":
      return { label: "BLOCK", tone: "tone-block" };
    default:
      return { label: action || "UNKNOWN", tone: "tone-unknown" };
  }
}

export function mappingStatusLabel(status: string): { label: string; tone: string } {
  switch (status) {
    case "MATCHED":
      return { label: "MATCHED", tone: "tone-matched" };
    case "UNMAPPED":
      return { label: "UNMAPPED", tone: "tone-unmapped" };
    case "UNSUPPORTED":
      return { label: "UNSUPPORTED", tone: "tone-unsupported" };
    default:
      return { label: status, tone: "tone-unknown" };
  }
}

export function agentStatusTone(status: string): string {
  switch (status) {
    case "COMPLETED":
      return "tone-committed";
    case "FAILED":
      return "tone-failed";
    case "RUNNING":
    case "STARTED":
      return "tone-monitor";
    case "PENDING":
      return "tone-unknown";
    default:
      return "tone-unknown";
  }
}

export function controllerModeLabel(mode: string): string {
  if (mode === "PRE_LZTAF_DEVICE_EVIDENCE") return "PRE_LZTAF_DEVICE_EVIDENCE";
  return mode;
}

export function behaviorSupportedLabel(supported: boolean): string {
  return supported ? "Supported" : "Behavioural evidence unsupported / unavailable";
}

export interface WorkflowEntityRow {
  entity_id: string;
  window_id?: number | null;
  network_observed?: boolean | null;
  behavior_supported?: boolean | null;
  mapping_status?: string | null;
  systemic_risk?: number | null;
  recommended_action?: string | null;
  committed_action?: string | null;
  hasThreat?: boolean;
  hasRisk?: boolean;
  hasAccess?: boolean;
  hasDecision?: boolean;
}

/**
 * Group backend entity-scoped outputs for display.
 * This does NOT compute risk or action; it only groups authoritative records by entity_id.
 */
export function groupByEntity(
  threats: Array<{ entity_id: string; mapping_status: string; window_id: number }>,
  risks: Array<{ entity_id: string; systemic_risk: number; window_id: number }>,
  access: Array<{ entity_id: string; action: string; window_id: number }>,
  decisions: Array<{ entity_id: string; action: string; window_id: number }>
): Map<string, { threat?: unknown; risk?: unknown; access?: unknown; decision?: unknown }> {
  const map = new Map<string, { threat?: unknown; risk?: unknown; access?: unknown; decision?: unknown }>();
  for (const t of threats) {
    const e = map.get(t.entity_id) || {};
    e.threat = t;
    map.set(t.entity_id, e);
  }
  for (const r of risks) {
    const e = map.get(r.entity_id) || {};
    e.risk = r;
    map.set(r.entity_id, e);
  }
  for (const a of access) {
    const e = map.get(a.entity_id) || {};
    e.access = a;
    map.set(a.entity_id, e);
  }
  for (const d of decisions) {
    const e = map.get(d.entity_id) || {};
    e.decision = d;
    map.set(d.entity_id, e);
  }
  return map;
}

/**
 * Safe rendering boundary: checks if a value contains forbidden ground-truth keys.
 * This is a defense-in-depth check; primary validation is via Zod.
 */
export const FORBIDDEN_RENDER_KEYS = new Set([
  "label",
  "label1",
  "label2",
  "label3",
  "label4",
  "label_full",
  "is_attack",
  "attack_category",
  "attack_name",
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
]);

export function containsForbiddenKeys(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(containsForbiddenKeys);
  if (value === null || typeof value !== "object") return false;
  return Object.entries(value as Record<string, unknown>).some(
    ([key, nested]) =>
      FORBIDDEN_RENDER_KEYS.has(key.trim().toLowerCase()) || containsForbiddenKeys(nested)
  );
}

/**
 * Sort events chronologically by sequence_number (backend authority).
 * Never sort by agent name, role order, or arrival time.
 */
export function sortChronologically<T extends { sequence_number: number }>(events: T[]): T[] {
  return [...events].sort((a, b) => a.sequence_number - b.sequence_number);
}

/**
 * Resolve authoritative window for a selected entity using deterministic priority:
 * latest EnforcementDecision → latest AccessRecommendation → latest RiskRecommendation
 * → latest ThreatCorrelation → matching recent window → null.
 * Presentation-only, no scientific calculation.
 */
export function resolveEntityWindow(
  snapshot: WorkflowSnapshotV1 | null,
  entityId: string | null
): number | null {
  if (!snapshot || !entityId) return null;
  const dec = [...snapshot.latest_enforcement_decisions].reverse().find((d) => d.entity_id === entityId);
  if (dec) return dec.window_id;
  const acc = [...snapshot.latest_access_recommendations].reverse().find((a) => a.entity_id === entityId);
  if (acc) return acc.window_id;
  const risk = [...snapshot.latest_risk_recommendations].reverse().find((r) => r.entity_id === entityId);
  if (risk) return risk.window_id;
  const threat = [...snapshot.latest_threat_correlations].reverse().find((t) => t.entity_id === entityId);
  if (threat) return threat.window_id;
  const w = [...snapshot.recent_windows].reverse().find((win) => win.entity_ids?.includes(entityId) || win.entity_id === entityId);
  if (w) return w.window_id;
  return null;
}
