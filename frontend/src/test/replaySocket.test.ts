import { afterEach, describe, expect, it, vi } from "vitest";
import { ReplaySocket } from "../api/replaySocket";
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
});
