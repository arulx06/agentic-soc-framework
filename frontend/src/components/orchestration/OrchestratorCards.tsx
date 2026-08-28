import type { OrchestratorStatusV1 } from "../../api/contracts";

export function OrchestratorCards({ replicas, note }: { replicas: OrchestratorStatusV1[]; note: string | null }) {
  return (
    <section aria-labelledby="orchestrator-cards-title">
      <header className="orchestration-section-heading">
        <div><span className="eyebrow">Operational participants / not Blackboard replicas</span><h2 id="orchestrator-cards-title">Orchestrators</h2></div>
        <span className="count-badge mono">{replicas.length}</span>
      </header>
      {note && <p className="annotation">{note}</p>}
      {replicas.length === 0 ? <div className="analysis-card compact-empty">No orchestrator status returned.</div> : (
        <div className="orchestrator-grid">
          {replicas.map((replica) => {
            const tone = replica.health === "HEALTHY" ? "tone-committed" : replica.health === "UNAVAILABLE" ? "tone-failed" : "tone-partial";
            return (
              <article className="analysis-card orchestrator-card" key={replica.orchestrator_id}>
                <header><strong className="mono">{replica.orchestrator_id}</strong><span className={`status-pill mono ${tone}`}>{replica.health}</span></header>
                <dl className="metadata-list metadata-list--compact">
                  <div><dt>Available</dt><dd>{replica.available ? "Yes" : "No"}</dd></div>
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
      )}
    </section>
  );
}
