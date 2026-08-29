/**
 * ConfirmedFeedbackForm — explicit confirmed feedback against real Stage-8 endpoint.
 * Requires existing authoritative committed action; explicit checkbox; principal audit identity.
 */
import { useState } from "react";
import type { EnforcementDecisionV1 } from "../../api/contracts";

export function ConfirmedFeedbackForm({
  selectedAction,
  onSubmit,
  status,
  error,
  result,
  onClear,
}: {
  selectedAction: EnforcementDecisionV1 | null;
  onSubmit: (params: {
    window_id: number;
    entity_id: string;
    related_action_id: string;
    feedback_source: string;
    verdict: string;
    reason_code: string;
    note?: string | null;
    principal: string;
  }) => Promise<unknown>;
  status: "idle" | "submitting" | "success" | "error";
  error: string | null;
  result: { feedback_id: string } | null;
  onClear: () => void;
}) {
  const [feedbackSource, setFeedbackSource] = useState("OPERATOR_CONFIRMED");
  const [verdict, setVerdict] = useState("correct");
  const [reasonCode, setReasonCode] = useState("operator_review");
  const [note, setNote] = useState("");
  const [principal, setPrincipal] = useState("operator-a");
  const [confirmed, setConfirmed] = useState(false);

  const isReady =
    selectedAction !== null &&
    !!feedbackSource.trim() &&
    !!verdict.trim() &&
    !!reasonCode.trim() &&
    !!principal.trim() &&
    confirmed;

  const handleSubmit = async () => {
    if (!selectedAction) return;
    await onSubmit({
      window_id: selectedAction.window_id,
      entity_id: selectedAction.entity_id,
      related_action_id: selectedAction.decision_id,
      feedback_source: feedbackSource,
      verdict,
      reason_code: reasonCode,
      note: note || null,
      principal: principal.trim(),
    });
  };

  if (!selectedAction) {
    return (
      <div className="compact-empty" data-testid="feedback-no-action">
        Select a committed EnforcementDecision above to submit confirmed feedback. Feedback is a new record and never rewrites the original action.
      </div>
    );
  }

  return (
    <section className="feedback-form" aria-label="Confirmed feedback" data-testid="confirmed-feedback-form" style={{ border: "1px solid var(--border-subtle)", padding: 12, borderRadius: 6, marginTop: 8 }}>
      <h4>Confirmed feedback — explicit confirmation required</h4>
      <p className="annotation">
        Feedback must be associated with an existing authoritative committed action. The backend requires explicit <span className="mono">confirmed=true</span> and rejects{" "}
        <span className="mono">DATASENSE_GROUND_TRUTH</span>. Principal is an audit/development identity, not a verified Zero Trust credential.
      </p>

      <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
        <div className="summary-item">
          <span>Related action</span>
          <strong className="mono" data-testid="feedback-related-action">{selectedAction.decision_id}</strong> — entity{" "}
          <span className="mono">{selectedAction.entity_id}</span> window <span className="mono">{selectedAction.window_id}</span> action{" "}
          <span className="mono">{selectedAction.action}</span>
        </div>

        <label>
          Feedback source
          <select
            aria-label="Feedback source"
            data-testid="feedback-source"
            value={feedbackSource}
            onChange={(e) => setFeedbackSource(e.target.value)}
            style={{ marginLeft: 8 }}
          >
            <option value="OPERATOR_CONFIRMED">OPERATOR_CONFIRMED</option>
            <option value="EXTERNAL_CONFIRMED">EXTERNAL_CONFIRMED</option>
            <option value="analyst_review">analyst_review</option>
          </select>
        </label>

        <label>
          Verdict
          <select aria-label="Verdict" data-testid="feedback-verdict" value={verdict} onChange={(e) => setVerdict(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="correct">correct</option>
            <option value="incorrect">incorrect</option>
            <option value="confirmed">confirmed</option>
            <option value="needs_review">needs_review</option>
          </select>
        </label>

        <label>
          Reason code
          <input
            aria-label="Reason code"
            data-testid="feedback-reason"
            value={reasonCode}
            onChange={(e) => setReasonCode(e.target.value)}
            style={{ marginLeft: 8 }}
            maxLength={64}
          />
        </label>

        <label>
          Note (optional)
          <input
            aria-label="Note"
            data-testid="feedback-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            style={{ marginLeft: 8 }}
            maxLength={512}
            placeholder="optional note"
          />
        </label>

        <label>
          Feedback principal / audit identity
          <input
            aria-label="Feedback principal"
            data-testid="feedback-principal"
            value={principal}
            onChange={(e) => setPrincipal(e.target.value)}
            style={{ marginLeft: 8 }}
            placeholder="operator-a"
          />
          <span className="annotation" style={{ marginLeft: 8 }}>audit identity — not an authenticated identity</span>
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            aria-label="I confirm this verdict"
            data-testid="feedback-confirmed"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          I confirm this verdict
        </label>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            data-testid="feedback-submit"
            disabled={!isReady || status === "submitting"}
            onClick={handleSubmit}
            aria-disabled={!isReady || status === "submitting"}
          >
            {status === "submitting" ? "Submitting…" : "Submit confirmed feedback"}
          </button>
          <button onClick={onClear} data-testid="feedback-clear">Clear</button>
        </div>

        {status === "success" && result && (
          <div className="banner-success" role="status" data-testid="feedback-success">
            Feedback committed — backend-confirmed feedback ID: <span className="mono">{result.feedback_id}</span>. EnforcementDecision is not mutated; feedback is a new record. Optionally reflects <span className="mono">CONFIRMED_FEEDBACK_RECORDED</span>.
          </div>
        )}
        {status === "error" && error && (
          <div className="error-banner" role="alert" data-testid="feedback-error">
            Feedback rejected: {error} — no optimistic success; original action unchanged.
          </div>
        )}
        {status === "submitting" && <div className="compact-empty" data-testid="feedback-submitting">Submitting feedback…</div>}
      </div>

      <p className="annotation" style={{ marginTop: 8 }}>
        Handle backend rejection: <span className="mono">confirmed=false</span>, unknown action, incorrect replay/window/entity, ground-truth contamination, Blackboard commit failure.
      </p>
    </section>
  );
}
