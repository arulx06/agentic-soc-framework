import { useEffect, useRef } from "react";
import type { OrchestrationDecisionV1 } from "../../api/contracts";
import { DigestField } from "./DigestField";
import { authoritativeRoute } from "./decisionResult";

const PARTICIPATION: Array<[keyof OrchestrationDecisionV1, string]> = [
  ["supporting_orchestrators", "Supporting"],
  ["disagreeing_orchestrators", "Disagreeing"],
  ["timed_out_orchestrators", "Timed out"],
  ["delayed_orchestrators", "Delayed after round close"],
  ["omitted_orchestrators", "Omitted messages"],
  ["unavailable_orchestrators", "Operationally unavailable"],
];

export function DecisionDetailPanel({ decision, loading, error, onClose }: { decision: OrchestrationDecisionV1 | null; loading: boolean; error: string | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    return () => previousFocus?.focus();
  }, []);
  const route = decision ? authoritativeRoute(decision) : null;

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="snapshot-drawer orchestration-drawer" role="dialog" aria-modal="true" aria-labelledby="decision-detail-title" onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
        <header className="drawer-heading"><div><span className="eyebrow">Backend terminal decision / authoritative</span><h2 id="decision-detail-title">Decision detail</h2></div><button ref={closeRef} className="icon-button" type="button" onClick={onClose} aria-label="Close decision detail">x</button></header>
        {loading && <div className="compact-empty">Loading decision...</div>}
        {error && <div className="error-banner" role="alert">Decision detail unavailable: {error}</div>}
        {decision && !loading && (
          <>
            <section className="orchestration-terminal" aria-label="Authoritative terminal result">
              <span className="eyebrow">Terminal outcome</span>
              <strong className={`mono ${decision.outcome === "DECIDED" ? "tone-committed" : "tone-failed"}`}>{decision.outcome}</strong>
              <span>Authoritative result</span><b className="mono">{route ?? "No route selected"}</b>
              <p>{decision.reason}</p>
            </section>
            <p className="annotation">The result above is read only from the terminal backend decision. Proposal counts, vote counts, supporter arrays, and QUORUM_REACHED events are never used by this UI to derive a result, support, or quorum.</p>

            <dl className="metadata-list">
              <div><dt>Decision ID</dt><dd className="mono">{decision.decision_id}</dd></div>
              <div><dt>Request</dt><dd className="mono">{decision.request_id} / v{decision.request_version}</dd></div>
              <div><dt>Round</dt><dd className="mono">{decision.round_id}</dd></div>
              <div><dt>Request digest</dt><dd><DigestField value={decision.request_digest} label="request digest" /></dd></div>
              <div><dt>Selected proposal digest</dt><dd><DigestField value={decision.outcome === "DECIDED" ? decision.selected_proposal_digest : null} label="selected proposal digest" /></dd></div>
              <div><dt>Backend quorum fact</dt><dd className="mono">formed={String(decision.quorum_formed)} / required={decision.required_quorum}</dd></div>
              <div><dt>Quorum latency</dt><dd className="mono">{decision.quorum_latency_ms == null ? "N/A" : `${decision.quorum_latency_ms} ms`}</dd></div>
              <div><dt>Decision latency</dt><dd className="mono">{decision.decision_latency_ms} ms</dd></div>
              <div><dt>Logical context</dt><dd className="mono">timestamp={decision.logical_timestamp ?? "None"}; window={decision.window_id ?? "None"}</dd></div>
              <div><dt>Completed</dt><dd className="mono">{decision.completed_at_utc}</dd></div>
            </dl>

            <section className="orchestration-detail-section"><h3>Participation distinctions</h3><div className="participation-grid">{PARTICIPATION.map(([key, label]) => { const values = decision[key] as string[]; return <div key={String(key)}><span>{label}</span><strong className="mono">{values.length ? values.join(", ") : "None listed"}</strong></div>; })}</div></section>

            <section className="orchestration-detail-section"><h3>Exact proposal summaries ({decision.proposal_summaries.length})</h3>{decision.proposal_summaries.length === 0 ? <p className="annotation">No proposal summaries returned.</p> : <div className="bounded-table"><table className="data-table"><thead><tr><th>Orchestrator</th><th>Route proposed</th><th>Auth verified</th><th>Policy / rationale</th><th>Latency</th><th>Proposal digest</th><th>Message hash</th></tr></thead><tbody>{decision.proposal_summaries.map((proposal) => <tr key={proposal.message_id}><td className="mono">{proposal.orchestrator_id}<br /><small>{proposal.message_id}</small></td><td className="mono">{proposal.proposed_route_id}</td><td>{String(proposal.authentication_verified)}</td><td className="mono">{proposal.policy_id}@{proposal.policy_version}<br />{proposal.rationale_code}</td><td className="mono">{proposal.latency_ms} ms</td><td><DigestField value={proposal.proposal_digest} label="proposal digest" /></td><td><DigestField value={proposal.message_hash} label="proposal message hash" /></td></tr>)}</tbody></table></div>}</section>

            <section className="orchestration-detail-section"><h3>Exact vote summaries ({decision.vote_summaries.length})</h3>{decision.vote_summaries.length === 0 ? <p className="annotation">No vote summaries returned.</p> : <div className="bounded-table"><table className="data-table"><thead><tr><th>Orchestrator</th><th>Vote</th><th>Auth verified</th><th>Reason</th><th>Latency</th><th>Selected digest</th><th>Message hash</th></tr></thead><tbody>{decision.vote_summaries.map((vote) => <tr key={vote.message_id}><td className="mono">{vote.orchestrator_id}<br /><small>{vote.message_id}</small></td><td className="mono">{vote.vote}</td><td>{String(vote.authentication_verified)}</td><td className="mono">{vote.reason_code}</td><td className="mono">{vote.latency_ms} ms</td><td><DigestField value={vote.selected_proposal_digest} label="voted proposal digest" /></td><td><DigestField value={vote.message_hash} label="vote message hash" /></td></tr>)}</tbody></table></div>}</section>

            <p className="annotation">The backend <code>proposal_digest</code> represents semantic route support for one request, so separate orchestrators can share it. Each <code>message_hash</code> binds an individual sender message and normally differs. React displays these values exactly as received and does not recompute or verify either hash.</p>

            <section className="orchestration-detail-section"><h3>Backend rejections ({decision.rejections.length})</h3>{decision.rejections.length === 0 ? <p className="annotation">No rejections returned.</p> : <div className="bounded-table"><table className="data-table"><thead><tr><th>Phase</th><th>Reason</th><th>Orchestrator</th><th>Message</th><th>Detail</th></tr></thead><tbody>{decision.rejections.map((rejection, index) => <tr key={`${rejection.message_id ?? "round"}-${index}`}><td>{rejection.phase}</td><td className="mono">{rejection.reason_code}</td><td className="mono">{rejection.orchestrator_id ?? "None"}</td><td className="mono">{rejection.message_id ?? "None"}</td><td>{rejection.detail}</td></tr>)}</tbody></table></div>}</section>

            <details className="technical-details" open><summary>Backend provenance</summary><pre>{JSON.stringify(decision.provenance, null, 2)}</pre></details>
            <p className="annotation banner-warning">A verified internal message authentication tag establishes key possession and message integrity under this runtime's key assumptions. Caller principal is an application/audit identity; its HTTP origin is not proof of honesty.</p>
          </>
        )}
      </aside>
    </div>
  );
}
