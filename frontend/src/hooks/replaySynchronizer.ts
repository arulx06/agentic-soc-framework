import type { z } from "zod";
import type { ApiClient } from "../api/client";
import {
  CommunicationGraphSnapshotV1Schema,
  DeviceRiskGraphSnapshotV1Schema,
  DeviceStateV1Schema,
  SrepSnapshotV1Schema,
  type EventEnvelopeV1,
  type ReplayStatusV1,
} from "../api/contracts";
import { BackendConflictError } from "../api/validation";
import type { ReplayAction, ReplayState } from "../state/replayReducer";

export type ReplayLifecycleClient = Pick<
  ApiClient,
  | "createReplay"
  | "getStatus"
  | "play"
  | "pause"
  | "resume"
  | "step"
  | "restart"
  | "setSpeed"
  | "getDeviceStates"
  | "getDeviceRiskGraph"
  | "getCommunicationGraph"
  | "getSrep"
>;

export interface ReplayScheduler {
  setTimeout(callback: () => void, delay: number): number;
  clearTimeout(timer: number): void;
}

const browserScheduler: ReplayScheduler = {
  setTimeout: (callback, delay) => window.setTimeout(callback, delay),
  clearTimeout: (timer) => window.clearTimeout(timer),
};

export class ReplaySynchronizer {
  private pendingTimer: number | null = null;
  private windowRefresh: Promise<void> | null = null;
  private trailingWindowRefresh = false;

  constructor(
    private readonly client: ReplayLifecycleClient,
    private readonly dispatch: (action: ReplayAction) => void,
    private readonly getState: () => ReplayState,
    private readonly scheduler: ReplayScheduler = browserScheduler
  ) {}

  async createReplay(sessionId: string, sourceMode: string, pacing: string) {
    try {
      const response = await this.client.createReplay(sessionId, sourceMode, pacing);
      this.dispatch({
        type: "REPLAY_SET",
        replayId: response.replay_id,
        status: response.status,
      });
    } catch (error) {
      this.reportError(error);
    }
  }

  async control(
    action: "play" | "pause" | "resume" | "step",
    replayId: string
  ) {
    this.dispatch({ type: "CLEAR_ERROR" });
    try {
      await this.client[action](replayId);
      await this.refreshStatus(replayId);
    } catch (error) {
      // A transition may race terminal completion. Refresh first so controls
      // converge to authoritative state, then retain the genuine conflict.
      const status = await this.refreshStatus(replayId, false);
      if (status && status.windows_processed > 0) {
        await this.refreshScientificState(replayId);
      }
      this.reportError(error);
    }
  }

  async restart(
    replayId: string,
    options?: { sessionId?: string; sourceMode?: string; pacing?: string }
  ) {
    this.dispatch({ type: "CLEAR_ERROR" });
    try {
      const response = await this.client.restart(replayId, options);
      this.cancelPendingRefresh();
      this.dispatch({
        type: "REPLAY_SET",
        replayId: response.new_replay_id,
        status: null,
      });
      // The replay-id change opens the new socket and performs status-first
      // hydration. No scientific request is made until readiness is known.
    } catch (error) {
      await this.refreshStatus(replayId, false);
      this.reportError(error);
    }
  }

  async setSpeed(replayId: string, pacing: string) {
    this.dispatch({ type: "CLEAR_ERROR" });
    try {
      await this.client.setSpeed(replayId, pacing);
      await this.refreshStatus(replayId);
    } catch (error) {
      await this.refreshStatus(replayId, false);
      this.reportError(error);
    }
  }

  async refreshStatus(
    replayId: string,
    reportFailure = true
  ): Promise<ReplayStatusV1 | null> {
    try {
      const status = await this.client.getStatus(replayId);
      if (this.getState().replayId !== replayId) return null;
      this.dispatch({ type: "STATUS", payload: status });
      if (status.state === "FAILED" && status.error) {
        this.dispatch({ type: "ERROR", message: status.error });
      }
      return status;
    } catch (error) {
      if (reportFailure) this.reportError(error);
      return null;
    }
  }

  async refreshScientificState(replayId: string): Promise<boolean> {
    try {
      const [devices, riskGraph, communicationGraph, srep] = await Promise.all([
        this.client.getDeviceStates(replayId),
        this.client.getDeviceRiskGraph(replayId),
        this.client.getCommunicationGraph(replayId),
        this.client.getSrep(replayId),
      ]);
      if (this.getState().replayId !== replayId) return false;
      this.dispatch({ type: "DEVICE_STATES", payload: devices.devices });
      this.dispatch({ type: "RISK_GRAPH", payload: riskGraph });
      this.dispatch({ type: "COMM_GRAPH", payload: communicationGraph });
      this.dispatch({ type: "SREP", payload: srep });
      this.dispatch({ type: "SCIENTIFIC_AVAILABLE" });
      return true;
    } catch (error) {
      if (this.getState().replayId !== replayId) return false;
      if (this.isExpectedUnavailable(error, replayId)) {
        this.dispatch({ type: "SCIENTIFIC_UNAVAILABLE" });
        return false;
      }
      this.reportError(error);
      return false;
    }
  }

