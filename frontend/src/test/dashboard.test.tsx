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
