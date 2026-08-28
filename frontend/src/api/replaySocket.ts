/**
 * ReplaySocket: manages one WebSocket connection per replay.
 * Validates the shared backend event-type registry and schema_version; enforces
 * strictly increasing sequence numbers; handles gap notices from the
 * server; reconnects with bounded exponential backoff while non-terminal.
 */

import { isEventEnvelope } from "./contracts";
import type { EventEnvelopeV1 } from "./contracts";

export type SocketState =
  | "IDLE"
  | "CONNECTING"
  | "OPEN"
  | "CLOSED"
  | "RECONNECTING"
  | "TERMINAL";

export interface ReplaySocketCallbacks {
  onEvent: (env: EventEnvelopeV1) => void;
  onGap: () => void;
  onOpen?: () => void;
  onClose?: (code: number) => void;
  onError?: (err: string) => void;
  onReconnectScheduled?: (attempt: number, delayMs: number) => void;
  onReconnectExhausted?: () => void;
}

const MAX_RECONNECT_ATTEMPTS = 6;

export class ReplaySocket {
  private ws: WebSocket | null = null;
  private lastSequence = -1;
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private closedByUser = false;
  private terminalSeen = false;

  constructor(
    private wsBaseUrl: string,
    private replayId: string,
    private callbacks: ReplaySocketCallbacks
  ) {}

  connect(): void {
    if (this.ws || this.closedByUser || this.terminalSeen) return;
    const url = `${this.wsBaseUrl}/replays/${this.replayId}/events`;
    try {
      this.ws = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.callbacks.onOpen?.();
    };

    this.ws.onmessage = (event) => {
      let raw: unknown;
      if (typeof event.data !== "string") {
        this.callbacks.onError?.("Unsupported WebSocket message type");
        return;
      }
      try {
        raw = JSON.parse(event.data);
      } catch {
        this.callbacks.onError?.("Malformed WebSocket JSON message");
        return;
      }
      // Gap notice from server
      if (
        typeof raw === "object" &&
        raw !== null &&
        "gap_notice" in raw &&
        Reflect.get(raw, "gap_notice") === true
      ) {
        this.callbacks.onGap();
        return;
      }
      const env = isEventEnvelope(raw);
      if (!env) {
        this.callbacks.onError?.("Malformed or unknown event envelope");
        return;
      }
      if (env.replay_id !== this.replayId) {
        return;
      }

      if (env.sequence_number <= this.lastSequence) {
        return; // duplicate or backward — drop
      }
      this.lastSequence = env.sequence_number;

      if (
        env.event_type === "REPLAY_COMPLETED" ||
        env.event_type === "REPLAY_FAILED"
      ) {
        this.terminalSeen = true;
      }
      this.callbacks.onEvent(env);
    };

    this.ws.onerror = () => {
      this.callbacks.onError?.("WebSocket error");
    };

    this.ws.onclose = (e) => {
      this.ws = null;
      this.callbacks.onClose?.(e.code);
      if (!this.closedByUser && !this.terminalSeen) {
        this.scheduleReconnect();
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.closedByUser || this.terminalSeen) return;
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.callbacks.onReconnectExhausted?.();
      return;
    }
    this.reconnectAttempts++;
    const delay = Math.min(1000 * 2 ** (this.reconnectAttempts - 1), 10_000);
    this.callbacks.onReconnectScheduled?.(this.reconnectAttempts, delay);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closedByUser && !this.terminalSeen) {
        this.connect();
      }
    }, delay);
  }

  close(): void {
    this.closedByUser = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
