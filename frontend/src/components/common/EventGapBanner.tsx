/** Gap / truncation banner. */
export function EventGapBanner({ gap, truncated }: { gap: boolean; truncated: boolean }) {
  if (!gap && !truncated) return null;
  const msgs = [];
  if (gap) msgs.push("Event history incomplete — authoritative REST state has been refreshed.");
  if (truncated) msgs.push("Local event history truncated to the configured buffer limit.");
  return (
    <div role="alert">
      {msgs.map((m, i) => (
        <div key={i} className="banner-warning">
          {m}
        </div>
      ))}
    </div>
  );
}
