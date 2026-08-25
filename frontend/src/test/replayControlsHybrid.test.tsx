import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReplayControls } from "../components/controls/ReplayControls";
import type { SessionCapability } from "../api/contracts";
import { createInitialReplayState } from "../state/replayReducer";
import type { ReplayStatusV1 } from "../api/contracts";

// Mock the context hook
const mockUseReplayContext = vi.fn();
vi.mock("../state/ReplayContext", () => ({
  useReplayContext: () => mockUseReplayContext(),
}));

function makeSession(): SessionCapability {
  return {
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
  };
}

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

describe("ReplayControls hybrid lifecycle fixes", () => {
  const sessions = [makeSession()];
  const baseProps = {
    sessions,
    selectedSession: "attack_recon_host-disc-udp-ping_soil-sensor" as string | null,
    onSessionChange: vi.fn(),
    onCreate: vi.fn(async () => {}),
    onControl: vi.fn(async () => {}),
    onRestart: vi.fn(async () => {}),
    onSaveSnapshot: vi.fn(async () => {}),
    pacing: "max",
    onSpeedChange: vi.fn(async () => {}),
  };

  beforeEach(() => vi.clearAllMocks());

  it("Create enabled after COMPLETED (terminal does not block)", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "COMPLETED", windows_processed: 13 }),
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Create")).not.toBeDisabled();
  });

  it("Create enabled after FAILED", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "FAILED" }),
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Create")).not.toBeDisabled();
  });

  it("Create disabled while active CREATED/RUNNING/PAUSED", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "RUNNING" }),
      },
    });
    const { unmount } = render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Create")).toBeDisabled();
    unmount();

    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "PAUSED" }),
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Create")).toBeDisabled();
  });

  it("Create disabled while loading (status null after restart)", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r2",
        status: null,
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Create")).toBeDisabled();
  });

  it("Play disabled while loading (status null) - prevents duplicate play race", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r2",
        status: null,
      },
    });
    render(<ReplayControls {...baseProps} />);
    const play = screen.getByText("Play");
    expect(play).toBeDisabled();
  });

  it("Play enabled when CREATED, disabled when RUNNING, Resume when PAUSED", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "CREATED" }),
      },
    });
    const { unmount } = render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Play")).not.toBeDisabled();
    unmount();

    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "RUNNING" }),
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Play")).toBeDisabled();
  });

  it("Pacing disabled when terminal or loading, enabled when active", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "COMPLETED" }),
      },
    });
    const { unmount } = render(<ReplayControls {...baseProps} />);
    expect(screen.getByLabelText("Pacing")).toBeDisabled();
    unmount();

    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r2",
        status: null,
      },
    });
    const { unmount: unmount2 } = render(<ReplayControls {...baseProps} />);
    expect(screen.getByLabelText("Pacing")).toBeDisabled();
    unmount2();

    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "RUNNING" }),
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByLabelText("Pacing")).not.toBeDisabled();
  });

  it("Restart passes current UI selections to onRestart", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    const onRestart = vi.fn(async () => {});
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "COMPLETED" }),
      },
    });
    render(
      <ReplayControls
        {...baseProps}
        onRestart={onRestart}
        selectedSession="attack_recon_host-disc-udp-ping_soil-sensor"
        pacing="max"
      />
    );
    // Change pacing to 5x triggers onSpeedChange but for restart we check click
    await user.click(screen.getByText("Restart"));
    expect(onRestart).toHaveBeenCalledWith("r1", {
      sessionId: "attack_recon_host-disc-udp-ping_soil-sensor",
      sourceMode: expect.any(String),
      pacing: expect.any(String),
    });
    const call = (onRestart.mock.calls[0] as unknown as [string, { pacing: string }] | undefined)?.[1];
    expect(call?.pacing).toBe("max");
  });

  it("Play stays disabled while isStarting (Restart CREATED but already starting)", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r2",
        status: makeStatus({ state: "CREATED" }),
        isStarting: true,
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Play")).toBeDisabled();
    expect(screen.getByText("Create")).toBeDisabled();
  });

  it("Play enabled when CREATED and not starting, disabled when starting", () => {
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "CREATED" }),
        isStarting: false,
      },
    });
    const { unmount } = render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Play")).not.toBeDisabled();
    unmount();
    mockUseReplayContext.mockReturnValue({
      state: {
        ...createInitialReplayState(),
        replayId: "r1",
        status: makeStatus({ state: "CREATED" }),
        isStarting: true,
      },
    });
    render(<ReplayControls {...baseProps} />);
    expect(screen.getByText("Play")).toBeDisabled();
  });
});
