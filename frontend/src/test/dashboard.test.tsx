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
  it("no longer renders beh risk, net risk or systemic columns", () => {
    const devices = [
      makeDeviceState({
        entity_id: "router",
        behavior_supported: false,
        propagated_risk: 0.12,
      }),
    ];
    render(<DeviceStateTable devices={devices} />);
    expect(screen.queryByTestId("beh-risk-router")).not.toBeInTheDocument();
    expect(screen.queryByText(/Beh risk/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Net risk/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Systemic/i)).not.toBeInTheDocument();
    expect(screen.getByText("router")).toBeInTheDocument();
  });

  it("inspector no longer shows beh/systemic risk, only propagated", async () => {
    const user = userEvent.setup();
    const devices = [
      makeDeviceState({
        entity_id: "soil-sensor",
        behavior_supported: true,
        propagated_risk: 0.42,
      }),
    ];
    render(<DeviceStateTable devices={devices} />);
    await user.click(screen.getByText("soil-sensor"));
    expect(await screen.findByLabelText("Selected device details")).toBeInTheDocument();
    expect(screen.queryByText(/Behavior risk/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Systemic risk/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Propagated risk/i)).toBeInTheDocument();
    expect(screen.getByText("0.420")).toBeInTheDocument();
  });

  it("renders device rows without risk columns", () => {
    const devices = [
      makeDeviceState({ entity_id: "edge1" }),
    ];
    render(<DeviceStateTable devices={devices} />);
    expect(screen.getByText("edge1")).toBeInTheDocument();
    expect(screen.queryByTestId("beh-risk-edge1")).not.toBeInTheDocument();
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
