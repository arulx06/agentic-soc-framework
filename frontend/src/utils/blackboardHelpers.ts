/**
 * Blackboard presentation helpers — frontend-only, no quorum/read/commit logic.
 * All outcome/health values are backend-authoritative strings; these only format
 * for display. Never infer COMMITTED from ack counts.
 */

export function shortenHash(hash: string): string {
  if (!hash || hash.length <= 12) return hash;
  return `${hash.slice(0, 6)}\u2026${hash.slice(-4)}`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "N/A";
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 1000) return `${ms.toFixed(1)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatTimestamp(ts: string | null | undefined): string {
  if (!ts) return "N/A";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export type WriteOutcomeLabel =
  | "COMMITTED"
  | "PARTIAL_COMMIT"
  | "FAILED_QUORUM"
  | "FAILED_STORAGE"
  | "REJECTED_STALE"
  | "REJECTED_CONFLICT"
  | "REJECTED_SCHEMA"
  | "REJECTED_AUTHORIZATION"
  | "ABORTED"
  | "UNKNOWN";

export function writeOutcomeLabel(outcome: string): { label: string; tone: string } {
  switch (outcome) {
    case "COMMITTED":
      return { label: "COMMITTED", tone: "tone-committed" };
    case "PARTIAL_COMMIT":
      return { label: "PARTIAL_COMMIT \u2014 degraded, requires reconciliation", tone: "tone-partial" };
    case "FAILED_QUORUM":
      return { label: "FAILED_QUORUM", tone: "tone-failed" };
    case "FAILED_STORAGE":
      return { label: "FAILED_STORAGE", tone: "tone-failed" };
    case "REJECTED_STALE":
      return { label: "REJECTED_STALE", tone: "tone-rejected" };
    case "REJECTED_CONFLICT":
      return { label: "REJECTED_CONFLICT", tone: "tone-conflict" };
    case "REJECTED_SCHEMA":
      return { label: "REJECTED_SCHEMA", tone: "tone-rejected" };
    case "REJECTED_AUTHORIZATION":
      return { label: "REJECTED_AUTHORIZATION", tone: "tone-rejected" };
    default:
      return { label: outcome || "UNKNOWN", tone: "tone-unknown" };
  }
}

export function replicaHealthLabel(health: string): { label: string; tone: string } {
  switch (health) {
    case "HEALTHY":
      return { label: "HEALTHY", tone: "tone-committed" };
    case "DIVERGED":
      return { label: "DIVERGED", tone: "tone-partial" };
    case "UNAVAILABLE":
      return { label: "UNAVAILABLE", tone: "tone-failed" };
    default:
      return { label: health, tone: "tone-unknown" };
  }
}

export function readOutcomeLabel(outcome: string): { label: string; tone: string; hasAuthoritativeRecord: boolean } {
  switch (outcome) {
    case "CONSISTENT":
      return { label: "CONSISTENT", tone: "tone-committed", hasAuthoritativeRecord: true };
    case "DEGRADED_CONSISTENT":
      return { label: "DEGRADED_CONSISTENT", tone: "tone-partial", hasAuthoritativeRecord: true };
    case "NOT_FOUND":
      return { label: "NOT_FOUND", tone: "tone-unknown", hasAuthoritativeRecord: false };
    case "INSUFFICIENT_QUORUM":
      return { label: "INSUFFICIENT_QUORUM", tone: "tone-failed", hasAuthoritativeRecord: false };
    case "INCONSISTENT":
      return { label: "INCONSISTENT", tone: "tone-failed", hasAuthoritativeRecord: false };
    case "UNAVAILABLE":
      return { label: "UNAVAILABLE", tone: "tone-failed", hasAuthoritativeRecord: false };
    case "AUTHORIZATION_REJECTED":
      return { label: "AUTHORIZATION_REJECTED", tone: "tone-rejected", hasAuthoritativeRecord: false };
    default:
      return { label: outcome, tone: "tone-unknown", hasAuthoritativeRecord: false };
  }
}

export function blackboardStatusTone(status: string): string {
  switch (status) {
    case "ok":
      return "tone-committed";
    case "degraded":
      return "tone-partial";
    case "offline":
      return "tone-failed";
    default:
      return "tone-unknown";
  }
}

/**
 * Group Blackboard events by operation_id for presentation only.
 * Does NOT infer outcomes — grouping is purely display.
 */
export interface OperationGroup {
  operationId: string;
  events: import("../api/contracts").EventEnvelopeV1[];
  proposed?: import("../api/contracts").EventEnvelopeV1;
  acks: import("../api/contracts").EventEnvelopeV1[];
  terminal?: import("../api/contracts").EventEnvelopeV1;
}

const TERMINAL_TYPES = new Set([
  "BLACKBOARD_WRITE_COMMITTED",
  "BLACKBOARD_WRITE_PARTIAL",
  "BLACKBOARD_WRITE_REJECTED",
  "BLACKBOARD_STALE_WRITE",
  "BLACKBOARD_CONFLICT",
  "BLACKBOARD_QUORUM_FAILED",
  "BLACKBOARD_STORAGE_FAILED",
  "BLACKBOARD_WRITE_ABORTED",
]);

export function groupBlackboardEvents(
  events: import("../api/contracts").EventEnvelopeV1[]
): OperationGroup[] {
  const map = new Map<string, OperationGroup>();
  for (const env of events) {
    const opId = (env.payload?.operation_id as string | undefined) || env.event_id;
    if (!opId || typeof opId !== "string") continue;
    // Only group events that actually carry an operation_id (PROPOSED/ACK/terminal)
    const hasOp = "operation_id" in (env.payload as Record<string, unknown>);
    if (!hasOp && !TERMINAL_TYPES.has(env.event_type)) {
      // For ACKs without terminal, still need grouping — but use operation_id from payload
      // If no operation_id at all, skip grouping (e.g. READ events)
      if (env.event_type === "BLACKBOARD_REPLICA_ACK" || env.event_type === "BLACKBOARD_WRITE_PROPOSED") {
        // Force include — payload should have it but guard
      } else {
        continue;
      }
    }
    const payloadOp = env.payload?.operation_id as string | undefined;
    const key = payloadOp || opId;
    if (!map.has(key)) {
      map.set(key, { operationId: key, events: [], acks: [] });
    }
    const g = map.get(key)!;
    g.events.push(env);
    if (env.event_type === "BLACKBOARD_WRITE_PROPOSED") g.proposed = env;
    else if (env.event_type === "BLACKBOARD_REPLICA_ACK") g.acks.push(env);
    else if (TERMINAL_TYPES.has(env.event_type)) g.terminal = env;
  }
  // Sort groups by earliest sequence_number, events within already in envelope order
  const groups = Array.from(map.values());
  groups.sort((a, b) => {
    const aSeq = a.events[0]?.sequence_number ?? 0;
    const bSeq = b.events[0]?.sequence_number ?? 0;
    return aSeq - bSeq;
  });
  for (const g of groups) {
    g.events.sort((a, b) => a.sequence_number - b.sequence_number);
    g.acks.sort((a, b) => a.sequence_number - b.sequence_number);
  }
  return groups;
}

export const BLACKBOARD_TERMINAL_EVENT_TYPES = TERMINAL_TYPES;

export function isTerminalBlackboardEvent(eventType: string): boolean {
  return TERMINAL_TYPES.has(eventType);
}
