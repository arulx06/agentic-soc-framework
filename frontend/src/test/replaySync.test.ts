/** Replay-control, WebSocket-sync, gap/lag and bounded-buffer tests. */
import { describe, expect, it, vi } from "vitest";
import {
  replayReducer,
  EVENT_BUFFER_LIMIT,
  createInitialReplayState,
  type ReplayState,
} from "../state/replayReducer";
import { makeDeviceState, makeEnvelope, makeRiskGraph } from "../test/fixtures";

function makeInitialState(overrides: Partial<ReplayState> = {}): ReplayState {
  return {
    ...createInitialReplayState(),
    replayId: "r1",
    connectionState: "OPEN",
    ...overrides,
  };
}

// ─── Bounded browser buffer ──────────────────────────────────────────────────

describe("bounded event history", () => {
  it("never exceeds the configured limit", () => {
    let state = makeInitialState();
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
    // oldest dropped
    expect(state.events[0].sequence_number).toBe(100);
    expect(state.eventHistoryTruncated).toBe(true);
  });

  it("preserves latest validated snapshots when events overflow", () => {
    let state = makeInitialState({
      deviceStates: [makeDeviceState()],
    });
    for (let i = 0; i < EVENT_BUFFER_LIMIT + 10; i++) {
      state = replayReducer(state, {
        type: "EVENT",
        envelope: makeEnvelope("WINDOW_STARTED", {
          sequence_number: i,
          event_id: `e-${i}`,
        }),
      });
    }
    expect(state.deviceStates).toHaveLength(1);
  });
});

// ─── Gap / lag detection ─────────────────────────────────────────────────────

describe("gap / lag", () => {
  it("EVENT_GAP sets gapDetected flag", () => {
    const state = replayReducer(makeInitialState(), { type: "EVENT_GAP" });
    expect(state.gapDetected).toBe(true);
  });
});

// ─── Restart clears namespace ────────────────────────────────────────────────

describe("restart namespace handling", () => {
  it("REPLAY_SET resets all replay-scoped state", () => {
    let state = makeInitialState({
      deviceStates: [makeDeviceState()],
      events: [makeEnvelope("WINDOW_COMPLETED")],
      riskGraph: makeRiskGraph(),
    });
    state = replayReducer(state, { type: "REPLAY_SET", replayId: "new-id", status: null });
    expect(state.replayId).toBe("new-id");
    expect(state.deviceStates).toHaveLength(0);
    expect(state.events).toHaveLength(0);
    expect(state.riskGraph).toBeNull();
  });

  it("REPLAY_CLEARED removes everything", () => {
    let state = makeInitialState({ deviceStates: [makeDeviceState()] });
    state = replayReducer(state, { type: "REPLAY_CLEARED" });
    expect(state.replayId).toBeNull();
    expect(state.deviceStates).toHaveLength(0);
  });
});

// ─── isStarting lifecycle ───────────────────────────────────────────────────

describe("isStarting lifecycle", () => {
  it("REPLAY_SET with null status sets isStarting true (Restart)", () => {
    let state = makeInitialState();
    state = replayReducer(state, { type: "REPLAY_SET", replayId: "r2", status: null });
    expect(state.isStarting).toBe(true);
  });

  it("REPLAY_SET with CREATED does not set isStarting (Create)", () => {
    let state = makeInitialState();
    const status = {
      schema_version: "replay_status_v1" as const,
      replay_id: "r1",
      session_trace: "trace",
      state: "CREATED" as const,
      source_mode: "feature_store",
      pacing: "max" as const,
      windows_total: 13,
      windows_processed: 0,
      last_window_id: null,
      sequence_number: 0,
      findings_emitted: {},
      error: null,
      provenance: {},
    };
    state = replayReducer(state, { type: "REPLAY_SET", replayId: "r1", status });
    expect(state.isStarting).toBe(false);
  });

  it("STATUS RUNNING clears isStarting, CREATED keeps it", () => {
    let state = makeInitialState({ replayId: "r2", isStarting: true });
    const created = {
      schema_version: "replay_status_v1" as const,
      replay_id: "r2",
      session_trace: "trace",
      state: "CREATED" as const,
      source_mode: "feature_store",
      pacing: "max" as const,
      windows_total: 13,
      windows_processed: 0,
      last_window_id: null,
      sequence_number: 1,
      findings_emitted: {},
      error: null,
      provenance: {},
    };
    state = replayReducer(state, { type: "STATUS", payload: created });
    expect(state.isStarting).toBe(true);
    const running = { ...created, state: "RUNNING" as const };
    state = replayReducer(state, { type: "STATUS", payload: running });
    expect(state.isStarting).toBe(false);
  });

  it("transient ERROR does not reopen Play while startup is unresolved", () => {
    let state = makeInitialState({ isStarting: true });
    state = replayReducer(state, { type: "ERROR", message: "boom" });
    expect(state.isStarting).toBe(true);
    state = replayReducer(state, { type: "START_CANCELLED" });
    expect(state.isStarting).toBe(false);
  });

  it("terminal status cannot regress to stale RUNNING status", () => {
    const completed = {
      schema_version: "replay_status_v1" as const,
      replay_id: "r1",
      session_trace: "trace",
      state: "COMPLETED" as const,
      source_mode: "feature_store",
      pacing: "max" as const,
      windows_total: 13,
      windows_processed: 13,
      last_window_id: 12,
      sequence_number: 50,
      findings_emitted: {},
      error: null,
      provenance: {},
    };
    let state = makeInitialState({ status: completed });
    state = replayReducer(state, {
      type: "STATUS",
      payload: {
        ...completed,
        state: "RUNNING",
        windows_processed: 5,
        last_window_id: 4,
        sequence_number: 20,
      },
    });
    expect(state.status).toBe(completed);
  });
});
