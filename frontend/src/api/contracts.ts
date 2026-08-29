/**
 * TypeScript contracts transcribed from the authoritative Stage-3A Pydantic
 * models (backend/app/contracts/). Field names match the backend exactly.
 * Zod schemas validate at runtime; unknown schema versions are rejected.
 */
import { z } from "zod";

// ─── ApiErrorV1 ──────────────────────────────────────────────────────────────

export const ApiErrorV1Schema = z.object({
  schema_version: z.literal("api_error_v1"),
  error_code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()).nullable().optional(),
});
export type ApiErrorV1 = z.infer<typeof ApiErrorV1Schema>;

// ─── ReplayStatusV1 ──────────────────────────────────────────────────────────

export const ReplayStateSchema = z.enum([
  "CREATED",
  "RUNNING",
  "PAUSED",
  "COMPLETED",
  "FAILED",
]);
export type ReplayState = z.infer<typeof ReplayStateSchema>;

export const PacingSpeedSchema = z.enum(["1x", "5x", "10x", "max"]);
export type PacingSpeed = z.infer<typeof PacingSpeedSchema>;

export const ReplayStatusV1Schema = z.object({
  schema_version: z.literal("replay_status_v1"),
  replay_id: z.string(),
  session_trace: z.string(),
  state: ReplayStateSchema,
  source_mode: z.string(),
  pacing: PacingSpeedSchema,
  windows_total: z.number().nullable(),
  windows_processed: z.number(),
  last_window_id: z.number().nullable(),
  sequence_number: z.number(),
  findings_emitted: z.record(z.number()),
  error: z.string().nullable(),
  provenance: z.record(z.unknown()),
});
export type ReplayStatusV1 = z.infer<typeof ReplayStatusV1Schema>;

export const ReplayCreateResponseSchema = z.object({
  replay_id: z.string(),
  status: ReplayStatusV1Schema.extend({ state: z.literal("CREATED") }),
});

export const ReplayControlResponseSchema = z.object({
  replay_id: z.string(),
  state: ReplayStateSchema,
});

export const ReplayStepResponseSchema = ReplayControlResponseSchema.extend({
  stepped: z.boolean(),
});

export const ReplayRestartResponseSchema = z.object({
  previous_replay_id: z.string(),
  new_replay_id: z.string(),
});

export const ReplaySpeedResponseSchema = z.object({
  replay_id: z.string(),
  pacing: PacingSpeedSchema,
});

// ─── DeviceStateV1 ───────────────────────────────────────────────────────────

export const DeviceStateV1Schema = z.object({
  schema_version: z.literal("device_state_v1"),
  replay_id: z.string(),
  entity_id: z.string(),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  network_observed: z.boolean(),
  behavior_observed: z.boolean(),
  behavior_supported: z.boolean(),
  network_risk: z.number().nullable(),
  behavior_risk: z.number().nullable(),
  propagated_risk: z.number().nullable(),
  systemic_risk: z.number().nullable(),
  is_attacker: z.boolean(),
  is_protected_asset: z.boolean(),
  operational_state: z.boolean().nullable(),
  compromise_state: z.boolean().nullable(),
  provenance: z.record(z.unknown()),
});
export type DeviceStateV1 = z.infer<typeof DeviceStateV1Schema>;

export const DeviceStateListV1Schema = z.object({
  schema_version: z.literal("device_state_v1"),
  replay_id: z.string(),
  devices: z.array(DeviceStateV1Schema),
});

// ─── Graph snapshots ─────────────────────────────────────────────────────────

export const DeviceRiskNodeV1Schema = z.object({
  entity_id: z.string(),
  role: z.string().nullable(),
  device_type: z.string().nullable(),
  network_observed: z.boolean(),
  behavior_observed: z.boolean(),
  behavior_supported: z.boolean(),
  network_risk: z.number().nullable(),
  behavior_risk: z.number().nullable(),
  propagated_risk: z.number().nullable(),
  systemic_risk: z.number().nullable(),
  is_attacker: z.boolean(),
  is_protected_asset: z.boolean(),
});
export type DeviceRiskNodeV1 = z.infer<typeof DeviceRiskNodeV1Schema>;

export const DeviceRiskEdgeV1Schema = z.object({
  src_entity_id: z.string(),
  dst_entity_id: z.string(),
  relationship: z.string().nullable(),
  direction: z.enum(["directed", "undirected"]),
  evidence_type: z.enum(["DOCUMENTED", "STRONGLY_INFERRED"]).nullable(),
});
export type DeviceRiskEdgeV1 = z.infer<typeof DeviceRiskEdgeV1Schema>;

export const DeviceRiskGraphSnapshotV1Schema = z.object({
  schema_version: z.literal("graph_snapshot_v1"),
  replay_id: z.string(),
  graph_kind: z.literal("device_risk_graph"),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  nodes: z.array(DeviceRiskNodeV1Schema),
  edges: z.array(DeviceRiskEdgeV1Schema),
  provenance: z.record(z.unknown()),
});
export type DeviceRiskGraphSnapshotV1 = z.infer<
  typeof DeviceRiskGraphSnapshotV1Schema
>;

export const CommunicationEdgeV1Schema = z.object({
  src_entity_id: z.string(),
  dst_entity_id: z.string(),
  packet_count_total: z.number(),
  captured_byte_total: z.number(),
  protocols_ever: z.array(z.string()),
  first_window_id: z.number().nullable(),
  last_window_id: z.number().nullable(),
  first_timestamp_utc: z.string().nullable(),
  last_timestamp_utc: z.string().nullable(),
  broadcast_ever: z.boolean(),
  multicast_ever: z.boolean(),
  packet_count_delta: z.number().optional().default(0),
  captured_byte_delta: z.number().optional().default(0),
  protocols_in_window: z.array(z.string()).optional().default([]),
});
export type CommunicationEdgeV1 = z.infer<typeof CommunicationEdgeV1Schema>;

export const CommunicationGraphSnapshotV1Schema = z.object({
  schema_version: z.literal("graph_snapshot_v1"),
  replay_id: z.string(),
  graph_kind: z.literal("communication_graph"),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  nodes: z.array(z.string()),
  edges: z.array(CommunicationEdgeV1Schema),
  provenance: z.record(z.unknown()),
});
export type CommunicationGraphSnapshotV1 = z.infer<
  typeof CommunicationGraphSnapshotV1Schema
>;

