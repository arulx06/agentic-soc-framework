import { describe, expect, it, vi } from "vitest";
import type {
  ReplayLifecycleClient,
  ReplayScheduler,
} from "../hooks/replaySynchronizer";
import { ReplaySynchronizer } from "../hooks/replaySynchronizer";
import {
  createInitialReplayState,
  replayReducer,
  type ReplayAction,
  type ReplayState,
} from "../state/replayReducer";
import type { ReplayStatusV1 } from "../api/contracts";
import { BackendConflictError } from "../api/validation";
import { makeCommGraph, makeEnvelope, makeRiskGraph, makeSrep } from "./fixtures";

function makeStatus(overrides: Partial<ReplayStatusV1> = {}): ReplayStatusV1 {
  return {
    schema_version: "replay_status_v1",
    replay_id: "r1",
    session_trace: "trace",
    state: "CREATED",
    source_mode: "feature_store",
    pacing: "max",
    windows_total: 13,
    windows_processed: 0,
    last_window_id: null,
    sequence_number: 0,
    findings_emitted: {},
    error: null,
    provenance: {},
    ...overrides,
  };
}

function makeClient(overrides: Partial<ReplayLifecycleClient> = {}) {
  const created = { ...makeStatus(), state: "CREATED" as const };
  return {
    createReplay: vi.fn(async () => ({ replay_id: "r1", status: created })),
    getStatus: vi.fn(async () => created),
    play: vi.fn(async () => ({ replay_id: "r1", state: "RUNNING" as const })),
    pause: vi.fn(async () => ({ replay_id: "r1", state: "PAUSED" as const })),
    resume: vi.fn(async () => ({ replay_id: "r1", state: "RUNNING" as const })),
    step: vi.fn(async () => ({ replay_id: "r1", state: "PAUSED" as const, stepped: true })),
    restart: vi.fn(async () => ({ previous_replay_id: "r1", new_replay_id: "r2" })),
    setSpeed: vi.fn(async () => ({ replay_id: "r1", pacing: "5x" as const })),
    getDeviceStates: vi.fn(async () => ({
      schema_version: "device_state_v1" as const,
      replay_id: "r1",
      devices: [],
    })),
    getDeviceRiskGraph: vi.fn(async () => makeRiskGraph()),
    getCommunicationGraph: vi.fn(async () => makeCommGraph()),
    getSrep: vi.fn(async () => makeSrep()),
    ...overrides,
  } satisfies ReplayLifecycleClient;
}

function makeHarness(client: ReplayLifecycleClient, scheduler?: ReplayScheduler) {
  let state: ReplayState = createInitialReplayState();
  const actions: ReplayAction[] = [];
  const dispatch = (action: ReplayAction) => {
    actions.push(action);
    state = replayReducer(state, action);
  };
  const synchronizer = new ReplaySynchronizer(client, dispatch, () => state, scheduler);
  return {
    synchronizer,
    actions,
    state: () => state,
    setReplay: () => dispatch({ type: "REPLAY_SET", replayId: "r1", status: makeStatus() }),
  };
}

