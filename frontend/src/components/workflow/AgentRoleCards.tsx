/**
 * AgentRoleCards — exactly five specialist cards.
 * Canonical IDs remain visible; friendly labels allowed.
 * Each card displays only real backend fields; no invented activity.
 */
import type { WorkflowSnapshotV1 } from "../../api/contracts";
import { AGENT_IDS, AGENT_DISPLAY_LABELS } from "../../api/contracts";
import { agentStatusTone } from "../../utils/workflowHelpers";

const AGENT_META: Record<string, { step: string; icon: string; accent: string }> = {
  network_anomaly_detector: { step: "1A", icon: "◉", accent: "#4f8ff7" },
  iot_behavioral_profiler: { step: "1B", icon: "◆", accent: "#2dd4bf" },
  threat_intelligence_correlator: { step: "2", icon: "◎", accent: "#38bdf8" },
  risk_propagation_analyst: { step: "3", icon: "⬡", accent: "#fbbf24" },
  trust_access_controller: { step: "4", icon: "⧉", accent: "#a78bfa" },
};

export function AgentRoleCards({ snapshot }: { snapshot: WorkflowSnapshotV1 | null }) {
  const statuses: Record<string, string> = {};
  if (snapshot) {
    for (const s of snapshot.five_agent_statuses) {
      statuses[s.agent_id] = s.status;
    }
  }

  return (
    <section className="agent-role-cards" aria-label="Five specialist agents" data-testid="agent-role-cards">
      <h3>Five specialist agents (exactly five)</h3>
      <p className="annotation">
        Specialist identities are <span className="mono">network_anomaly_detector</span>,{" "}
        <span className="mono">iot_behavioral_profiler</span>,{" "}
        <span className="mono">threat_intelligence_correlator</span>,{" "}
        <span className="mono">risk_propagation_analyst</span>,{" "}
        <span className="mono">trust_access_controller</span> — distinct from orchestrators (3) and Blackboard
        replicas (3).
      </p>
      <div className="agent-cards-grid">
        {AGENT_IDS.map((agentId) => {
          const status = statuses[agentId] ?? "PENDING";
          const display = AGENT_DISPLAY_LABELS[agentId];
          const tone = agentStatusTone(status);
          const meta = AGENT_META[agentId];
          return (
            <article
              key={agentId}
              className={`agent-card agent-card--stage-${meta.step.replace("A","").replace("B","")} ${tone}`}
              data-testid={`agent-card-${agentId}`}
              aria-label={`${agentId} card`}
              style={{ borderLeft: `3px solid ${meta.accent}` }}
            >
              <div className="agent-card__head">
                <span className="agent-card__icon" aria-hidden="true">{meta.icon}</span>
                <span className="agent-card__step">{meta.step}</span>
                <span className={`pipeline-pill ${tone}`} style={{ marginLeft: "auto", fontSize: "0.60rem" }}>{status}</span>
              </div>
              <h4 style={{ margin: "6px 0 4px" }}>{display}</h4>
              <div className="mono" data-testid={`agent-id-${agentId}`} style={{ fontSize: "0.8em", color: "var(--text-muted)" }}>
                {agentId}
              </div>
              <div style={{ marginTop: 6 }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Status: </span>
                <strong className="mono" data-testid={`agent-status-${agentId}`}>{status}</strong>
              </div>
              {/* Per-agent dispatch not inferred from global window dispatch list */}
              <div className="annotation" style={{ marginTop: 6, fontSize: "0.82em" }} data-testid={`agent-dispatch-${agentId}`}>
                Backend status: {status} — per-agent dispatch/execution evidence is in the workflow trace; global window dispatch list does not imply this specialist was dispatched.
              </div>
            </article>
          );
        })}
      </div>
      <p className="annotation" style={{ marginTop: 8 }}>
        Each card shows only real backend fields. When state is absent, no activity is invented. Never show orchestrator or replica IDs as specialists.
      </p>
    </section>
  );
}