// ─── SrepSnapshotV1 ──────────────────────────────────────────────────────────

export const SrepDeviceNodeV1Schema = z.object({
  node_id: z.string(),
  role: z.string().nullable(),
  is_protected_asset: z.boolean(),
  is_attacker: z.boolean(),
  network_risk: z.number().nullable(),
  behavior_risk: z.number().nullable(),
  propagated_risk: z.number().nullable(),
  systemic_risk: z.number().nullable(),
  criticality: z.number().nullable(),
  defended_contribution: z.number().nullable(),
  compromised: z.boolean(),
});
export type SrepDeviceNodeV1 = z.infer<typeof SrepDeviceNodeV1Schema>;

export const SrepSnapshotV1Schema = z.object({
  schema_version: z.literal("srep_snapshot_v1"),
  replay_id: z.string(),
  mode: z.literal("DEVICE_ONLY"),
  mode_note: z.string().nullable(),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  steps_replayed: z.number().nullable(),
  defended_blast_radius: z.number().nullable(),
  compromised_protected_assets: z.array(z.string()),
  top_risky_protected_nodes: z.array(z.record(z.unknown())),
  device_risk_nodes: z.array(SrepDeviceNodeV1Schema),
  simulation_defined_parameters: z.record(z.unknown()),
  artifact_flags: z.array(z.string()).optional(),
  provenance: z.record(z.unknown()),
});
export type SrepSnapshotV1 = z.infer<typeof SrepSnapshotV1Schema>;

// ─── SavedReplaySnapshotV1 / meta ────────────────────────────────────────────

export const SavedSnapshotMetaV1Schema = z.object({
  snapshot_id: z.string(),
  replay_id: z.string(),
  session_trace: z.string(),
  schema_version: z.string(),
  created_at_utc: z.string().nullable(),
  state: z.string().nullable(),
  size_bytes: z.number().nullable(),
});
export type SavedSnapshotMetaV1 = z.infer<typeof SavedSnapshotMetaV1Schema>;

export const SavedReplaySnapshotV1Schema = z.object({
  schema_version: z.literal("saved_replay_snapshot_v1"),
  snapshot_id: z.string(),
  replay_id: z.string(),
  session_trace: z.string(),
  created_at_utc: z.string().nullable(),
  replay_status: z.record(z.unknown()),
  device_states: z.array(z.record(z.unknown())),
  device_risk_graph: z.record(z.unknown()).nullable(),
  communication_graph: z.record(z.unknown()).nullable(),
  srep: z.record(z.unknown()).nullable(),
  provenance: z.record(z.unknown()),
});
export type SavedReplaySnapshotV1 = z.infer<typeof SavedReplaySnapshotV1Schema>;

// ─── Health ──────────────────────────────────────────────────────────────────

export const HealthResponseSchema = z.object({
  service: z.string(),
  api_version: z.string(),
  contract_versions: z.record(z.string()),
  active_replay: z.string().nullable().optional(),
  active_replay_starting: z.boolean().default(false),
  artifact_readiness: z.record(z.boolean()).default({}),
  scientific_ready: z.boolean(),
});

// ─── Sessions ────────────────────────────────────────────────────────────────

export const SessionCapabilitySchema = z.object({
  session_id: z.string(),
  session_trace: z.string(),
  feature_store_available: z.boolean(),
  raw_available: z.boolean(),
  network_available: z.boolean(),
  behavior_available: z.boolean(),
  communication_available: z.boolean(),
  schema_compatible: z.boolean(),
  window_count: z.number().nullable().optional(),
  duration_seconds: z.number().nullable().optional(),
  supported_source_modes: z.array(z.string()),
});
export type SessionCapability = z.infer<typeof SessionCapabilitySchema>;

export const SessionListResponseSchema = z.object({
  sessions: z.array(SessionCapabilitySchema),
  default_session: z.string(),
});

// ─── Blackboard contracts (mirrors backend/app/contracts/blackboard_v1.py + blackboard/contracts.py) ──

export const BlackboardRecordTypeValues = [
  "NETWORK_FINDING_RECORD",
  "BEHAVIOR_FINDING_RECORD",
  "DEVICE_STATE_RECORD",
  "DEVICE_RISK_SNAPSHOT_RECORD",
  "DEVICE_ONLY_SREP_RECORD",
  "SYSTEM_RECORD",
] as const;
export type BlackboardRecordTypeValue = (typeof BlackboardRecordTypeValues)[number];

export const WriteOutcomeValues = [
  "COMMITTED",
  "PARTIAL_COMMIT",
  "REJECTED_STALE",
  "REJECTED_CONFLICT",
  "REJECTED_SCHEMA",
  "REJECTED_AUTHORIZATION",
  "FAILED_QUORUM",
  "FAILED_STORAGE",
] as const;
export type WriteOutcomeValue = (typeof WriteOutcomeValues)[number];

export const ReadOutcomeValues = [
  "CONSISTENT",
  "DEGRADED_CONSISTENT",
  "NOT_FOUND",
  "INSUFFICIENT_QUORUM",
  "INCONSISTENT",
  "UNAVAILABLE",
  "AUTHORIZATION_REJECTED",
] as const;
export type ReadOutcomeValue = (typeof ReadOutcomeValues)[number];

export const ReplicaHealthValues = ["HEALTHY", "UNAVAILABLE", "DIVERGED"] as const;
export type ReplicaHealthValue = (typeof ReplicaHealthValues)[number];

export const AckStatusValues = [
  "ACK_PREPARED",
  "ACK_COMMITTED",
  "ABORTED",
  "REJECT_STALE",
  "REJECT_CONFLICT",
  "REJECT_SCHEMA",
  "REJECT_INTEGRITY",
  "REJECT_AUTHORIZATION",
  "UNAVAILABLE",
  "STORAGE_ERROR",
] as const;
export type AckStatusValue = (typeof AckStatusValues)[number];

export const ReplicaStatusV1Schema = z.object({
  replica_id: z.string(),
  health: z.string(),
  available: z.boolean(),
  storage_error_count: z.number().int().min(0),
  last_error: z.string().nullable(),
  committed_record_count: z.number().int().min(0),
  pending_record_count: z.number().int().min(0),
  divergence_history: z.array(z.string()),
  head: z.record(z.unknown()).nullable().optional(),
});
export type ReplicaStatusV1 = z.infer<typeof ReplicaStatusV1Schema>;

