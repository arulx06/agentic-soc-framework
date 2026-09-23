/**
 * WorkflowPipeline — read-only scientific pipeline visualization.
 * Network + Behaviour as separate inputs converging at Finding Gateway,
 * then Threat Correlator → Risk Analyst → Trust & Access (PRE_LZTAF) → Enforcement.
 * All states derived from backend snapshot/events; no inferred execution.
 */
import type { WorkflowSnapshotV1, EventEnvelopeV1 } from "../../api/contracts";
import { AGENT_IDS } from "../../api/contracts";
import { agentStatusTone } from "../../utils/workflowHelpers";

interface Props {
  snapshot: WorkflowSnapshotV1 | null;
  selectedEntityId: string | null;
  selectedWindowId: number | null;
  events: EventEnvelopeV1[];
}

function agentStatus(snapshot: WorkflowSnapshotV1 | null, agentId: string): string {
  if (!snapshot) return "PENDING";
  const s = snapshot.five_agent_statuses.find((x) => x.agent_id === agentId);
  return s?.status ?? "PENDING";
}

export function WorkflowPipeline({ snapshot, selectedEntityId, selectedWindowId, events }: Props) {
  const hasSnapshot = !!snapshot;
  // Gateway: derive from retained GATEWAY events for selected entity/window
  const gateway = (() => {
    if (!selectedEntityId) return { label: "No entity selected", tone: "tone-unknown" as const, detail: "Select an entity" };
    const gw = events.filter(
      (e) => (e.event_type === "GATEWAY_ACCEPTED" || e.event_type === "GATEWAY_REJECTED") && e.entity_id === selectedEntityId && (selectedWindowId === null || e.window_id === selectedWindowId)
    );
    if (gw.length === 0) return { label: "No gateway evidence in retained history", tone: "tone-unknown" as const, detail: "REST remains authoritative" };
    const hasAccept = gw.some((x) => x.event_type === "GATEWAY_ACCEPTED");
    const hasReject = gw.some((x) => x.event_type === "GATEWAY_REJECTED");
    if (hasAccept && !hasReject) return { label: "Accepted", tone: "tone-committed" as const, detail: `${gw.length} event(s)` };
    if (hasReject && !hasAccept) return { label: "Rejected", tone: "tone-rejected" as const, detail: `${gw.length} event(s) — see reason` };
    return { label: "Mixed (accepted + rejected)", tone: "tone-partial" as const, detail: `${gw.length} events` };
  })();

  const threat = (() => {
    if (!snapshot || !selectedEntityId) return { label: "No data", tone: "tone-unknown" as const };
    const c = snapshot.latest_threat_correlations.find((x) => x.entity_id === selectedEntityId);
    if (!c) return { label: "No correlation", tone: "tone-unknown" as const };
    const m = c.mapping_status;
    if (m === "MATCHED") return { label: "MATCHED", tone: "tone-matched" as const };
    if (m === "UNMAPPED") return { label: "UNMAPPED", tone: "tone-unmapped" as const };
    return { label: "UNSUPPORTED", tone: "tone-unsupported" as const };
  })();

  const risk = (() => {
    if (!snapshot || !selectedEntityId) return { label: "No data", tone: "tone-unknown" as const };
    const r = snapshot.latest_risk_recommendations.find((x) => x.entity_id === selectedEntityId);
    if (!r) return { label: "No recommendation", tone: "tone-unknown" as const };
    return { label: `${r.systemic_risk?.toFixed(2) ?? "N/A"} systemic`, tone: "tone-unknown" as const };
  })();

  const access = (() => {
    if (!snapshot || !selectedEntityId) return { label: "No data", tone: "tone-unknown" as const };
    const a = snapshot.latest_access_recommendations.find((x) => x.entity_id === selectedEntityId);
    if (!a) return { label: "No recommendation", tone: "tone-unknown" as const };
    return { label: a.action, tone: a.action === "BLOCK" ? "tone-block" as const : a.action === "MONITOR" ? "tone-monitor" as const : "tone-allow" as const };
  })();

  const enforcement = (() => {
    if (!snapshot || !selectedEntityId) return { label: "No committed action", tone: "tone-unknown" as const };
    const d = snapshot.latest_enforcement_decisions.find((x) => x.entity_id === selectedEntityId);
    if (!d) return { label: "None — no committed action", tone: "tone-unknown" as const };
    return { label: d.action, tone: d.action === "BLOCK" ? "tone-block" as const : d.action === "MONITOR" ? "tone-monitor" as const : "tone-allow" as const };
  })();

  const netStatus = agentStatus(snapshot, AGENT_IDS[0]);
  const behStatus = agentStatus(snapshot, AGENT_IDS[1]);
  const threatAgentStatus = agentStatus(snapshot, AGENT_IDS[2]);
  const riskAgentStatus = agentStatus(snapshot, AGENT_IDS[3]);
  const trustAgentStatus = agentStatus(snapshot, AGENT_IDS[4]);

  return (
    <section className="workflow-pipeline" aria-label="Scientific pipeline — five-agent workflow" data-testid="workflow-pipeline">
      <header className="workflow-pipeline__head">
        <span className="eyebrow">Scientific pipeline · read-only · backend authoritative</span>
        <h3>Network & Behaviour → Gateway → Threat → Risk → Trust & Access (PRE_LZTAF) → Enforcement</h3>
        <p className="annotation">Network and Behaviour are scientifically separate inputs; they converge only at the controlled Finding Gateway boundary. Each stage shows backend evidence only — no inferred execution.</p>
      </header>

      <div className="pipeline-grid">
        {/* Row 1: two separate detectors */}
        <div className="pipeline-row pipeline-row--inputs">
          <article className={`pipeline-card ${agentStatusTone(netStatus)}`} data-testid="pipeline-network">
            <span className="pipeline-card__stage">1A · Separate input</span>
            <strong>Network / Anomaly Detector</strong>
            <span className={`pipeline-pill ${agentStatusTone(netStatus)}`}>{hasSnapshot ? netStatus : "No data"}</span>
            <small className="mono">{AGENT_IDS[0]}</small>
          </article>
          <span className="pipeline-join" aria-hidden="true">＋</span>
          <article className={`pipeline-card ${agentStatusTone(behStatus)}`} data-testid="pipeline-behavior">
            <span className="pipeline-card__stage">1B · Separate input</span>
            <strong>IoT Behavioural Profiler</strong>
            <span className={`pipeline-pill ${agentStatusTone(behStatus)}`}>{hasSnapshot ? behStatus : "No data"}</span>
            <small className="mono">{AGENT_IDS[1]}</small>
          </article>
        </div>

        <div className="pipeline-arrow" aria-hidden="true">↓ converge only at Gateway</div>

        {/* Gateway boundary */}
        <div className="pipeline-gateway" data-testid="pipeline-gateway">
          <span className="eyebrow">Controlled boundary</span>
          <strong>Finding Gateway</strong>
          <span className={`pipeline-pill ${gateway.tone}`}>{gateway.label}</span>
          <small className="mono">{gateway.detail}</small>
          <p className="annotation">Raw findings → validated evidence. Accepted vs Rejected with reason, per finding type (NetworkFinding / BehaviorFinding).</p>
        </div>

        <div className="pipeline-arrow" aria-hidden="true">↓</div>

        {/* Downstream */}
        <div className="pipeline-row pipeline-row--downstream">
          <article className={`pipeline-card ${agentStatusTone(threatAgentStatus)}`} data-testid="pipeline-threat">
            <span className="pipeline-card__stage">2 · Threat Intelligence Correlator</span>
            <strong>Threat mapping</strong>
            <span className={`pipeline-pill ${threat.tone}`}>{threat.label}</span>
            <small className="mono">{AGENT_IDS[2]}</small>
            <span className="mono" style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{hasSnapshot ? threatAgentStatus : "No data"}</span>
          </article>
          <span className="pipeline-arrow" aria-hidden="true">→</span>
          <article className={`pipeline-card ${agentStatusTone(riskAgentStatus)}`} data-testid="pipeline-risk">
            <span className="pipeline-card__stage">3 · Risk Propagation Analyst</span>
            <strong>Risk recommendation</strong>
            <span className={`pipeline-pill ${risk.tone}`}>{risk.label}</span>
            <small className="mono">{AGENT_IDS[3]}</small>
            <span className="mono" style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{hasSnapshot ? riskAgentStatus : "No data"}</span>
          </article>
          <span className="pipeline-arrow" aria-hidden="true">→</span>
          <article className={`pipeline-card ${agentStatusTone(trustAgentStatus)}`} data-testid="pipeline-trust">
            <span className="pipeline-card__stage">4 · Trust & Access (PRE_LZTAF)</span>
            <strong>Access recommendation</strong>
            <span className={`pipeline-pill ${access.tone}`}>{access.label}</span>
            <small className="mono">{AGENT_IDS[4]} · PRE_LZTAF_DEVICE_EVIDENCE</small>
            <span className="mono" style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{hasSnapshot ? trustAgentStatus : "No data"}</span>
          </article>
          <span className="pipeline-arrow" aria-hidden="true">→</span>
          <article className={`pipeline-card pipeline-card--enforcement ${enforcement.tone}`} data-testid="pipeline-enforcement">
            <span className="pipeline-card__stage">5 · Enforcement Decision</span>
            <strong>ALLOW / MONITOR / BLOCK</strong>
            <span className={`pipeline-pill is-large ${enforcement.tone}`}>{enforcement.label}</span>
            <small className="mono">physical_enforcement_claimed=false · counterfactual_effect_applied=false</small>
          </article>
        </div>
      </div>

      <p className="annotation" style={{ marginTop: 8 }}>Each pill shows backend state only. Pending / No data means no suitable backend evidence for the selected entity/window.</p>
    </section>
  );
}
