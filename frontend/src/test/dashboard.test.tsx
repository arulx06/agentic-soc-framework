/** Dashboard integration tests (§21.1–§21.12 requirements). */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReplayProvider } from "../state/ReplayContext";
import { Header } from "../components/layout/Header";
import { DeviceStateTable } from "../components/devices/DeviceStateTable";
import { TrustGraphPlaceholder } from "../components/graphs/TrustGraphPlaceholder";
import { SrepPanel } from "../components/srep/SrepPanel";
import { makeDeviceState, makeSrep } from "../test/fixtures";

describe("Header", () => {
  it("renders DEVICE_ONLY badge prominently", () => {
    render(
      <ReplayProvider>
        <Header />
      </ReplayProvider>
    );
    const badge = screen.getByTestId("srep-mode-badge");
    expect(badge).toHaveTextContent("SREP MODE: DEVICE_ONLY");
  });

  it("renders smoke artifact warnings", () => {
    render(
      <ReplayProvider>
        <Header />
      </ReplayProvider>
    );
    expect(screen.getByText("SMOKE MODEL ARTIFACTS")).toBeInTheDocument();
    expect(screen.getByText("NOT RESEARCH RESULTS")).toBeInTheDocument();
  });

  it("shows Window windows_processed / windows_total (13/13) not raw W12", async () => {
    const { ReplayContext } = await import("../state/ReplayContext");
    const { createInitialReplayState } = await import("../state/replayReducer");
    const status = {
      schema_version: "replay_status_v1" as const,
      replay_id: "r1",
      session_trace: "trace",
      state: "COMPLETED" as const,
      source_mode: "feature_store",
      pacing: "max" as const,
      windows_total: 13,
      windows_processed: 13,
      last_window_id: 12,
      sequence_number: 42,
      findings_emitted: {},
      error: null,
      provenance: {},
    };
    const state = { ...createInitialReplayState(), replayId: "r1", status, connectionState: "CLOSED" as const };
    render(
      <ReplayContext.Provider value={{ client: null as unknown as import("../api/client").ApiClient, state, dispatch: () => {} }}>
        <Header />
      </ReplayContext.Provider>
    );
    expect(screen.getByText(/Window 13 \/ 13/)).toBeInTheDocument();
    expect(screen.queryByText(/W12/)).not.toBeInTheDocument();
    expect(screen.getByText(/seq 42/)).toBeInTheDocument();
  });
});

describe("Device-state table", () => {
  it("unsupported behaviour renders N/A / Unsupported, never 0", () => {
    const devices = [
      makeDeviceState({
        entity_id: "router",
        behavior_supported: false,
        behavior_risk: null,
      }),
    ];
    render(<DeviceStateTable devices={devices} />);
    const cell = screen.getByTestId("beh-risk-router");
    expect(cell).toHaveTextContent("N/A / Unsupported");
    expect(cell).not.toHaveTextContent(/^0\.000$/);
  });

  it("supported zero risk renders as 0.000", () => {
    const devices = [
      makeDeviceState({
        entity_id: "soil-sensor",
        behavior_supported: true,
        behavior_risk: 0,
      }),
    ];
    render(<DeviceStateTable devices={devices} />);
    expect(screen.getByTestId("beh-risk-soil-sensor")).toHaveTextContent(
      "0.000"
    );
  });

  it("supported non-zero risk renders numerically", () => {
    const devices = [
      makeDeviceState({ entity_id: "edge1", behavior_risk: 0.42 }),
    ];
    render(<DeviceStateTable devices={devices} />);
    expect(screen.getByTestId("beh-risk-edge1")).toHaveTextContent("0.420");
  });
});

describe("Agent Trust Graph placeholder", () => {
  it("renders only the disabled placeholder with no graph content", () => {
    render(<TrustGraphPlaceholder />);
    expect(
      screen.getByText(/Not yet implemented/)
    ).toBeInTheDocument();
    // No cytoscape canvas or SVG nodes
    expect(document.querySelector("[data-cy]")).toBeNull();
  });
});

describe("SREP panel", () => {
  it("displays DEVICE_ONLY mode from backend data", () => {
    render(<SrepPanel srep={makeSrep()} />);
    expect(screen.getByText("DEVICE_ONLY")).toBeInTheDocument();
    expect(screen.getByText(/3.318/)).toBeInTheDocument();
    expect(screen.getByText(/13/)).toBeInTheDocument(); // steps replayed
  });
});