export const RecordSummaryV1Schema = z.object({
  record_key: z.string(),
  record_type: z.string(),
  record_version: z.number().int().min(1),
  record_id: z.string(),
  content_hash: z.string(),
  author_id: z.string(),
  source_component: z.string(),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  supporting_replicas: z.array(z.string()),
});
export type RecordSummaryV1 = z.infer<typeof RecordSummaryV1Schema>;

export const BlackboardRecordV1Schema = z.object({
  schema_version: z.literal("blackboard_record_v1"),
  record_id: z.string(),
  record_key: z.string(),
  record_type: z.string(),
  record_version: z.number().int().min(1),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  author_id: z.string(),
  source_component: z.string(),
  payload: z.record(z.unknown()),
  provenance: z.record(z.unknown()),
  content_hash: z.string(),
});
export type BlackboardRecordV1 = z.infer<typeof BlackboardRecordV1Schema>;

export const BlackboardHealthV1Schema = z.object({
  schema_version: z.literal("blackboard_health_v1"),
  status: z.string(),
  replicas_available: z.number().int().min(0),
  replicas_total: z.number().int().min(0),
  divergent_replicas: z.array(z.string()),
  counters: z.record(z.number()),
});
export type BlackboardHealthV1 = z.infer<typeof BlackboardHealthV1Schema>;

export const BlackboardSnapshotV1Schema = z.object({
  schema_version: z.literal("blackboard_snapshot_v1"),
  snapshot_id: z.string(),
  generated_at_utc: z.string(),
  scope_replay_id: z.string().nullable().optional(),
  latest_by_key: z.record(RecordSummaryV1Schema),
  recent_records: z.array(RecordSummaryV1Schema),
  replica_statuses: z.array(ReplicaStatusV1Schema),
  divergent_replicas: z.array(z.string()),
  counters: z.record(z.number()),
  latencies: z.record(z.unknown()),
  recent_rejections: z.array(z.record(z.unknown())),
  unverified_rows_excluded: z.number(),
  truncated: z.boolean(),
  truncated_replicas: z.array(z.string()),
  bounds: z.record(z.unknown()),
  provenance: z.record(z.unknown()),
});
export type BlackboardSnapshotV1 = z.infer<typeof BlackboardSnapshotV1Schema>;

export const BlackboardRecordListingV1Schema = z.object({
  schema_version: z.literal("blackboard_record_listing_v1"),
  items: z.array(RecordSummaryV1Schema),
  total: z.number().int().min(0),
  limit: z.number().int().min(1),
  offset: z.number().int().min(0),
  unverified_rows_excluded: z.number(),
  responsive_replicas: z.array(z.string()),
  truncated: z.boolean(),
  truncated_replicas: z.array(z.string()),
  scanned_rows_per_replica: z.record(z.number()),
  scan_bounds: z.record(z.unknown()),
  bounds: z.record(z.unknown()),
});
export type BlackboardRecordListingV1 = z.infer<typeof BlackboardRecordListingV1Schema>;

export const BlackboardReplicasResponseSchema = z.object({
  schema_version: z.literal("blackboard_health_v1"),
  replicas: z.array(ReplicaStatusV1Schema),
  divergent_replicas: z.array(z.string()),
  note: z.string(),
});
export type BlackboardReplicasResponse = z.infer<typeof BlackboardReplicasResponseSchema>;

export const ReplicaReadObservationV1Schema = z.object({
  replica_id: z.string(),
  responded: z.boolean(),
  found: z.boolean(),
  record_version: z.number().nullable(),
  content_hash: z.string().nullable(),
  detail: z.string().nullable().optional(),
});
export type ReplicaReadObservationV1 = z.infer<typeof ReplicaReadObservationV1Schema>;

export const BlackboardReadResultV1Schema = z.object({
  schema_version: z.literal("blackboard_read_result_v1"),
  read_operation_id: z.string(),
  principal: z.string(),
  record_key: z.string(),
  requested_version: z.number().nullable(),
  outcome: z.string(),
  record: BlackboardRecordV1Schema.nullable(),
  reason: z.string().nullable().optional(),
  observations: z.array(ReplicaReadObservationV1Schema),
  divergent_replicas: z.array(z.string()),
  unavailable_replicas: z.array(z.string()),
  duration_ms: z.number(),
});
export type BlackboardReadResultV1 = z.infer<typeof BlackboardReadResultV1Schema>;

export const DevWriteResponseV1Schema = z.object({
  schema_version: z.string(),
  outcome: z.string(),
  operation_id: z.string(),
  record_id: z.string().nullable(),
  record_key: z.string().nullable(),
  record_version: z.number().nullable(),
  content_hash: z.string().nullable(),
  reason: z.string().nullable(),
  replica_sync: z.record(z.string()),
  durable_commit_ack_count: z.number(),
});
export type DevWriteResponseV1 = z.infer<typeof DevWriteResponseV1Schema>;

// ─── Orchestration contracts (Stage-6 public transport) ─────────────────────

export const ORCHESTRATION_FORBIDDEN_KEYS = [
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

const orchestrationForbiddenKeySet = new Set<string>(ORCHESTRATION_FORBIDDEN_KEYS);

export function hasForbiddenOrchestrationKey(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenOrchestrationKey);
  if (value === null || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, nested]) =>
      orchestrationForbiddenKeySet.has(key.trim().toLowerCase()) ||
      hasForbiddenOrchestrationKey(nested)
  );
}

const RuntimeSafeOrchestrationRecordSchema = z.record(z.unknown()).superRefine(
  (value, context) => {
    if (hasForbiddenOrchestrationKey(value)) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Forbidden evaluation metadata is not valid orchestration transport",
      });
    }
  }
);

export const OrchestrationOutcomeValues = [
  "DECIDED",
  "NO_QUORUM",
  "TIMED_OUT",
  "INSUFFICIENT_RESPONSES",
  "REJECTED_REQUEST",
] as const;
export const OrchestrationOutcomeSchema = z.enum(OrchestrationOutcomeValues);
export type OrchestrationOutcome = z.infer<typeof OrchestrationOutcomeSchema>;

export const VoteValueValues = ["APPROVE", "REJECT", "ABSTAIN"] as const;
export const VoteValueSchema = z.enum(VoteValueValues);
export type VoteValue = z.infer<typeof VoteValueSchema>;

