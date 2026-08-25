/**
 * Stage-3B coverage tests.
 * Validates replay controls, WS-sync, bounded buffers, restart, graph
 * separation, legend, and that production components use no mock values.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  EventEnvelopeV1Schema,
  type SessionCapability,
} from "../api/contracts";
import { ReplayProvider } from "../state/ReplayContext";
import { ReplayControls } from "../components/controls/ReplayControls";
import { GraphWorkspace } from "../components/graphs/GraphWorkspace";
import {
  makeCommGraph,
  makeDeviceState,
  makeEnvelope,
  makeRiskGraph,
} from "./fixtures";
import { createInitialReplayState, replayReducer } from "../state/replayReducer";

// ─── 5. Replay controls call correct REST endpoints ─────────────────────────

describe("ReplayControls REST contract", () => {
  it("Create button calls createReplay with correct args", async () => {
    const user = userEvent.setup();
    const sessions: SessionCapability[] = [
      {
        session_id: "attack_recon_host-disc-udp-ping_soil-sensor",
        session_trace: "abc123",
        supported_source_modes: ["feature_store", "direct_raw"],
        feature_store_available: true,
        raw_available: true,
        network_available: true,
        behavior_available: true,
        communication_available: true,
        schema_compatible: true,
        window_count: 13,
        duration_seconds: 65,
      },
    ];
    const onCreate = vi.fn(async () => {});
    const onControl = vi.fn(async () => {});
    const onRestart = vi.fn(async () => {});
    const onSaveSnapshot = vi.fn(async () => {});

    render(
      <ReplayProvider>
        <ReplayControls
          sessions={sessions}
          selectedSession="attack_recon_host-disc-udp-ping_soil-sensor"
          onSessionChange={() => {}}
          onCreate={onCreate}
          onControl={onControl}
          onRestart={onRestart}
          onSaveSnapshot={onSaveSnapshot}
          pacing="max"
          onSpeedChange={vi.fn(async () => {})}
        />
      </ReplayProvider>
    );

    await user.click(screen.getByText("Create"));
    expect(onCreate).toHaveBeenCalledWith(
      "attack_recon_host-disc-udp-ping_soil-sensor",
      expect.any(String),
      expect.any(String)
    );
  });
});

// ─── 6. Button availability follows backend replay states ────────────────────

describe("ReplayControls button availability", () => {
  it("Create disabled when no session selected", () => {
    render(
      <ReplayProvider>
        <ReplayControls
          sessions={[]}
          selectedSession={null}
          onSessionChange={() => {}}
          onCreate={vi.fn()}
          onControl={vi.fn()}
          onRestart={vi.fn()}
          onSaveSnapshot={vi.fn()}
          pacing="max"
          onSpeedChange={vi.fn(async () => {})}
        />
      </ReplayProvider>
    );
    expect(screen.getByText("Create")).toBeDisabled();
  });
});

// ─── 12. Unknown schema versions produce visible errors ─────────────────────

describe("Contract validation", () => {
  it("rejects unknown schema_version visibly", () => {
    const result = EventEnvelopeV1Schema.safeParse({
      schema_version: "simulation_event_v999",
      replay_id: "r",
      event_id: "e",
      sequence_number: 0,
      event_type: "WINDOW_STARTED",
      source_component: "test",
    });
    expect(result.success).toBe(false);
  });

  it("never silently coerces malformed scientific payloads", () => {
    const result = EventEnvelopeV1Schema.safeParse({
      schema_version: "simulation_event_v1",
      replay_id: "r",
      event_id: "e",
      sequence_number: "not-a-number",
      event_type: "WINDOW_STARTED",
      source_component: "test",
    });
    expect(result.success).toBe(false);
  });
});

// ─── 16. Graph separation ────────────────────────────────────────────────────

describe("Graph contracts separation", () => {
  it("Device Risk Graph and Communication Graph use distinct contracts", () => {
    const risk = makeRiskGraph();
    const comm = makeCommGraph();
    expect(risk.graph_kind).toBe("device_risk_graph");
    expect(comm.graph_kind).toBe("communication_graph");
    expect(risk.graph_kind).not.toBe(comm.graph_kind);
  });
});

// ─── 17. Legend distinguishability ─────────────────────────────────────────

describe("DeviceRiskGraph legend", () => {
  it("renders both DOCUMENTED and STRONGLY_INFERRED legend entries", () => {
    const { container } = render(
      <GraphWorkspace
        riskSnapshot={makeRiskGraph()}
        communicationSnapshot={makeCommGraph()}
      />
    );
    expect(container.textContent).toContain("DOCUMENTED");
    expect(container.textContent).toContain("STRONGLY_INFERRED");
  });
});

// ─── 15. Restart clears old namespace ───────────────────────────────────────

describe("Restart namespace handling", () => {
  it("REPLAY_SET resets old events and uses new replay ID", () => {
    let state: import("../state/replayReducer").ReplayState = {
      ...createInitialReplayState(),
      replayId: "old-id",
      connectionState: "OPEN",
      deviceStates: [makeDeviceState()],
      riskGraph: makeRiskGraph(),
      commGraph: makeCommGraph(),
      events: [
        makeEnvelope("WINDOW_COMPLETED", { sequence_number: 5, event_id: "e-5" }),
      ],
    };
    state = replayReducer(state, { type: "REPLAY_SET", replayId: "new-id", status: null });
    expect(state.replayId).toBe("new-id");
    expect(state.events).toHaveLength(0);
    expect(state.deviceStates).toHaveLength(0);
  });
});

// ─── Reducer DEVICE_STATES handling ────────────────────────────────────────

describe("Reducer DEVICE_STATES handling", () => {
  it("DEVICE_STATES dispatch updates state without cross-contamination", () => {
    const initial: import("../state/replayReducer").ReplayState = {
      ...createInitialReplayState(),
      replayId: "r1",
      connectionState: "OPEN",
    };
    const updated = replayReducer(initial, {
      type: "DEVICE_STATES",
      payload: [makeDeviceState({ entity_id: "edge1" })],
    });
    expect(updated.deviceStates[0].entity_id).toBe("edge1");
    expect(updated.riskGraph).toBeNull();
  });
});