describe("ReplaySynchronizer lifecycle authority", () => {
  it("Create performs one POST and zero scientific requests", async () => {
    const client = makeClient();
    const harness = makeHarness(client);
    await harness.synchronizer.createReplay("session", "feature_store", "max");

    expect(client.createReplay).toHaveBeenCalledOnce();
    expect(client.getStatus).not.toHaveBeenCalled();
    expect(client.getDeviceStates).not.toHaveBeenCalled();
    expect(client.getDeviceRiskGraph).not.toHaveBeenCalled();
    expect(client.getCommunicationGraph).not.toHaveBeenCalled();
    expect(client.getSrep).not.toHaveBeenCalled();
    expect(harness.state().status?.state).toBe("CREATED");
  });

  it("status-first hydration does not request science before a completed window", async () => {
    const client = makeClient();
    const harness = makeHarness(client);
    harness.setReplay();
    await harness.synchronizer.hydrateReplay("r1");

    expect(client.getStatus).toHaveBeenCalledOnce();
    expect(client.getDeviceStates).not.toHaveBeenCalled();
  });

  it("Play refreshes authoritative status without eagerly fetching science", async () => {
    const running = makeStatus({ state: "RUNNING" });
    const client = makeClient({ getStatus: vi.fn(async () => running) });
    const harness = makeHarness(client);
    harness.setReplay();
    await harness.synchronizer.control("play", "r1");

    expect(client.play).toHaveBeenCalledOnce();
    expect(client.getStatus).toHaveBeenCalledOnce();
    expect(client.getDeviceRiskGraph).not.toHaveBeenCalled();
    expect(harness.state().status?.state).toBe("RUNNING");
  });

  it("coalesces WINDOW_COMPLETED bursts before authoritative hydration", async () => {
    const callbacks: Array<() => void> = [];
    const scheduler: ReplayScheduler = {
      setTimeout: vi.fn((next) => {
        callbacks.push(next);
        return 1;
      }),
      clearTimeout: vi.fn(),
    };
    const ready = makeStatus({ state: "RUNNING", windows_processed: 1, last_window_id: 0 });
    const client = makeClient({ getStatus: vi.fn(async () => ready) });
    const harness = makeHarness(client, scheduler);
    harness.setReplay();

    await harness.synchronizer.handleEvent(makeEnvelope("WINDOW_COMPLETED", { replay_id: "r1" }));
    await harness.synchronizer.handleEvent(makeEnvelope("WINDOW_COMPLETED", { replay_id: "r1" }));
    expect(scheduler.setTimeout).toHaveBeenCalledOnce();
    callbacks[0]?.();

    await vi.waitFor(() => expect(client.getSrep).toHaveBeenCalledOnce());
    expect(client.getStatus).toHaveBeenCalledOnce();
    expect(client.getDeviceStates).toHaveBeenCalledOnce();
    expect(harness.actions.filter((action) => action.type === "EVENT")).toHaveLength(2);
  });

  it("completion converges to COMPLETED and performs a final scientific refresh", async () => {
    const completed = makeStatus({
      state: "COMPLETED",
      windows_processed: 13,
      last_window_id: 12,
    });
    const client = makeClient({ getStatus: vi.fn(async () => completed) });
    const harness = makeHarness(client);
    harness.setReplay();
    await harness.synchronizer.handleEvent(
      makeEnvelope("REPLAY_COMPLETED", { replay_id: "r1" })
    );

    expect(harness.state().status?.state).toBe("COMPLETED");
    expect(client.getDeviceStates).toHaveBeenCalledOnce();
    expect(client.getSrep).toHaveBeenCalledOnce();
  });

  it("hydrates final science when a control races replay completion", async () => {
    const completed = makeStatus({
      state: "COMPLETED",
      windows_processed: 13,
      last_window_id: 12,
    });
    const client = makeClient({
      play: vi.fn(async () => {
        throw new BackendConflictError(409, "replay_completed", "restart required");
      }),
      getStatus: vi.fn(async () => completed),
    });
    const harness = makeHarness(client);
    harness.setReplay();

    await harness.synchronizer.control("play", "r1");

    expect(harness.state().status?.state).toBe("COMPLETED");
    expect(client.getDeviceRiskGraph).toHaveBeenCalledOnce();
    expect(client.getSrep).toHaveBeenCalledOnce();
    expect(harness.state().error).toContain("restart required");
  });
});