export const OrchestratorHealthValues = [
  "HEALTHY",
  "DEGRADED",
  "UNAVAILABLE",
] as const;
export const OrchestratorHealthSchema = z.enum(OrchestratorHealthValues);
export type OrchestratorHealth = z.infer<typeof OrchestratorHealthSchema>;

export const OrchestratorRecentOutcomeV1Schema = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("PROPOSAL"),
    request_id: z.string(),
    route_id: z.string(),
  }).strict(),
  z.object({
    kind: z.literal("VOTE"),
    request_id: z.string(),
    proposal_digest: z.string(),
  }).strict(),
]);
export type OrchestratorRecentOutcomeV1 = z.infer<
  typeof OrchestratorRecentOutcomeV1Schema
>;

export const OrchestratorStatusV1Schema = z.object({
  schema_version: z.literal("orchestrator_status_v1"),
  orchestrator_id: z.string(),
  health: OrchestratorHealthSchema,
  available: z.boolean(),
  messages_proposed: z.number().int().min(0),
  votes_issued: z.number().int().min(0),
  authentication_failures_observed: z.number().int().min(0),
  timeouts: z.number().int().min(0),
  omissions: z.number().int().min(0),
  last_error: z.string().nullable(),
  recent_outcomes: z.array(OrchestratorRecentOutcomeV1Schema),
  recent_outcomes_limit: z.number().int().min(1),
}).strict();
export type OrchestratorStatusV1 = z.infer<typeof OrchestratorStatusV1Schema>;

export const OrchestratorListingV1Schema = z.object({
  schema_version: z.literal("orchestrator_listing_v1"),
  replicas: z.array(OrchestratorStatusV1Schema),
  note: z.string(),
}).strict();
export type OrchestratorListingV1 = z.infer<typeof OrchestratorListingV1Schema>;

export const OrchestrationCountersV1Schema = z.object({
  rounds_started: z.number().int().min(0),
  decisions_reached: z.number().int().min(0),
  no_quorum: z.number().int().min(0),
  timed_out: z.number().int().min(0),
  insufficient_responses: z.number().int().min(0),
  proposals_received: z.number().int().min(0),
  proposals_rejected: z.number().int().min(0),
  votes_received: z.number().int().min(0),
  votes_rejected: z.number().int().min(0),
  authentication_failures: z.number().int().min(0),
  duplicate_messages: z.number().int().min(0),
  conflicting_votes: z.number().int().min(0),
  orchestrator_timeouts: z.number().int().min(0),
  orchestrator_delays: z.number().int().min(0),
  orchestrator_omissions: z.number().int().min(0),
  orchestrator_disagreements: z.number().int().min(0),
}).strict();
export type OrchestrationCountersV1 = z.infer<
  typeof OrchestrationCountersV1Schema
>;

export const OrchestrationLatencySummaryV1Schema = z.union([
  z.object({ count: z.literal(0) }).strict(),
  z.object({
    count: z.number().int().min(1),
    mean_ms: z.number().min(0),
    p50_ms: z.number().min(0),
    p95_ms: z.number().min(0),
    max_ms: z.number().min(0),
  }).strict(),
]);
export type OrchestrationLatencySummaryV1 = z.infer<
  typeof OrchestrationLatencySummaryV1Schema
>;

export const OrchestrationLatenciesV1Schema = z.object({
  proposal_ms: OrchestrationLatencySummaryV1Schema,
  vote_ms: OrchestrationLatencySummaryV1Schema,
  quorum_ms: OrchestrationLatencySummaryV1Schema,
  decision_ms: OrchestrationLatencySummaryV1Schema,
}).strict();
export type OrchestrationLatenciesV1 = z.infer<
  typeof OrchestrationLatenciesV1Schema
>;

export const MessageRejectionV1Schema = z.object({
  schema_version: z.literal("orchestrator_message_rejection_v1"),
  phase: z.enum(["PROPOSAL", "VOTE", "ROUND"]),
  reason_code: z.string(),
  orchestrator_id: z.string().nullable(),
  message_id: z.string().nullable(),
  detail: z.string(),
}).strict();
export type MessageRejectionV1 = z.infer<typeof MessageRejectionV1Schema>;

export const OrchestrationInstrumentationBoundsV1Schema = z.object({
  latency_samples: z.number().int().min(1),
  recent_rejections: z.number().int().min(1),
}).strict();
export type OrchestrationInstrumentationBoundsV1 = z.infer<
  typeof OrchestrationInstrumentationBoundsV1Schema
>;

export const OrchestrationInstrumentationV1Schema = z.object({
  counters: OrchestrationCountersV1Schema,
  latencies: OrchestrationLatenciesV1Schema,
  recent_rejections: z.array(MessageRejectionV1Schema),
  bounds: OrchestrationInstrumentationBoundsV1Schema,
}).strict();
export type OrchestrationInstrumentationV1 = z.infer<
  typeof OrchestrationInstrumentationV1Schema
>;

export const OrchestrationHealthV1Schema = z.object({
  schema_version: z.literal("orchestration_health_v1"),
  status: z.enum(["ok", "degraded", "offline"]),
  orchestrators_available: z.number().int().min(0),
  orchestrators_total: z.literal(3),
  required_quorum: z.literal(2),
  event_namespace: z.literal("orchestration-ops"),
  decision_history_persistent: z.literal(false),
  instrumentation: OrchestrationInstrumentationV1Schema,
}).strict();
export type OrchestrationHealthV1 = z.infer<typeof OrchestrationHealthV1Schema>;

export const ProposalSummaryV1Schema = z.object({
  orchestrator_id: z.string(),
  message_id: z.string(),
  proposed_route_id: z.string(),
  proposal_digest: z.string(),
  message_hash: z.string(),
  authentication_verified: z.boolean(),
  policy_id: z.string(),
  policy_version: z.string(),
  rationale_code: z.string(),
  latency_ms: z.number().min(0),
}).strict();
export type ProposalSummaryV1 = z.infer<typeof ProposalSummaryV1Schema>;

export const VoteSummaryV1Schema = z.object({
  orchestrator_id: z.string(),
  message_id: z.string(),
  selected_proposal_digest: z.string(),
  vote: VoteValueSchema,
  message_hash: z.string(),
  authentication_verified: z.boolean(),
  reason_code: z.string(),
  latency_ms: z.number().min(0),
}).strict();
export type VoteSummaryV1 = z.infer<typeof VoteSummaryV1Schema>;

