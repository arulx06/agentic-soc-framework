import type { OrchestratorStatusV1 } from "../../api/contracts";

export function OrchestratorCards({ replicas, note }: { replicas: OrchestratorStatusV1[]; note: string | null }) {
  return (
    <section className="orchestrator-participants" aria-labelledby="orchestrator-cards-title">
      <header className="orchestration-section-heading">
        <div><span className="eyebrow">One adjudication process · three participants · 2-of-3 backend</span><h2 id="orchestrator-cards-title">Orchestrators</h2></div>
        <span className="count-badge mono">{replicas.length}</span>
      </header>
      {note && <p className="annotation">{note}</p>}
      {replicas.length === 0 ? <div className="analysis-card compact-empty">No orchestrator status returned.</div> : (
        <div className="orchestrator-group" aria-label="Three participants forming one quorum adjudication">
          <div className="orchestrator-group__rail" aria-hidden="true"><span /></div>
          <div className="orchestrator-grid">
            {replicas.map((replica) => {
              const tone = replica.health === "HEALTHY" ? "tone-committed" : replica.health === "UNAVAILABLE" ? "tone-failed" : "tone-partial";
              const title = replica.orchestrator_id.replace("orchestrator_", "Orchestrator ").toUpperCase();
              return (
                <article className={`analysis-card orchestrator-card orchestrator-card--${replica.health.toLowerCase()}`} key={replica.orchestrator_id}>
                  <header>
                    <div className="orchestrator-card__identity">
                      <span className="orchestrator-avatar" aria-hidden="true">{replica.orchestrator_id.slice(-1).toUpperCase()}</span>
                      <div>
                        <strong className="mono">{replica.orchestrator_id}</strong>
                        <small className="mono" style={{ display: "block", color: "var(--text-muted)" }}>{title} · participant</small>
                      </div>
                    </div>
                    <span className={`status-pill mono ${tone}`} style={{ borderRadius: "var(--radius-pill)", padding: "4px 8px" }}>{replica.health}</span>
                  </header>
                  <dl className="metadata-list metadata-list--compact">
                    <div><dt>Available</dt><dd className={replica.available ? "tone-committed" : "tone-failed"}>{replica.available ? "Yes" : "No"}</dd></div>
                    <div><dt>Proposals emitted</dt><dd className="mono">{replica.messages_proposed}</dd></div>
                    <div><dt>Votes issued</dt><dd className="mono">{replica.votes_issued}</dd></div>
                    <div><dt>Auth failures observed</dt><dd className="mono">{replica.authentication_failures_observed}</dd></div>
                    <div><dt>Timeouts / omissions</dt><dd className="mono">{replica.timeouts} / {replica.omissions}</dd></div>
                    <div><dt>Last error</dt><dd className="mono">{replica.last_error ?? "None"}</dd></div>
                  </dl>
                  <details className="technical-details">
                    <summary>Recent backend outcomes ({replica.recent_outcomes.length} / {replica.recent_outcomes_limit})</summary>
                    <pre>{JSON.stringify(replica.recent_outcomes, null, 2)}</pre>
                  </details>
                </article>
              );
            })}
          </div>
          <div className="orchestrator-group__footer" aria-hidden="true">
            <span className="orchestrator-flow__arrow">↓</span>
            <span className="mono" style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>converge via backend quorum check (2-of-3)</span>
          </div>
        </div>
      )}
    </section>
  );
}
