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

// ─── Event envelope (17-value enum) ─────────────────────────────────────────

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
] as const;

export type EventTypeValue = (typeof EVENT_TYPE_VALUES)[number];

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

export function isEventEnvelope(raw: unknown): EventEnvelopeV1 | null {
  const r = EventEnvelopeV1Schema.safeParse(raw);
  return r.success ? r.data : null;
}