export const OrchestrationDecisionV1Schema = z.object({
  schema_version: z.literal("orchestration_decision_v1"),
  decision_id: z.string(),
  request_id: z.string(),
  request_version: z.number().int(),
  round_id: z.string(),
  request_digest: z.string(),
  outcome: OrchestrationOutcomeSchema,
  selected_route_id: z.string().nullable(),
  selected_proposal_digest: z.string().nullable(),
  required_quorum: z.literal(2),
  proposal_summaries: z.array(ProposalSummaryV1Schema),
  vote_summaries: z.array(VoteSummaryV1Schema),
  rejections: z.array(MessageRejectionV1Schema),
  supporting_orchestrators: z.array(z.string()),
  disagreeing_orchestrators: z.array(z.string()),
  timed_out_orchestrators: z.array(z.string()),
  delayed_orchestrators: z.array(z.string()),
  omitted_orchestrators: z.array(z.string()),
  unavailable_orchestrators: z.array(z.string()),
  quorum_formed: z.boolean(),
  quorum_latency_ms: z.number().min(0).nullable(),
  decision_latency_ms: z.number().min(0),
  reason: z.string(),
  logical_timestamp: z.string().nullable(),
  window_id: z.number().int().min(0).nullable(),
  completed_at_utc: z.string(),
  provenance: RuntimeSafeOrchestrationRecordSchema,
}).strict().superRefine((decision, context) => {
  if (decision.outcome === "DECIDED") {
    if (!decision.quorum_formed || !decision.selected_route_id) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "DECIDED requires backend quorum_formed and selected_route_id",
      });
    }
    return;
  }
  if (decision.selected_route_id !== null || decision.selected_proposal_digest !== null) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Non-decided outcomes cannot carry a selected route or proposal digest",
    });
  }
});
export type OrchestrationDecisionV1 = z.infer<
  typeof OrchestrationDecisionV1Schema
>;

export const OrchestrationDecisionListingBoundsV1Schema = z.object({
  history_limit: z.number().int().min(1),
  max_page_limit: z.number().int().min(1),
}).strict();
export type OrchestrationDecisionListingBoundsV1 = z.infer<
  typeof OrchestrationDecisionListingBoundsV1Schema
>;

export const OrchestrationDecisionListingV1Schema = z.object({
  schema_version: z.literal("orchestration_decision_listing_v1"),
  decisions: z.array(OrchestrationDecisionV1Schema),
  total_retained: z.number().int().min(0),
  limit: z.number().int().min(1),
  offset: z.number().int().min(0),
  history_complete: z.literal(false),
  bounds: OrchestrationDecisionListingBoundsV1Schema,
}).strict();
export type OrchestrationDecisionListingV1 = z.infer<
  typeof OrchestrationDecisionListingV1Schema
>;

// ─── Event registry ──────────────────────────────────────────────────────────

export const EVENT_TYPE_VALUES = [
  "REPLAY_CREATED",
  "REPLAY_STARTED",
  "REPLAY_PAUSED",
  "REPLAY_RESUMED",
  "REPLAY_STEPPED",
  "REPLAY_COMPLETED",
  "REPLAY_FAILED",
  "WINDOW_STARTED",
  "WINDOW_COMPLETED",
  "NETWORK_FINDING",
  "BEHAVIOR_FINDING",
  "GATEWAY_ACCEPTED",
  "GATEWAY_REJECTED",
  "DEVICE_STATE",
  "DEVICE_RISK_GRAPH_SNAPSHOT",
  "COMMUNICATION_GRAPH_SNAPSHOT",
  "SREP_SNAPSHOT",
  "BLACKBOARD_WRITE_PROPOSED",
  "BLACKBOARD_REPLICA_ACK",
  "BLACKBOARD_WRITE_COMMITTED",
  "BLACKBOARD_WRITE_PARTIAL",
  "BLACKBOARD_WRITE_ABORTED",
  "BLACKBOARD_WRITE_REJECTED",
  "BLACKBOARD_STALE_WRITE",
  "BLACKBOARD_CONFLICT",
  "BLACKBOARD_QUORUM_FAILED",
  "BLACKBOARD_STORAGE_FAILED",
  "BLACKBOARD_READ",
  "BLACKBOARD_READ_INCONSISTENT",
  "BLACKBOARD_REPLICA_STATUS",
  "ORCHESTRATION_REQUEST_RECEIVED",
  "ORCHESTRATOR_PROPOSAL",
  "ORCHESTRATOR_VOTE",
  "ORCHESTRATOR_TIMEOUT",
  "ORCHESTRATOR_DELAYED",
  "ORCHESTRATOR_OMISSION",
  "ORCHESTRATOR_STATUS",
  "ORCHESTRATION_QUORUM_REACHED",
  "ORCHESTRATION_NO_QUORUM",
  "ORCHESTRATION_DECISION",
  "WORKFLOW_WINDOW_STARTED",
  "AGENT_DISPATCHED",
  "AGENT_EXECUTION_STARTED",
  "AGENT_EXECUTION_COMPLETED",
  "AGENT_EXECUTION_FAILED",
  "AGENT_EXECUTION_SKIPPED",
  "THREAT_CORRELATION_PRODUCED",
  "RISK_RECOMMENDATION_PRODUCED",
  "ACCESS_RECOMMENDATION_PRODUCED",
  "ENFORCEMENT_DECISION_COMMITTED",
  "CONFIRMED_FEEDBACK_RECORDED",
  "WORKFLOW_WINDOW_COMPLETED",
  "WORKFLOW_WINDOW_FAILED",
] as const;

export type EventTypeValue = (typeof EVENT_TYPE_VALUES)[number];

export const BLACKBOARD_EVENT_TYPES: ReadonlySet<EventTypeValue> = new Set<EventTypeValue>([
  "BLACKBOARD_WRITE_PROPOSED",
  "BLACKBOARD_REPLICA_ACK",
  "BLACKBOARD_WRITE_COMMITTED",
  "BLACKBOARD_WRITE_PARTIAL",
  "BLACKBOARD_WRITE_ABORTED",
  "BLACKBOARD_WRITE_REJECTED",
  "BLACKBOARD_STALE_WRITE",
  "BLACKBOARD_CONFLICT",
  "BLACKBOARD_QUORUM_FAILED",
  "BLACKBOARD_STORAGE_FAILED",
  "BLACKBOARD_READ",
  "BLACKBOARD_READ_INCONSISTENT",
  "BLACKBOARD_REPLICA_STATUS",
]);

