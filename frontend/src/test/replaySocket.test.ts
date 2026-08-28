import { afterEach, describe, expect, it, vi } from "vitest";
import { ReplaySocket } from "../api/replaySocket";
import { BLACKBOARD_EVENT_TYPES, isEventEnvelope } from "../api/contracts";
import { makeEnvelope } from "./fixtures";

class FakeWebSocket {
  static OPEN = 1;
  static instance: FakeWebSocket | null = null;

  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;

  constructor(public readonly url: string) {
    FakeWebSocket.instance = this;
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  message(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  close() {
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  FakeWebSocket.instance = null;
});

describe("ReplaySocket replay namespace", () => {
  it("ignores foreign high sequences before tracking current replay sequence", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const events: number[] = [];
    const onOpen = vi.fn();
    const socket = new ReplaySocket("ws://test", "new", {
      onEvent: (event) => events.push(event.sequence_number),
      onGap: vi.fn(),
      onOpen,
    });

    socket.connect();
    const ws = FakeWebSocket.instance!;
    ws.open();
    ws.message(
      makeEnvelope("REPLAY_COMPLETED", {
        replay_id: "old",
        sequence_number: 40,
      })
    );
    ws.message(
      makeEnvelope("REPLAY_STARTED", {
        replay_id: "new",
        sequence_number: 0,
      })
    );

    expect(onOpen).toHaveBeenCalledOnce();
    expect(events).toEqual([0]);
    socket.close();
  });

  it("accepts Stage-6 transport events without classifying them as Blackboard", () => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    const onEvent = vi.fn();
    const socket = new ReplaySocket("ws://test", "orchestration-ops", {
      onEvent,
      onGap: vi.fn(),
    });
    socket.connect();
    const ws = FakeWebSocket.instance!;
    ws.open();
    const envelope = makeEnvelope("ORCHESTRATION_DECISION", {
      replay_id: "orchestration-ops",
      sequence_number: 0,
    });
    ws.message(envelope);

    expect(isEventEnvelope(envelope)?.event_type).toBe("ORCHESTRATION_DECISION");
    expect(onEvent).toHaveBeenCalledOnce();
    expect(BLACKBOARD_EVENT_TYPES.has("ORCHESTRATION_DECISION")).toBe(false);
    socket.close();
  });

  it("bounds retries and reports exhaustion exactly once", async () => {
    vi.useFakeTimers();
    let constructionAttempts = 0;
    class FailingWebSocket {
      constructor() {
        constructionAttempts += 1;
        throw new Error("connection failed");
      }
    }
    vi.stubGlobal("WebSocket", FailingWebSocket);
    const onReconnectScheduled = vi.fn();
    const onReconnectExhausted = vi.fn();
    const socket = new ReplaySocket("ws://test", "orchestration-ops", {
      onEvent: vi.fn(),
      onGap: vi.fn(),
      onReconnectScheduled,
      onReconnectExhausted,
    });

    socket.connect();
    for (const delay of [1000, 2000, 4000, 8000, 10_000, 10_000]) {
      await vi.advanceTimersByTimeAsync(delay);
    }

    expect(onReconnectScheduled.mock.calls).toEqual([
      [1, 1000],
      [2, 2000],
      [3, 4000],
      [4, 8000],
      [5, 10_000],
      [6, 10_000],
    ]);
    expect(constructionAttempts).toBe(7);
    expect(onReconnectExhausted).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
    socket.close();
  });
});
