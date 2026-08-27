import { useState } from "react";
import { shortenHash } from "../../utils/blackboardHelpers";

export function HashField({ hash, label }: { hash: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const short = shortenHash(hash);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // clipboard may be unavailable in test
    }
  };
  return (
    <span className="hash-field mono" title={hash} aria-label={label ? `${label}: ${hash}` : hash} data-testid="hash-field">
      <span>{short}</span>
      <button className="icon-button icon-button--hash" type="button" onClick={copy} aria-label={`Copy ${label ?? "hash"} ${hash}`} title={copied ? "Copied" : hash}>
        {copied ? "✓" : "⧉"}
      </button>
      <span className="sr-only">{hash}</span>
    </span>
  );
}
