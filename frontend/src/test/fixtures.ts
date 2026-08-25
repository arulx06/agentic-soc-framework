/** Shared mock fixtures for Stage-3B tests — clearly isolated, never used in
 *  production components. */

import type {
  CommunicationGraphSnapshotV1,
  DeviceRiskGraphSnapshotV1,
  DeviceStateV1,
  EventEnvelopeV1,
  EventTypeValue,
  SrepSnapshotV1,
} from "../api/contracts";

export function makeDeviceState(
  overrides: Partial<DeviceStateV1> = {}
): DeviceStateV1 {
  return {
    schema_version: "device_state_v1",
    replay_id: "test-replay",
    entity_id: "soil-sensor",
    logical_timestamp: "2025-01-15T21:25:13Z",
    window_id: 0,
    network_observed: true,
    behavior_observed: true,
    behavior_supported: true,
    network_risk: 0.5,
    behavior_risk: null,
    propagated_risk: 0,
    systemic_risk: 0.5,
    is_attacker: false,
    is_protected_asset: true,
    operational_state: true,
    compromise_state: false,
    provenance: {},
    ...overrides,
  };
}

export function makeRiskGraph(): DeviceRiskGraphSnapshotV1 {
  return {
    schema_version: "graph_snapshot_v1",
    replay_id: "test-replay",
    graph_kind: "device_risk_graph",
    logical_timestamp: "2025-01-15T21:25:13Z",
    window_id: 0,
    nodes: [
      {
        entity_id: "soil-sensor",
        role: "sensor",
        device_type: "sensor",
        network_observed: true,
        behavior_observed: true,
        behavior_supported: true,
        network_risk: 0.5,
        behavior_risk: 0.2,
        propagated_risk: 0,
        systemic_risk: 0.5,
        is_attacker: false,
        is_protected_asset: true,
      },
      {
        entity_id: "mqtt-broker",
        role: "mqtt-broker",
        device_type: "raspberry-pie",
        network_observed: false,
        behavior_observed: false,
        behavior_supported: false,
        network_risk: null,
        behavior_risk: null,
        propagated_risk: null,
        systemic_risk: null,
        is_attacker: false,
        is_protected_asset: true,
      },
    ],
    edges: [
      {
        src_entity_id: "soil-sensor",
        dst_entity_id: "mqtt-broker",
        relationship: "mqtt_publish",
        direction: "directed",
        evidence_type: "DOCUMENTED",
      },
      {
        src_entity_id: "soil-sensor",
        dst_entity_id: "ap",
        relationship: "wireless_association",
        direction: "directed",
        evidence_type: "STRONGLY_INFERRED",
      },
    ],
    provenance: {},
  };
}

export function makeCommGraph(): CommunicationGraphSnapshotV1 {
  return {
    schema_version: "graph_snapshot_v1",
    replay_id: "test-replay",
    graph_kind: "communication_graph",
    logical_timestamp: "2025-01-15T21:25:43Z",
    window_id: 5,
    nodes: ["soil-sensor", "mqtt-broker"],
    edges: [
      {
        src_entity_id: "soil-sensor",
        dst_entity_id: "mqtt-broker",
        packet_count_total: 100,
        captured_byte_total: 6000,
        protocols_ever: ["tcp"],
        first_window_id: 0,
        last_window_id: 5,
        first_timestamp_utc: "2025-01-15T21:25:13Z",
        last_timestamp_utc: "2025-01-15T21:25:43Z",
        broadcast_ever: false,
        multicast_ever: false,
        packet_count_delta: 10,
        captured_byte_delta: 600,
        protocols_in_window: ["tcp"],
      },
    ],
    provenance: {},
  };
}

export function makeSrep(overrides: Partial<SrepSnapshotV1> = {}): SrepSnapshotV1 {
  return {
    schema_version: "srep_snapshot_v1",
    replay_id: "test-replay",
    mode: "DEVICE_ONLY",
    mode_note: "No Agent Trust Graph implemented",
    logical_timestamp: "2025-01-15T21:26:45Z",
    window_id: 12,
    steps_replayed: 13,
    defended_blast_radius: 3.318,
    compromised_protected_assets: [],
    top_risky_protected_nodes: [],
    device_risk_nodes: [],
    simulation_defined_parameters: { hop_decay: 0.5 },
    artifact_flags: ["SMOKE_MODEL_ARTIFACTS"],
    provenance: {},
    ...overrides,
  };
}

export function makeEnvelope(
  eventType: EventTypeValue,
  overrides: Record<string, unknown> = {}
): EventEnvelopeV1 {
  return {
    schema_version: "simulation_event_v1",
    replay_id: "test-replay",
    event_id: `test-${Math.random().toString(36).slice(2)}`,
    sequence_number: Math.floor(Math.random() * 10_000),
    event_type: eventType,
    logical_timestamp: null,
    window_id: null,
    source_component: "test",
    entity_id: null,
    payload: {},
    provenance: { session_trace: "abc123" },
    ...overrides,
  };
}
