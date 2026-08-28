import { useState } from "react";
// Stage 6 supplies this hook; Stage 7 only consumes its REST and stream state.
import { useOrchestration } from "../../hooks/useOrchestration";
import { DecisionBrowser } from "./DecisionBrowser";
import { DecisionDetailPanel } from "./DecisionDetailPanel";
import { DecisionTrace } from "./DecisionTrace";
import { LiveOrchestrationActivity } from "./LiveOrchestrationActivity";
import { OrchestrationOverview } from "./OrchestrationOverview";
import { OrchestratorCards } from "./OrchestratorCards";

export function OrchestrationView() {
  const orchestration = useOrchestration();
  const [selectedTraceKey, setSelectedTraceKey] = useState<string | null>(null);
  const [detailRequested, setDetailRequested] = useState(false);
  const streamOpen = orchestration.connectionState === "OPEN";

  return (
    <div className="orchestration-view" aria-label="Orchestration dashboard" data-testid="orchestration-view">
      <section className="orchestration-boundary" aria-labelledby="orchestration-boundary-title">
        <span className="eyebrow">Stage 7 / read-only explainability</span>
        <h1 id="orchestration-boundary-title">Three-orchestrator adjudication</h1>
        <p>Orchestrators adjudicate opaque route identifiers. They are separate from the three Blackboard storage replicas: Blackboard acknowledgements and health are never orchestrator votes or agreement.</p>
      </section>

      {(!streamOpen || orchestration.gapDetected || orchestration.localHistoryIncomplete) && (
        <div className="orchestration-notices">
          {!streamOpen && <div className="banner-warning" role="status">Orchestration stream state: <strong className="mono">{orchestration.connectionState}</strong>. REST decisions remain authoritative during disconnect or reconnect.</div>}
          {orchestration.gapDetected && <div className="banner-warning" role="alert">A live stream gap was detected. Some chronological facts may be missing; no events or lifecycle stages are fabricated.</div>}
          {orchestration.localHistoryIncomplete && <div className="banner-warning" role="alert">Local live history is incomplete or bounded. Use REST decision detail for retained authoritative terminal state; neither source is a durable all-time audit archive.</div>}
        </div>
      )}

      <OrchestrationOverview health={orchestration.health} loading={orchestration.loading} error={orchestration.error} onRefresh={orchestration.refreshAll} />
      <OrchestratorCards replicas={orchestration.replicas} note={orchestration.replicasNote} />
      <DecisionBrowser listing={orchestration.decisionListing} filters={orchestration.filters} loading={orchestration.decisionsLoading} setFilters={orchestration.updateFilters} onSelect={(decisionId) => { setDetailRequested(true); void orchestration.loadDecision(decisionId); }} />
      <LiveOrchestrationActivity events={orchestration.events} selectedTraceKey={selectedTraceKey} onSelectTrace={setSelectedTraceKey} />
      <DecisionTrace events={orchestration.events} selectedTraceKey={selectedTraceKey} onSelectTrace={setSelectedTraceKey} incomplete={orchestration.gapDetected || orchestration.localHistoryIncomplete} />

      {detailRequested && <DecisionDetailPanel decision={orchestration.decisionDetail} loading={orchestration.detailLoading} error={orchestration.detailError} onClose={() => { setDetailRequested(false); orchestration.clearDecisionDetail(); }} />}

      <footer className="orchestration-limitations">
        <strong>Scope and security limits</strong>
        <p>Three-replica, two-of-three quorum adjudication under authenticated orchestrator-message assumptions. This is not full Byzantine Fault Tolerance. Authentication proves key possession and message integrity under runtime-key assumptions; it does not prove sender honesty.</p>
        <p>Coordination is single-process. Keys are runtime-resident, caller principal is an application/audit identity rather than proof of authenticated origin or honesty, and decision/event history is bounded and non-durable. Two colluding authenticated orchestrators, a compromised valid key, malicious majority, and network partitions are not tolerated.</p>
        <p>This UI is observational only. It does not author or execute routes, enforce network access, or convert decisions into actions.</p>
      </footer>
    </div>
  );
}
