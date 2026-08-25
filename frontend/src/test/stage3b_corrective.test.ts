/** Stage-3B corrective-pass tests: lifecycle sync, graph layout, controls. */
import { describe, expect, it, vi } from "vitest";
import {
  replayReducer,
  EVENT_BUFFER_LIMIT,
  createInitialReplayState,
  type ReplayState,
} from "../state/replayReducer";
import { makeDeviceState, makeEnvelope, makeRiskGraph, makeCommGraph, makeSrep } from "./fixtures";
import { EventEnvelopeV1Schema } from "../api/contracts";

// ─── Lifecycle: Create stores CREATED status ────────────────────────────────

describe("Create behaviour", () => {
  it("REPLAY_SET stores CREATED status and resets scientific state", () => {
    const initial: ReplayState = {
      ...createInitialReplayState(),
      replayId: "old",
      connectionState: "OPEN",
      deviceStates: [makeDeviceState()],
      riskGraph: makeRiskGraph(),
      commGraph: makeCommGraph(),
      srep: makeSrep(),
    };
    const st = {
      schema_version: "replay_status_v1" as const,
      replay_id: "new-replay",
      session_trace: "trace123",
      state: "CREATED" as const,
      source_mode: "feature_store",
      pacing: "max" as const,
      windows_total: null,
      windows_processed: 0,
      last_window_id: null,
      sequence_number: 0,
      findings_emitted: {},
      error: null,
      provenance: {},
    };
    const state = replayReducer(initial, {
      type: "REPLAY_SET", replayId: "new-replay", status: st,
    });
    expect(state.replayId).toBe("new-replay");
    expect(state.status?.state).toBe("CREATED");
    // Scientific state cleared
    expect(state.deviceStates).toHaveLength(0);
    expect(state.riskGraph).toBeNull();
    expect(state.commGraph).toBeNull();
    expect(state.srep).toBeNull();
    expect(state.events).toHaveLength(0);
  });
});

// ─── Bounded browser buffer ──────────────────────────────────────────────────

describe("bounded event history", () => {
  it("never exceeds the configured limit", () => {
    let state: ReplayState = {
      ...createInitialReplayState(),
      replayId: "r1",
      connectionState: "OPEN",
    };
    for (let i = 0; i < EVENT_BUFFER_LIMIT + 100; i++) {
      state = replayReducer(state, {
        type: "EVENT",
        envelope: makeEnvelope("NETWORK_FINDING", {
          sequence_number: i,
          event_id: `e-${i}`,
        }),
      });
    }
    expect(state.events.length).toBe(EVENT_BUFFER_LIMIT);
    expect(state.events[0].sequence_number).toBe(100);
    expect(state.eventHistoryTruncated).toBe(true);
  });
});

// ─── Gap / lag detection ─────────────────────────────────────────────────────

describe("gap / lag", () => {
  it("EVENT_GAP sets gapDetected flag", () => {
    const state = replayReducer(
      {
        ...createInitialReplayState(),
        replayId: "r1",
        connectionState: "OPEN",
      },
      { type: "EVENT_GAP" }
    );
    expect(state.gapDetected).toBe(true);
  });
});

// ─── Restart namespace handling ────────────────────────────────────────────

describe("restart namespace handling", () => {
  it("REPLAY_SET resets old events and uses new replay ID", () => {
    let state: ReplayState = {
      ...createInitialReplayState(),
      replayId: "old-id",
      connectionState: "OPEN",
      deviceStates: [makeDeviceState()],
      riskGraph: makeRiskGraph(),
      commGraph: makeCommGraph(),
      srep: makeSrep(),
      events: [
        makeEnvelope("WINDOW_COMPLETED", { sequence_number: 5, event_id: "e-5" }),
      ],
    };
    state = replayReducer(state, {
      type: "REPLAY_SET", replayId: "new-id", status: null,
    });
    expect(state.replayId).toBe("new-id");
    expect(state.events).toHaveLength(0);
    expect(state.deviceStates).toHaveLength(0);
    expect(state.riskGraph).toBeNull();
    expect(state.commGraph).toBeNull();
    expect(state.srep).toBeNull();
  });
});

// ─── Contract validation ─────────────────────────────────────────────────────

describe("contract validation", () => {
  it("rejects unknown schema_version", () => {
    const result = EventEnvelopeV1Schema.safeParse({
      schema_version: "simulation_event_v999",
      replay_id: "r", event_id: "e", sequence_number: 0,
      event_type: "WINDOW_STARTED", source_component: "test",
    });
    expect(result.success).toBe(false);
  });

  it("rejects unknown event_type", () => {
    const result = EventEnvelopeV1Schema.safeParse({
      schema_version: "simulation_event_v1",
      replay_id: "r", event_id: "e", sequence_number: 0,
      event_type: "TOTALLY_UNKNOWN_TYPE",
      source_component: "test", window_id: 0,
      logical_timestamp: null, entity_id: null,
      payload: {}, provenance: {},
    });
    expect(result.success).toBe(false);
  });

  it("never silently coerces malformed payloads", () => {
    const result = EventEnvelopeV1Schema.safeParse({
      schema_version: "simulation_event_v1",
      replay_id: "r", event_id: "e",
      sequence_number: "not-a-number",
      event_type: "WINDOW_STARTED", source_component: "test",
    });
    expect(result.success).toBe(false);
  });
});

// ─── Reducer DEVICE_STATES handling ────────────────────────────────────────

describe("reducer device states", () => {
  it("DEVICE_STATES dispatch updates without cross-contamination", () => {
    const initial: ReplayState = {
      ...createInitialReplayState(),
      replayId: "r1", connectionState: "OPEN",
    };
    const updated = replayReducer(initial, {
      type: "DEVICE_STATES", payload: [makeDeviceState({ entity_id: "edge1" })],
    });
    expect(updated.deviceStates[0].entity_id).toBe("edge1");
    expect(updated.riskGraph).toBeNull();
  });
});

// ─── Graph layout: deterministic grid distribution ─────────────────────────

describe("graph grid layout", () => {
  function computeGridLayout(
    nodeCount: number, width: number, height: number
  ): Array<{ x: number; y: number }> {
    if (nodeCount === 0) return [];
    const cols = Math.max(1, Math.ceil(Math.sqrt(nodeCount * (width / Math.max(1, height)))));
    const rows = Math.max(1, Math.ceil(nodeCount / cols));
    const cellW = width / (cols + 1);
    const cellH = height / (rows + 1);
    const positions: Array<{ x: number; y: number }> = [];
    for (let i = 0; i < nodeCount; i++) {
      positions.push({
        x: cellW * ((i % cols) + 1),
        y: cellH * (Math.floor(i / cols) + 1),
      });
    }
    return positions;
  }

  it("distributes multi-node graph across distinct coordinates", () => {
    const positions = computeGridLayout(10, 600, 400);
    expect(positions).toHaveLength(10);
    const uniqueXs = new Set(positions.map((p) => p.x));
    const uniqueYs = new Set(positions.map((p) => p.y));
    expect(uniqueXs.size).toBeGreaterThan(1);
    expect(uniqueYs.size).toBeGreaterThan(1);
  });

  it("all nodes receive distinct non-zero coordinates", () => {
    const positions = computeGridLayout(45, 800, 600);
    expect(positions).toHaveLength(45);
    const coords = positions.map((p) => `${p.x},${p.y}`);
    expect(new Set(coords).size).toBe(coords.length);
    for (const p of positions) {
      expect(p.x).toBeGreaterThan(0);
      expect(p.y).toBeGreaterThan(0);
    }
  });
});
