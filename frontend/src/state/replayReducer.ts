/** Browser-owned presentation state; all scientific values remain backend-produced. */
import type {
  CommunicationGraphSnapshotV1,
  DeviceRiskGraphSnapshotV1,
  DeviceStateV1,
  EventEnvelopeV1,
  ReplayStatusV1,
  SrepSnapshotV1,
} from "../api/contracts";

export const EVENT_BUFFER_LIMIT = 1500;

export interface ReplayState {
  replayId: string | null;
  connectionState: string;
  status: ReplayStatusV1 | null;
  deviceStates: DeviceStateV1[];
  riskGraph: DeviceRiskGraphSnapshotV1 | null;
  commGraph: CommunicationGraphSnapshotV1 | null;
  srep: SrepSnapshotV1 | null;
  events: EventEnvelopeV1[];
  eventHistoryTruncated: boolean;
  gapDetected: boolean;
  scientificUnavailable: boolean;
  error: string | null;
  isStarting: boolean;
}

export type ReplayAction =
  | { type: "REPLAY_SET"; replayId: string; status: ReplayStatusV1 | null }
  | { type: "REPLAY_CLEARED" }
  | { type: "CONNECTION"; state: string }
  | { type: "START_REQUESTED" }
  | { type: "START_CANCELLED" }
  | { type: "STATUS"; payload: ReplayStatusV1 }
  | { type: "DEVICE_STATES"; payload: DeviceStateV1[] }
  | { type: "UPSERT_DEVICE_STATE"; payload: DeviceStateV1 }
  | { type: "RISK_GRAPH"; payload: DeviceRiskGraphSnapshotV1 }
  | { type: "COMM_GRAPH"; payload: CommunicationGraphSnapshotV1 }
  | { type: "SREP"; payload: SrepSnapshotV1 }
  | { type: "EVENT"; envelope: EventEnvelopeV1 }
  | { type: "EVENT_GAP" }
  | { type: "SCIENTIFIC_UNAVAILABLE" }
  | { type: "SCIENTIFIC_AVAILABLE" }
  | { type: "ERROR"; message: string }
  | { type: "CLEAR_ERROR" };

export function createInitialReplayState(): ReplayState {
  return {
    replayId: null,
    connectionState: "IDLE",
    status: null,
    deviceStates: [],
    riskGraph: null,
    commGraph: null,
    srep: null,
    events: [],
    eventHistoryTruncated: false,
    gapDetected: false,
    scientificUnavailable: false,
    error: null,
    isStarting: false,
  };
}

export function hasScientificState(state: ReplayState): boolean {
  return state.status !== null && state.status.windows_processed > 0;
}

export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  switch (action.type) {
    case "REPLAY_SET":
      return {
        ...createInitialReplayState(),
        replayId: action.replayId,
        connectionState: state.connectionState,
        status: action.status,
        isStarting: action.status === null,
      };
    case "REPLAY_CLEARED":
      return { ...createInitialReplayState(), connectionState: state.connectionState };
    case "CONNECTION":
      return { ...state, connectionState: action.state };
    case "START_REQUESTED":
      return { ...state, isStarting: true };
    case "START_CANCELLED":
      return { ...state, isStarting: false };
    case "STATUS": {
      if (action.payload.replay_id !== state.replayId) return state;
      if (
        state.status?.replay_id === action.payload.replay_id &&
        action.payload.sequence_number < state.status.sequence_number
      ) {
        return state;
      }
      if (
        (state.status?.state === "COMPLETED" || state.status?.state === "FAILED") &&
        action.payload.state !== "COMPLETED" &&
        action.payload.state !== "FAILED"
      ) {
        return state;
      }
      const st = action.payload.state;
      const shouldClearStarting =
        st === "RUNNING" || st === "PAUSED" || st === "COMPLETED" || st === "FAILED";
      return {
        ...state,
        status: action.payload,
        isStarting: shouldClearStarting ? false : state.isStarting,
      };
    }
    case "DEVICE_STATES":
      return {
        ...state,
        deviceStates: action.payload,
        scientificUnavailable: false,
      };
    case "UPSERT_DEVICE_STATE": {
      const existing = state.deviceStates.some(
        (device) => device.entity_id === action.payload.entity_id
      );
      return {
        ...state,
        deviceStates: existing
          ? state.deviceStates.map((device) =>
              device.entity_id === action.payload.entity_id ? action.payload : device
            )
          : [...state.deviceStates, action.payload],
        scientificUnavailable: false,
      };
    }
    case "RISK_GRAPH":
      return { ...state, riskGraph: action.payload, scientificUnavailable: false };
    case "COMM_GRAPH":
      return { ...state, commGraph: action.payload, scientificUnavailable: false };
    case "SREP":
      return { ...state, srep: action.payload, scientificUnavailable: false };
    case "EVENT": {
      if (state.events.some((event) => event.event_id === action.envelope.event_id)) {
        return state;
      }
      const events = [...state.events, action.envelope];
      const truncated = events.length > EVENT_BUFFER_LIMIT;
      if (truncated) events.splice(0, events.length - EVENT_BUFFER_LIMIT);
      return {
        ...state,
        events,
        eventHistoryTruncated: truncated || state.eventHistoryTruncated,
      };
    }
    case "EVENT_GAP":
      return { ...state, gapDetected: true };
    case "SCIENTIFIC_UNAVAILABLE":
      return { ...state, scientificUnavailable: true };
    case "SCIENTIFIC_AVAILABLE":
      return { ...state, scientificUnavailable: false };
    case "ERROR":
      return { ...state, error: action.message };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    default:
      return state;
  }
}
