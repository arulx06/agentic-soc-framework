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
import { SrepPanel } from "../components/srep/SrepPanel";
import { SnapshotPanel } from "../components/snapshots/SnapshotPanel";
import { ProvenancePanel } from "../components/provenance/ProvenancePanel";
import { EventGapBanner } from "../components/common/EventGapBanner";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000/api/v1";

export function DashboardPage() {
  const { client, state, dispatch } = useReplayContext();
  const [sessions, setSessions] = useState<SessionCapability[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
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

  const status = state.status;
  const displayError = sessionError ?? state.error;
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

        <section className="runtime-summary" aria-label="Replay summary">
          <Summary label="Replay state" value={status?.state ?? "Not created"} />
          <Summary label="Windows processed" value={`${status?.windows_processed ?? 0} / ${status?.windows_total ?? "?"}`} />
          <Summary label="Findings emitted" value={String(sumValues(status?.findings_emitted))} />
          <Summary label="Current window" value={String(status?.last_window_id ?? "-")} />
          <div className="progress-summary">
            <div><span>Replay progress</span><strong className="mono">{Math.round(progress)}%</strong></div>
            <div className="progress-track"><i style={{ width: `${progress}%` }} /></div>
          </div>
        </section>

        <GraphWorkspace
          riskSnapshot={state.riskGraph}
          communicationSnapshot={state.commGraph}
        />

        <section className="analysis-grid" aria-label="Replay analysis panels">
          <div className="analysis-grid__summary">
            <SrepPanel srep={state.srep} />
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
