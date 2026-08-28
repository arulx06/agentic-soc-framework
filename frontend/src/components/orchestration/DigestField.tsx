import { useState } from "react";

export function DigestField({ value, label = "digest" }: { value: string | null; label?: string }) {
  const [copied, setCopied] = useState(false);

  if (!value) return <span className="mono tone-unknown">None</span>;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };

  return (
    <span className="orchestration-digest mono">
      <span className="orchestration-digest__short" title={value}>{value.slice(0, 12)}...{value.slice(-8)}</span>
      <details onClick={(event) => event.stopPropagation()}>
        <summary aria-label={`Inspect full ${label}`}>Inspect</summary>
        <code>{value}</code>
      </details>
      <button className="button button--ghost orchestration-digest__copy" type="button" onClick={(event) => { event.stopPropagation(); void copy(); }} aria-label={`Copy ${label}: ${value}`}>
        {copied ? "Copied" : "Copy"}
      </button>
    </span>
  );
}
