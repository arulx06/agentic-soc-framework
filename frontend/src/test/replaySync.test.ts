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
