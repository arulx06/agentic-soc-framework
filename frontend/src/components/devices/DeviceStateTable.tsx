import { useMemo, useState } from "react";
import type { DeviceStateV1 } from "../../api/contracts";

function formatRisk(value: number | null | undefined, supported: boolean) {
  if (value === null || value === undefined) return supported ? "-" : "N/A / Unsupported";
  return value.toFixed(3);
}

export function DeviceStateTable({ devices }: { devices: DeviceStateV1[] }) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const sorted = useMemo(() => {
    const query = search.trim().toLowerCase();
    return devices
      .filter((device) => !query || device.entity_id.toLowerCase().includes(query))
      .slice()
      .sort((left, right) => left.entity_id.localeCompare(right.entity_id));
  }, [devices, search]);
  const selectedDevice = devices.find((device) => device.entity_id === selected) ?? null;

  return (
    <section className="analysis-card devices-card">
      <header className="card-heading">
        <div>
          <span className="eyebrow">Backend device state</span>
          <h2>Devices <small>{devices.length}</small></h2>
        </div>
        <input
          className="control-input table-search"
          placeholder="Search device…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search device"
        />
      </header>
      <div className="bounded-table">
        <table className="data-table" aria-label="Device state table">
          <thead>
            <tr><th>Entity</th><th>Net obs</th><th>Beh sup</th><th>Beh risk</th><th>Net risk</th><th>Systemic</th></tr>
          </thead>
          <tbody>
            {sorted.map((device) => (
              <tr
                key={device.entity_id}
                className={selected === device.entity_id ? "is-selected" : ""}
                onClick={() => setSelected(device.entity_id)}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") setSelected(device.entity_id);
                }}
              >
                <td className="mono">{device.entity_id}</td>
                <td>{device.network_observed ? "Yes" : "No"}</td>
                <td>{device.behavior_supported ? "Yes" : "No"}</td>
                <td className="mono" data-testid={`beh-risk-${device.entity_id}`}>
                  {formatRisk(device.behavior_risk, device.behavior_supported)}
                </td>
                <td className="mono">{formatRisk(device.network_risk, true)}</td>
                <td className="mono">{formatRisk(device.systemic_risk, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length === 0 && <div className="compact-empty">No matching devices.</div>}
      </div>
      {selectedDevice && (
        <aside className="inline-inspector" aria-label="Selected device details">
          <header>
            <strong className="mono">{selectedDevice.entity_id}</strong>
            <button className="icon-button" onClick={() => setSelected(null)} aria-label="Close device details">×</button>
          </header>
          <dl className="metadata-list metadata-list--columns">
            <Metadata label="Network observed" value={String(selectedDevice.network_observed)} />
            <Metadata label="Behavior observed" value={String(selectedDevice.behavior_observed)} />
            <Metadata label="Behavior supported" value={String(selectedDevice.behavior_supported)} />
            <Metadata label="Behavior risk" value={formatRisk(selectedDevice.behavior_risk, selectedDevice.behavior_supported)} />
            <Metadata label="Propagated risk" value={formatRisk(selectedDevice.propagated_risk, true)} />
            <Metadata label="Systemic risk" value={formatRisk(selectedDevice.systemic_risk, true)} />
            <Metadata label="Attacker" value={String(selectedDevice.is_attacker)} />
            <Metadata label="Protected asset" value={String(selectedDevice.is_protected_asset)} />
          </dl>
        </aside>
      )}
    </section>
  );
}

function Metadata({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd className="mono">{value}</dd></div>;
}