  async hydrateReplay(replayId: string) {
    const status = await this.refreshStatus(replayId);
    if (status && status.windows_processed > 0) {
      await this.refreshScientificState(replayId);
    }
  }

  async handleEvent(envelope: EventEnvelopeV1) {
    if (this.getState().replayId !== envelope.replay_id) return;
    this.dispatch({ type: "EVENT", envelope });
    const replayId = envelope.replay_id;

    switch (envelope.event_type) {
      case "REPLAY_CREATED":
      case "REPLAY_STARTED":
      case "REPLAY_RESUMED":
        await this.refreshStatus(replayId);
        return;
      case "WINDOW_COMPLETED":
        this.scheduleWindowRefresh(replayId);
        return;
      case "REPLAY_PAUSED":
      case "REPLAY_STEPPED": {
        const status = await this.refreshStatus(replayId);
        if (status && status.windows_processed > 0) {
          await this.refreshScientificState(replayId);
        }
        return;
      }
      case "DEVICE_STATE":
        this.applyPayload(envelope, DeviceStateV1Schema, (payload) =>
          this.dispatch({ type: "UPSERT_DEVICE_STATE", payload })
        );
        return;
      case "DEVICE_RISK_GRAPH_SNAPSHOT":
        this.applyPayload(envelope, DeviceRiskGraphSnapshotV1Schema, (payload) =>
          this.dispatch({ type: "RISK_GRAPH", payload })
        );
        return;
      case "COMMUNICATION_GRAPH_SNAPSHOT":
        this.applyPayload(
          envelope,
          CommunicationGraphSnapshotV1Schema,
          (payload) => this.dispatch({ type: "COMM_GRAPH", payload })
        );
        return;
      case "SREP_SNAPSHOT":
        this.applyPayload(envelope, SrepSnapshotV1Schema, (payload) =>
          this.dispatch({ type: "SREP", payload })
        );
        return;
      case "REPLAY_COMPLETED":
        await this.finalRefresh(replayId);
        return;
      case "REPLAY_FAILED":
        await this.refreshStatus(replayId);
        return;
      default:
        return;
    }
  }

  handleGap(replayId: string) {
    this.dispatch({ type: "EVENT_GAP" });
    void this.hydrateReplay(replayId);
  }

  reportError(error: unknown) {
    this.dispatch({
      type: "ERROR",
      message: error instanceof Error ? error.message : String(error),
    });
  }

  cancelPendingRefresh() {
    this.trailingWindowRefresh = false;
    if (this.pendingTimer !== null) {
      this.scheduler.clearTimeout(this.pendingTimer);
      this.pendingTimer = null;
    }
  }

  dispose() {
    this.cancelPendingRefresh();
  }

  private scheduleWindowRefresh(replayId: string) {
    if (this.pendingTimer !== null) return;
    if (this.windowRefresh !== null) {
      this.trailingWindowRefresh = true;
      return;
    }
    this.pendingTimer = this.scheduler.setTimeout(() => {
      this.pendingTimer = null;
      this.windowRefresh = this.refreshWindow(replayId).finally(() => {
        this.windowRefresh = null;
        if (this.trailingWindowRefresh) {
          this.trailingWindowRefresh = false;
          this.scheduleWindowRefresh(replayId);
        }
      });
    }, 300);
  }

  private async refreshWindow(replayId: string) {
    await this.refreshStatus(replayId);
    await this.refreshScientificState(replayId);
  }

  private async finalRefresh(replayId: string) {
    this.cancelPendingRefresh();
    if (this.windowRefresh) await this.windowRefresh;
    await this.refreshStatus(replayId);
    await this.refreshScientificState(replayId);
  }

  private applyPayload<T extends { replay_id: string }>(
    envelope: EventEnvelopeV1,
    schema: z.ZodType<T>,
    apply: (payload: T) => void
  ) {
    const parsed = schema.safeParse(envelope.payload);
    if (!parsed.success) {
      this.dispatch({
        type: "ERROR",
        message: `Invalid ${envelope.event_type} payload: ${parsed.error.message}`,
      });
      return;
    }
    if (parsed.data.replay_id !== envelope.replay_id) {
      this.dispatch({
        type: "ERROR",
        message: `${envelope.event_type} payload belongs to a different replay`,
      });
      return;
    }
    apply(parsed.data);
  }

  private isExpectedUnavailable(error: unknown, replayId: string) {
    const status = this.getState().status;
    return (
      error instanceof BackendConflictError &&
      error.status === 409 &&
      error.code === "no_scientific_state" &&
      (!status || status.replay_id !== replayId || status.windows_processed === 0)
    );
  }
}