const EventTypeSchema = z.enum(EVENT_TYPE_VALUES);
export { EventTypeSchema as ReplayEventType };

export const EventEnvelopeV1Schema = z.object({
  schema_version: z.literal("simulation_event_v1"),
  replay_id: z.string(),
  event_id: z.string(),
  sequence_number: z.number().int().min(0),
  event_type: EventTypeSchema,
  logical_timestamp: z.string().nullable(),
  window_id: z.number().nullable(),
  source_component: z.string(),
  entity_id: z.string().nullable(),
  payload: z.record(z.unknown()),
  provenance: z.record(z.unknown()),
});
export type EventEnvelopeV1 = z.infer<typeof EventEnvelopeV1Schema>;

// Stage-6 event projections contain summaries and backend-selected facts only;
// authenticated message bodies and key material are not public transport.
export const OrchestrationRequestReceivedPayloadV1Schema = z.object({
  request_id: z.string(),
  request_version: z.number().int(),
  round_id: z.string(),
  request_digest: z.string(),
  candidate_route_ids: z.array(z.string()),
  decision_kind: z.string(),
  source_component: z.string(),
  caller_principal: z.string(),
}).strict();
export type OrchestrationRequestReceivedPayloadV1 = z.infer<
  typeof OrchestrationRequestReceivedPayloadV1Schema
>;

export const OrchestratorProposalEventPayloadV1Schema = ProposalSummaryV1Schema.extend({
  request_id: z.string(),
  round_id: z.string(),
}).strict();
export type OrchestratorProposalEventPayloadV1 = z.infer<
  typeof OrchestratorProposalEventPayloadV1Schema
>;

export const OrchestratorVoteEventPayloadV1Schema = VoteSummaryV1Schema.extend({
  request_id: z.string(),
  round_id: z.string(),
}).strict();
export type OrchestratorVoteEventPayloadV1 = z.infer<
  typeof OrchestratorVoteEventPayloadV1Schema
>;

export const OrchestratorTimeoutPayloadV1Schema = z.object({
  request_id: z.string(),
  round_id: z.string(),
  orchestrator_id: z.string(),
  phase: z.literal("ROUND"),
  budget_ms: z.number().min(0),
  reason: z.literal("NO_USABLE_RESPONSE_BEFORE_TERMINAL_ROUND"),
}).strict();
export type OrchestratorTimeoutPayloadV1 = z.infer<
  typeof OrchestratorTimeoutPayloadV1Schema
>;

export const OrchestratorDelayedPayloadV1Schema = z.object({
  request_id: z.string(),
  round_id: z.string(),
  orchestrator_id: z.string(),
  phase: z.enum(["PROPOSAL", "VOTE"]),
  reason: z.literal("ROUND_CLOSED_AFTER_QUORUM_BEFORE_RESPONSE"),
}).strict();
export type OrchestratorDelayedPayloadV1 = z.infer<
  typeof OrchestratorDelayedPayloadV1Schema
>;

export const OrchestratorOmissionPayloadV1Schema = z.object({
  request_id: z.string(),
  round_id: z.string(),
  orchestrator_id: z.string(),
  phase: z.literal("ROUND"),
  reason: z.literal("NO_MESSAGE_PRODUCED"),
}).strict();
export type OrchestratorOmissionPayloadV1 = z.infer<
  typeof OrchestratorOmissionPayloadV1Schema
>;

export const OrchestratorStatusEventPayloadV1Schema = z.object({
  request_id: z.string(),
  round_id: z.string(),
  orchestrator_id: z.string(),
  health: z.literal("UNAVAILABLE"),
  available: z.literal(false),
  reason: z.literal("OPERATIONALLY_UNAVAILABLE"),
}).strict();
export type OrchestratorStatusEventPayloadV1 = z.infer<
  typeof OrchestratorStatusEventPayloadV1Schema
>;

export const OrchestrationQuorumReachedPayloadV1Schema = z.object({
  request_id: z.string(),
  round_id: z.string(),
  proposal_digest: z.string(),
  supporting_orchestrators: z.array(z.string()),
  required_quorum: z.literal(2),
  quorum_latency_ms: z.number().min(0),
}).strict();
export type OrchestrationQuorumReachedPayloadV1 = z.infer<
  typeof OrchestrationQuorumReachedPayloadV1Schema
>;

export const OrchestrationNoQuorumPayloadV1Schema = z.object({
  request_id: z.string(),
  round_id: z.string(),
  outcome: z.enum([
    "NO_QUORUM",
    "TIMED_OUT",
    "INSUFFICIENT_RESPONSES",
    "REJECTED_REQUEST",
  ]),
  reason: z.string(),
  required_quorum: z.literal(2),
}).strict();
export type OrchestrationNoQuorumPayloadV1 = z.infer<
  typeof OrchestrationNoQuorumPayloadV1Schema
>;

export const OrchestrationEventPayloadSchemas = {
  ORCHESTRATION_REQUEST_RECEIVED: OrchestrationRequestReceivedPayloadV1Schema,
  ORCHESTRATOR_PROPOSAL: OrchestratorProposalEventPayloadV1Schema,
  ORCHESTRATOR_VOTE: OrchestratorVoteEventPayloadV1Schema,
  ORCHESTRATOR_TIMEOUT: OrchestratorTimeoutPayloadV1Schema,
  ORCHESTRATOR_DELAYED: OrchestratorDelayedPayloadV1Schema,
  ORCHESTRATOR_OMISSION: OrchestratorOmissionPayloadV1Schema,
  ORCHESTRATOR_STATUS: OrchestratorStatusEventPayloadV1Schema,
  ORCHESTRATION_QUORUM_REACHED: OrchestrationQuorumReachedPayloadV1Schema,
  ORCHESTRATION_NO_QUORUM: OrchestrationNoQuorumPayloadV1Schema,
  ORCHESTRATION_DECISION: OrchestrationDecisionV1Schema,
} as const;
export type OrchestrationEventType = keyof typeof OrchestrationEventPayloadSchemas;
export type OrchestrationEventPayload = z.infer<
  (typeof OrchestrationEventPayloadSchemas)[OrchestrationEventType]
>;

const OrchestrationEventBaseV1Schema = EventEnvelopeV1Schema.extend({
  replay_id: z.literal("orchestration-ops"),
  provenance: RuntimeSafeOrchestrationRecordSchema,
});

