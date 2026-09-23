/** Backend-controlled replay console. The browser only formats authoritative values. */
import { useEffect, useState } from "react";
import type { SessionCapability } from "../api/contracts";
import { useReplayContext } from "../state/ReplayContext";
import { useReplayEvents } from "../hooks/useReplayEvents";
import { useSnapshots } from "../hooks/useSnapshots";
import { Header } from "../components/layout/Header";
import { ReplayControls } from "../components/controls/ReplayControls";
import { GraphWorkspace } from "../components/graphs/GraphWorkspace";
import { TrustGraphPlaceholder } from "../components/graphs/TrustGraphPlaceholder";
import { DeviceStateTable } from "../components/devices/DeviceStateTable";
import { FindingsStream } from "../components/findings/FindingsStream";
import { SnapshotPanel } from "../components/snapshots/SnapshotPanel";
import { ProvenancePanel } from "../components/provenance/ProvenancePanel";
import { EventGapBanner } from "../components/common/EventGapBanner";
import { BlackboardView } from "../components/blackboard/BlackboardView";
import { OrchestrationView } from "../components/orchestration/OrchestrationView";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/api/v1";

export function DashboardPage() {
  const { client, state, dispatch } = useReplayContext();
  const [sessions, setSessions] = useState<SessionCapability[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [recoveringReplay, setRecoveringReplay] = useState(true);
  const [activeView, setActiveView] = useState<"device" | "blackboard" | "orchestration">("device");
  const snapshots = useSnapshots(client);
  const synchronizer = useReplayEvents(client, dispatch, state, WS_BASE);

  useEffect(() => {
    let active = true;
    client
      .getSessions()
      .then((response) => {
        if (!active) return;
        setSessions(response.sessions);
        setSelectedSession(response.default_session || response.sessions[0]?.session_id || null);
        setSessionError(null);
      })
      .catch((error: unknown) => {
        if (active) setSessionError(formatError("Cannot load sessions", error));
      });
    return () => {
      active = false;
    };
  }, [client]);

  useEffect(() => {
    let active = true;
    void synchronizer.recoverActiveReplay().finally(() => {
      if (active) setRecoveringReplay(false);
    });
    return () => {
      active = false;
    };
  }, [synchronizer]);

  const status = state.status;
  const displayError = sessionError ?? state.error;
  const isRunning = status?.state === "RUNNING";
  const progress = status?.windows_total
    ? Math.min(100, (status.windows_processed / status.windows_total) * 100)
    : 0;

  return (
    <div className="dashboard">
      <Header />
      <main className="dashboard-shell">
        <ReplayControls
          sessions={sessions}
          selectedSession={selectedSession}
          onSessionChange={setSelectedSession}
          onCreate={(sessionId, mode, pacing) => synchronizer.createReplay(sessionId, mode, pacing)}
          onControl={(action, replayId) => synchronizer.control(action, replayId)}
          onRestart={(replayId, options) => synchronizer.restart(replayId, options)}
          onSaveSnapshot={() => (state.replayId ? snapshots.save(state.replayId) : Promise.resolve())}
          pacing={status?.pacing ?? "max"}
          initializing={recoveringReplay}
          onSpeedChange={(replayId, pacing) => synchronizer.setSpeed(replayId, pacing)}
        />

        {displayError && (
          <div role="alert" className="error-banner">
            <div><strong>Runtime notice</strong><span>{displayError}</span></div>
            <button
              className="icon-button"
              aria-label="Dismiss runtime notice"
              onClick={() => {
                setSessionError(null);
                dispatch({ type: "CLEAR_ERROR" });
              }}
            >
              ×
            </button>
          </div>
        )}
        {state.scientificUnavailable && (
          <div className="info-banner">
            Scientific snapshots are not available before the first completed window.
          </div>
        )}
        <EventGapBanner gap={state.gapDetected} truncated={state.eventHistoryTruncated} />

        <nav className="view-switch" aria-label="Dashboard view">
          <div
            className="primary-nav"
            role="tablist"
            aria-label="Primary navigation"
            onKeyDown={(event) => {
              const order: Array<"device" | "blackboard" | "orchestration"> = ["device", "blackboard", "orchestration"];
              const currentIndex = order.indexOf(activeView);
              let nextIndex: number | null = null;
              if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % order.length;
              else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + order.length) % order.length;
              else if (event.key === "Home") nextIndex = 0;
              else if (event.key === "End") nextIndex = order.length - 1;
              if (nextIndex !== null) {
                event.preventDefault();
                const nextView = order[nextIndex];
                setActiveView(nextView);
                // Move focus to the newly selected tab for roving keyboard nav
                const el = document.querySelector<HTMLElement>(`[data-testid="nav-${nextView === "device" ? "device-view" : nextView}"]`);
                el?.focus();
              }
            }}
          >
            <button
              role="tab"
              aria-selected={activeView === "device"}
              aria-controls="device-view"
              tabIndex={activeView === "device" ? 0 : -1}
              onClick={() => setActiveView("device")}
              data-testid="nav-device-view"
            >
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35"><rect x="2" y="2.5" width="5" height="5" rx="1"/><rect x="9" y="2.5" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>
              </span>
              Device View
            </button>
            <button
              role="tab"
              aria-selected={activeView === "blackboard"}
              aria-controls="blackboard-view"
              tabIndex={activeView === "blackboard" ? 0 : -1}
              onClick={() => setActiveView("blackboard")}
              data-testid="nav-blackboard"
            >
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35"><rect x="3" y="3" width="10" height="3" rx="1"/><rect x="3" y="7" width="10" height="3" rx="1"/><rect x="3" y="11" width="10" height="3" rx="1"/></svg>
              </span>
              Blackboard
            </button>
            <button
              role="tab"
              aria-selected={activeView === "orchestration"}
              aria-controls="orchestration-view-panel"
              tabIndex={activeView === "orchestration" ? 0 : -1}
              onClick={() => setActiveView("orchestration")}
              data-testid="nav-orchestration"
            >
              <span className="nav-icon" aria-hidden="true">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.35"><circle cx="8" cy="3.5" r="2"/><circle cx="3.5" cy="11.5" r="2"/><circle cx="12.5" cy="11.5" r="2"/><path d="M6.2 4.8 5 9.6M9.8 4.8 11 9.6M5.6 11.5H10.4"/></svg>
              </span>
              Orchestration
            </button>

          </div>
        </nav>

        {activeView === "device" && (
          <div id="device-view" role="tabpanel" aria-label="Device View">
            <section className="runtime-summary" aria-label="Replay summary">
              <div className="summary-item summary-item--status">
                <span className="eyebrow">Replay state</span>
                <div className={`runtime-state runtime-state--${(state.isStarting ? "starting" : status?.state ?? "none").toLowerCase()}`}>
                  <span className="runtime-state__dot" aria-hidden="true" />
                  <strong className="mono">{state.isStarting ? "Starting..." : status?.state ?? "Not created"}</strong>
                </div>
              </div>
              <Summary label="Windows processed" value={`${status?.windows_processed ?? 0} / ${status?.windows_total ?? "?"}`} />
              <Summary label="Findings emitted" value={String(sumValues(status?.findings_emitted))} />
              <Summary label="Current window" value={status?.last_window_id != null ? String(status.last_window_id + 1) : "-"} />
              <div className="progress-summary">
                <div><span>Replay progress</span><strong className="mono">{Math.round(progress)}%</strong></div>
                <div className="progress-track" role="progressbar" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100} aria-label="Replay progress"><i style={{ width: `${progress}%` }} /></div>
              </div>
            </section>

            <GraphWorkspace
              riskSnapshot={state.riskGraph}
              communicationSnapshot={state.commGraph}
              isRunning={isRunning}
            />

            <section className="analysis-grid" aria-label="Replay analysis panels">
              <div className="analysis-grid__summary">
                <ProvenancePanel />
              </div>
              <DeviceStateTable devices={state.deviceStates} />
              <FindingsStream events={state.events} />
              <TrustGraphPlaceholder />
              <SnapshotPanel
                snapshots={snapshots.snapshots}
                selected={snapshots.selectedSnapshot}
                loading={snapshots.loading}
                error={snapshots.error}
                onRead={snapshots.read}
                onCloseRead={snapshots.closeReadView}
              />
            </section>
          </div>
        )}

        {activeView === "blackboard" && (
          <div id="blackboard-view" role="tabpanel" aria-label="Blackboard">
            <BlackboardView client={client} />
          </div>
        )}

        {activeView === "orchestration" && (
          <div id="orchestration-view-panel" role="tabpanel" aria-label="Orchestration">
            <OrchestrationView />
          </div>
        )}


      </main>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return <div className="summary-item"><span>{label}</span><strong className="mono">{value}</strong></div>;
}

function sumValues(values: Record<string, number> | undefined) {
  return values ? Object.values(values).reduce((sum, value) => sum + value, 0) : 0;
}

function formatError(prefix: string, error: unknown) {
  return `${prefix}: ${error instanceof Error ? error.message : String(error)}`;
}