describe("Hybrid lifecycle: restart overrides, stale protection, terminal", () => {
  it("restart forwards current UI selections to backend", async () => {
    const client = makeClient();
    const harness = makeHarness(client);
    harness.setReplay();
    await harness.synchronizer.restart("r1", {
      sessionId: "new-session",
      sourceMode: "feature_store",
      pacing: "5x",
    });
    expect(client.restart).toHaveBeenCalledWith("r1", {
      sessionId: "new-session",
      sourceMode: "feature_store",
      pacing: "5x",
    });
    expect(harness.state().replayId).toBe("r2");
    expect(harness.state().status).toBeNull();
    expect(harness.state().events).toHaveLength(0);
  });

  it("restart without overrides preserves backward compat (undefined)", async () => {
    const client = makeClient();
    const harness = makeHarness(client);
    harness.setReplay();
    await harness.synchronizer.restart("r1");
    expect(client.restart).toHaveBeenCalledWith("r1", undefined);
  });

  it("stale events belonging to previous replay ID are ignored after restart", async () => {
    const client = makeClient();
    const harness = makeHarness(client);
    harness.setReplay();
    await harness.synchronizer.restart("r1");
    // state now points to r2
    expect(harness.state().replayId).toBe("r2");
    const stale = makeEnvelope("WINDOW_COMPLETED", { replay_id: "r1" });
    await harness.synchronizer.handleEvent(stale);
    // No EVENT dispatched for stale id, status not fetched for stale
    expect(harness.actions.filter((a) => a.type === "EVENT" && (a as any).envelope?.replay_id === "r1")).toHaveLength(0);
  });

  it("stale getStatus responses for old replay do not overwrite new replay", async () => {
    let resolveOld: (v: ReplayStatusV1) => void = () => {};
    const oldStatusPromise = new Promise<ReplayStatusV1>((res) => (resolveOld = res));
    const client = makeClient({
      getStatus: vi.fn((rid: string) => {
        if (rid === "r1") return oldStatusPromise;
        return Promise.resolve(makeStatus({ replay_id: "r2", state: "RUNNING" }));
      }),
    });
    const harness = makeHarness(client);
    harness.setReplay(); // r1
    const hydrateOld = harness.synchronizer.refreshStatus("r1");
    await harness.synchronizer.restart("r1"); // now r2, status null
    // Resolve old request late
    resolveOld(makeStatus({ replay_id: "r1", state: "RUNNING" }));
    await hydrateOld;
    // Should still be on r2 with null/unchanged, not overwritten to r1 state
    expect(harness.state().replayId).toBe("r2");
    expect(harness.state().status).toBeNull();
  });

  it("restart clears pending window refreshes", async () => {
    const scheduler: ReplayScheduler = {
      setTimeout: vi.fn(() => 1),
      clearTimeout: vi.fn(),
    };
    const client = makeClient();
    const harness = makeHarness(client, scheduler);
    harness.setReplay();
    await harness.synchronizer.handleEvent(makeEnvelope("WINDOW_COMPLETED", { replay_id: "r1" }));
    expect(scheduler.setTimeout).toHaveBeenCalledOnce();
    await harness.synchronizer.restart("r1");
    expect(scheduler.clearTimeout).toHaveBeenCalled();
    expect(harness.state().replayId).toBe("r2");
  });

  it("terminal replay allows create not blocked", async () => {
    const completed = makeStatus({ state: "COMPLETED", windows_processed: 13 });
    const client = makeClient({
      getStatus: vi.fn(async () => completed),
      createReplay: vi.fn(async () => ({
        replay_id: "r2",
        status: makeStatus({ replay_id: "r2", state: "CREATED" }),
      })) as any,
    });
    const harness = makeHarness(client);
    harness.setReplay();
    // Simulate hydration to COMPLETED
    await harness.synchronizer.handleEvent(makeEnvelope("REPLAY_COMPLETED", { replay_id: "r1" }));
    expect(harness.state().status?.state).toBe("COMPLETED");
    // Now new create should succeed (terminal does not block)
    await harness.synchronizer.createReplay("session", "feature_store", "max");
    expect(client.createReplay).toHaveBeenCalledWith("session", "feature_store", "max");
    expect(harness.state().replayId).toBe("r2");
    expect(harness.state().status?.state).toBe("CREATED");
  });
});