export const OrchestrationEventEnvelopeV1Schema = z.discriminatedUnion("event_type", [
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATION_REQUEST_RECEIVED"),
    payload: OrchestrationRequestReceivedPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATOR_PROPOSAL"),
    payload: OrchestratorProposalEventPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATOR_VOTE"),
    payload: OrchestratorVoteEventPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATOR_TIMEOUT"),
    payload: OrchestratorTimeoutPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATOR_DELAYED"),
    payload: OrchestratorDelayedPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATOR_OMISSION"),
    payload: OrchestratorOmissionPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATOR_STATUS"),
    payload: OrchestratorStatusEventPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATION_QUORUM_REACHED"),
    payload: OrchestrationQuorumReachedPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATION_NO_QUORUM"),
    payload: OrchestrationNoQuorumPayloadV1Schema,
  }).strict(),
  OrchestrationEventBaseV1Schema.extend({
    event_type: z.literal("ORCHESTRATION_DECISION"),
    payload: OrchestrationDecisionV1Schema,
  }).strict(),
]);
export type OrchestrationEventEnvelopeV1 = z.infer<
  typeof OrchestrationEventEnvelopeV1Schema
>;

// ─── Workflow contracts (Stage-8 live five-agent workflow) ─────────────────

export const AGENT_IDS = [
  "network_anomaly_detector",
  "iot_behavioral_profiler",
  "threat_intelligence_correlator",
  "risk_propagation_analyst",
  "trust_access_controller",
] as const;
export type AgentId = (typeof AGENT_IDS)[number];

export const AGENT_DISPLAY_LABELS: Record<AgentId, string> = {
  network_anomaly_detector: "Network / Anomaly Detector",
  iot_behavioral_profiler: "IoT Behavioural Profiler",
  threat_intelligence_correlator: "Threat Intelligence Correlator",
  risk_propagation_analyst: "Risk Propagation Analyst",
  trust_access_controller: "Trust & Access Controller",
};

export const ACTION_TYPES = ["ALLOW", "MONITOR", "BLOCK"] as const;
export type ActionType = (typeof ACTION_TYPES)[number];
export const ActionTypeSchema = z.enum(ACTION_TYPES);

export const MAPPING_STATUSES = ["MATCHED", "UNMAPPED", "UNSUPPORTED"] as const;
export type MappingStatus = (typeof MAPPING_STATUSES)[number];
export const MappingStatusSchema = z.enum(MAPPING_STATUSES);

export const CONTROLLER_MODES = ["PRE_LZTAF_DEVICE_EVIDENCE"] as const;
export type ControllerMode = (typeof CONTROLLER_MODES)[number];

export const WORKFLOW_FORBIDDEN_KEYS = [
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

const workflowForbiddenKeySet = new Set<string>(WORKFLOW_FORBIDDEN_KEYS.map((k) => k.toLowerCase()));

export function hasForbiddenWorkflowKey(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasForbiddenWorkflowKey);
  if (value === null || typeof value !== "object") return false;
  return Object.entries(value as Record<string, unknown>).some(
    ([key, nested]) =>
      workflowForbiddenKeySet.has(key.trim().toLowerCase()) ||
      hasForbiddenWorkflowKey(nested)
  );
}

const RuntimeSafeWorkflowRecordSchema = z.record(z.unknown()).superRefine((value, context) => {
  if (hasForbiddenWorkflowKey(value)) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Forbidden evaluation metadata is not valid workflow transport",
    });
  }
});

export const WorkflowWindowStateV1Schema = z.object({
  window_id: z.number().int().min(0),
  entity_id: z.string(),
  entity_ids: z.array(z.string()).optional(),
  status: z.string(),
  dispatch_ids: z.array(z.string()),
  execution_ids: z.array(z.string()),
}).passthrough();
export type WorkflowWindowStateV1 = z.infer<typeof WorkflowWindowStateV1Schema>;

export const AgentStatusV1Schema = z.object({
  agent_id: z.string(),
  status: z.string(),
}).passthrough();
export type AgentStatusV1 = z.infer<typeof AgentStatusV1Schema>;

export const ThreatCorrelationV1Schema = z.object({
  schema_version: z.literal("threat_correlation_v1"),
  correlation_id: z.string(),
  workflow_id: z.string(),
  entity_id: z.string(),
  window_id: z.number().int().min(0),
  logical_timestamp: z.string(),
  source_finding_ids: z.array(z.string()),
  mapping_status: MappingStatusSchema,
  threat_behavior_id: z.string().nullable().optional(),
  threat_behavior_name: z.string().nullable().optional(),
  mapping_catalog_version: z.string(),
  mapping_rule_id: z.string().nullable().optional(),
  mapping_basis: z.string().nullable().optional(),
  evidence_refs: z.array(z.string()),
  confidence: z.number().min(0).max(1).nullable().optional(),
  provenance: RuntimeSafeWorkflowRecordSchema,
}).passthrough();
export type ThreatCorrelationV1 = z.infer<typeof ThreatCorrelationV1Schema>;

export const RiskRecommendationV1Schema = z.object({
  schema_version: z.literal("risk_recommendation_v1"),
  recommendation_id: z.string(),
  workflow_id: z.string(),
  entity_id: z.string(),
  window_id: z.number().int().min(0),
  logical_timestamp: z.string(),
  network_risk: z.number().min(0).max(1).nullable().optional(),
  behavior_risk: z.number().min(0).max(1).nullable().optional(),
  behavior_supported: z.boolean(),
  direct_risk: z.number().min(0).max(1).nullable().optional(),
  propagated_risk: z.number().min(0).max(1),
  systemic_risk: z.number().min(0).max(1),
  threat_correlation_refs: z.array(z.string()),
  evidence_complete: z.boolean(),
  reason_codes: z.array(z.string()),
  recommended_escalation: z.string(),
  agent_trust_graph_supported: z.literal(false),
  agent_workflow_risk_supported: z.literal(false),
  device_risk_supported: z.literal(true),
  provenance: RuntimeSafeWorkflowRecordSchema,
  source_component: z.string().optional(),
}).passthrough();
export type RiskRecommendationV1 = z.infer<typeof RiskRecommendationV1Schema>;

