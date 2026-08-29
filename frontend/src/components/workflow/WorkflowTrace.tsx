/**
 * WorkflowTrace — five-agent causal trace, chronological by sequence_number.
 * Shows backend facts only; never synthesizes absent steps.
 */
import { useMemo } from "react";
import type { EventEnvelopeV1 } from "../../api/contracts";
import { sortChronologically } from "../../utils/workflowHelpers";

export function WorkflowTrace({
  events,
  selectedEntityId,
  selectedWindowId,
}: {
  events: EventEnvelopeV1[];
  selectedEntityId: string | null;
  selectedWindowId: number | null;
}) {
  // Filter to workflow + orchestration events relevant to workflow, sorted by sequence_number
  const trace = useMemo(() => {
    const relevant = events.filter((e) => {
      // Workflow events or orchestration events that are part of scientific replay
      const types = new Set([
        "WORKFLOW_WINDOW_STARTED",
        "AGENT_DISPATCHED",
        "AGENT_EXECUTION_STARTED",
        "AGENT_EXECUTION_COMPLETED",
        "AGENT_EXECUTION_FAILED",
        "AGENT_EXECUTION_SKIPPED",
        "THREAT_CORRELATION_PRODUCED",
        "RISK_RECOMMENDATION_PRODUCED",
        "ACCESS_RECOMMENDATION_PRODUCED",
        "ENFORCEMENT_DECISION_COMMITTED",
        "CONFIRMED_FEEDBACK_RECORDED",
        "WORKFLOW_WINDOW_COMPLETED",
        "WORKFLOW_WINDOW_FAILED",
        "ORCHESTRATION_REQUEST_RECEIVED",
        "ORCHESTRATOR_PROPOSAL",
        "ORCHESTRATOR_VOTE",
        "ORCHESTRATOR_TIMEOUT",
        "ORCHESTRATOR_DELAYED",
        "ORCHESTRATOR_OMISSION",
        "ORCHESTRATOR_STATUS",
        "ORCHESTRATION_QUORUM_REACHED",
        "ORCHESTRATION_NO_QUORUM",
        "ORCHESTRATION_DECISION",
      ]);
      if (!types.has(e.event_type)) return false;
      // Entity filter: if selectedEntityId, show events for that entity OR window-scope or null entity (orchestration)
      if (selectedEntityId) {
        // Keep if entity_id matches selected, or is window-scope/null for orchestration aggregation
        if (e.entity_id === selectedEntityId) return true;
        if (e.entity_id === "window-scope") return true;
        if (e.entity_id === null && selectedWindowId !== null && e.window_id === selectedWindowId) return true;
        // Also keep orchestration events for the window regardless of entity
        if (e.event_type.startsWith("ORCHESTRATION") || e.event_type.startsWith("ORCHESTRATOR")) {
          return selectedWindowId === null || e.window_id === selectedWindowId;
        }
        return false;
      }
      if (selectedWindowId !== null) {
        return e.window_id === selectedWindowId;
      }
      return true;
    });
    return sortChronologically(relevant);
  }, [events, selectedEntityId, selectedWindowId]);

  if (trace.length === 0) {
    return (
      <div className="compact-empty" data-testid="trace-empty">
        No workflow trace events for selected entity/window — run a replay or select an entity with evidence.
      </div>
    );
  }

  return (
    <section className="workflow-trace" aria-label="Five-agent causal trace" data-testid="workflow-trace">
      <h4>Five-agent causal trace (sequence_number order)</h4>
      <p className="annotation">
        Stage-6 orchestration → Agent dispatched → Execution → Finding/output → Gateway/Blackboard → next specialist → AccessRecommendation → ActionCommitter → EnforcementDecision. Never synthesizes absent steps; IDs link actual events.
      </p>
      <div style={{ maxHeight: 320, overflowY: "auto", border: "1px solid var(--border-subtle)", borderRadius: 4 }}>
        <table role="table" aria-label="Workflow trace" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85em" }}>
          <thead>
            <tr style={{ position: "sticky", top: 0, background: "var(--bg-surface)" }}>
              <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid var(--border-subtle)" }}>Seq</th>
              <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid var(--border-subtle)" }}>Type</th>
              <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid var(--border-subtle)" }}>Window</th>
              <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid var(--border-subtle)" }}>Entity</th>
              <th style={{ textAlign: "left", padding: 4, borderBottom: "1px solid var(--border-subtle)" }}>IDs / Payload</th>
            </tr>
          </thead>
          <tbody>
            {trace.map((e) => (
              <tr key={e.event_id} data-testid={`trace-row-${e.sequence_number}`} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                <td className="mono" style={{ padding: 4 }}>{e.sequence_number}</td>
                <td className="mono" data-testid={`trace-type-${e.sequence_number}`}>{e.event_type}</td>
                <td className="mono" style={{ padding: 4 }}>{e.window_id ?? "—"}</td>
                <td className="mono" style={{ padding: 4 }}>{e.entity_id ?? "—"}</td>
                <td className="mono" style={{ padding: 4, maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={JSON.stringify(e.payload)}>
                  {!!(e.payload as Record<string, unknown>)?.request_id && <span>req:{String((e.payload as Record<string, unknown>).request_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.round_id && <span>round:{String((e.payload as Record<string, unknown>).round_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.decision_id && <span>dec:{String((e.payload as Record<string, unknown>).decision_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.dispatch_id && <span>disp:{String((e.payload as Record<string, unknown>).dispatch_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.execution_id && <span>exec:{String((e.payload as Record<string, unknown>).execution_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.agent_id && <span>agent:{String((e.payload as Record<string, unknown>).agent_id)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.correlation_id && <span>corr:{String((e.payload as Record<string, unknown>).correlation_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.recommendation_id && <span>rec:{String((e.payload as Record<string, unknown>).recommendation_id).slice(0, 8)} </span>}
                  {!!(e.payload as Record<string, unknown>)?.decision_id && !(e.payload as Record<string, unknown>)?.request_id && <span>decision:{String((e.payload as Record<string, unknown>).decision_id).slice(0, 8)}</span>}
                  {JSON.stringify(e.payload).slice(0, 80)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="annotation">Chronology follows backend <span className="mono">sequence_number</span> within selected scientific replay. Stable sorting only for non-chronological tables.</p>
    </section>
  );
}