export const AccessRecommendationV1Schema = z.object({
  schema_version: z.literal("access_recommendation_v1"),
  recommendation_id: z.string(),
  workflow_id: z.string(),
  entity_id: z.string(),
  window_id: z.number().int().min(0),
  logical_timestamp: z.string(),
  action: ActionTypeSchema,
  policy_id: z.string(),
  policy_version: z.string(),
  controller_mode: z.enum(CONTROLLER_MODES),
  evidence_refs: z.array(z.string()),
  evidence_complete: z.boolean(),
  behavior_supported: z.boolean(),
  reason_codes: z.array(z.string()),
  trust_vector_supported: z.literal(false),
  agent_trust_supported: z.literal(false),
  credential_controls_supported: z.literal(false),
  provenance: RuntimeSafeWorkflowRecordSchema,
  source_component: z.string().optional(),
}).passthrough();
export type AccessRecommendationV1 = z.infer<typeof AccessRecommendationV1Schema>;

export const EnforcementDecisionV1Schema = z.object({
  schema_version: z.literal("enforcement_decision_v1"),
  decision_id: z.string(),
  workflow_id: z.string(),
  replay_id: z.string(),
  window_id: z.number().int().min(0),
  logical_timestamp: z.string(),
  entity_id: z.string(),
  action: ActionTypeSchema,
  controller_recommendation_id: z.string(),
  controller_mode: z.enum(CONTROLLER_MODES),
  policy_id: z.string(),
  policy_version: z.string(),
  evidence_refs: z.array(z.string()),
  reason_codes: z.array(z.string()),
  evidence_complete: z.boolean(),
  behavior_supported: z.boolean(),
  source_agent: z.string().optional(),
  source_component: z.string().optional(),
  physical_enforcement_claimed: z.literal(false),
  counterfactual_effect_applied: z.literal(false),
  provenance: RuntimeSafeWorkflowRecordSchema,
}).passthrough();
export type EnforcementDecisionV1 = z.infer<typeof EnforcementDecisionV1Schema>;

export const ConfirmedFeedbackV1Schema = z.object({
  schema_version: z.literal("confirmed_feedback_v1"),
  feedback_id: z.string(),
  replay_id: z.string(),
  window_id: z.number().int().min(0),
  entity_id: z.string(),
  related_action_id: z.string(),
  related_finding_ids: z.array(z.string()),
  feedback_source: z.string(),
  confirmed: z.literal(true),
  verdict: z.string(),
  reason_code: z.string(),
  note: z.string().nullable().optional(),
  submitted_at: z.string(),
  provenance: RuntimeSafeWorkflowRecordSchema,
  source_component: z.string().optional(),
}).passthrough();
export type ConfirmedFeedbackV1 = z.infer<typeof ConfirmedFeedbackV1Schema>;

export const WorkflowSnapshotV1Schema = z.object({
  schema_version: z.literal("workflow_snapshot_v1"),
  replay_id: z.string(),
  workflow_mode: z.literal("FIVE_AGENT_LIVE"),
  workflow_id: z.string(),
  current_window_id: z.number().int().min(0).nullable().optional(),
  last_window_id: z.number().int().min(0).nullable().optional(),
  recent_windows: z.array(WorkflowWindowStateV1Schema),
  five_agent_statuses: z.array(AgentStatusV1Schema),
  latest_threat_correlations: z.array(ThreatCorrelationV1Schema),
  latest_risk_recommendations: z.array(RiskRecommendationV1Schema),
  latest_access_recommendations: z.array(AccessRecommendationV1Schema),
  latest_enforcement_decisions: z.array(EnforcementDecisionV1Schema),
  recent_failures: z.array(RuntimeSafeWorkflowRecordSchema),
  bounds: RuntimeSafeWorkflowRecordSchema,
  instrumentation: RuntimeSafeWorkflowRecordSchema,
  provenance: RuntimeSafeWorkflowRecordSchema,
}).passthrough();
export type WorkflowSnapshotV1 = z.infer<typeof WorkflowSnapshotV1Schema>;

export const ActionListingV1Schema = z.object({
  schema_version: z.literal("action_listing_v1"),
  replay_id: z.string(),
  actions: z.array(EnforcementDecisionV1Schema),
  total: z.number().int().min(0),
  limit: z.number().int().min(1),
  offset: z.number().int().min(0),
  history_complete: z.literal(false),
  bounds: RuntimeSafeWorkflowRecordSchema,
}).passthrough();
export type ActionListingV1 = z.infer<typeof ActionListingV1Schema>;

export const FeedbackRequestV1Schema = z.object({
  window_id: z.number().int().min(0),
  entity_id: z.string().min(1).max(128),
  related_action_id: z.string().min(1).max(128),
  related_finding_ids: z.array(z.string()).default([]),
  feedback_source: z.string().min(1).max(64),
  confirmed: z.boolean(),
  verdict: z.string().min(1).max(32),
  reason_code: z.string().min(1).max(64),
  note: z.string().max(512).nullable().optional(),
  provenance: RuntimeSafeWorkflowRecordSchema.optional(),
}).passthrough();
export type FeedbackRequestV1 = z.infer<typeof FeedbackRequestV1Schema>;

// Workflow-specific event types (subset of global EVENT_TYPE_VALUES)
export const WORKFLOW_EVENT_TYPES: ReadonlySet<EventTypeValue> = new Set<EventTypeValue>([
  "WORKFLOW_WINDOW_STARTED",
  "AGENT_DISPATCHED",
  "AGENT_EXECUTION_STARTED",
  "AGENT_EXECUTION_COMPLETED",
  "AGENT_EXECUTION_FAILED",
  "AGENT_EXECUTION_SKIPPED",
  "THREAT_CORRELATION_PRODUCED",
  "RISK_RECOMMENDATION_PRODUCED",
  "ACCESS_RECOMMENDATION_PRODUCED",
  "ENFORCEMENT_DECISION_COMMITTED",
  "CONFIRMED_FEEDBACK_RECORDED",
  "WORKFLOW_WINDOW_COMPLETED",
  "WORKFLOW_WINDOW_FAILED",
]);

export function isWorkflowEvent(envelope: EventEnvelopeV1): boolean {
  return WORKFLOW_EVENT_TYPES.has(envelope.event_type as EventTypeValue);
}

export function isEventEnvelope(raw: unknown): EventEnvelopeV1 | null {
  const r = EventEnvelopeV1Schema.safeParse(raw);
  return r.success ? r.data : null;
}

export function isBlackboardEvent(envelope: EventEnvelopeV1): boolean {
  return BLACKBOARD_EVENT_TYPES.has(envelope.event_type as EventTypeValue);
}
