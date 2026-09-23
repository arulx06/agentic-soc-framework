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
        <div className="table-toolbar">
          <input
            className="control-input table-search"
            placeholder="Search device…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search device"
          />
        </div>
      </header>
      <div className="bounded-table devices-table__wrap">
        <table className="data-table" aria-label="Device state table">
          <thead>
            <tr><th>Entity</th><th>Net obs</th><th>Beh sup</th></tr>
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
                aria-selected={selected === device.entity_id}
                data-entity={device.entity_id}
              >
                <td className="mono entity-cell">
                  <span className="entity-id">{device.entity_id}</span>
                  {(device.is_attacker || device.is_protected_asset) && (
                    <span className="entity-flags" aria-hidden="true">
                      {device.is_attacker && <i className="flag-dot flag-dot--attacker" title="Attacker" />}
                      {device.is_protected_asset && <i className="flag-ring" title="Protected asset" />}
                    </span>
                  )}
                </td>
                <td><span className={`status-chip ${device.network_observed ? "is-yes" : "is-no"}`}>{device.network_observed ? "Yes" : "No"}</span></td>
                <td><span className={`status-chip ${device.behavior_supported ? "is-yes" : "is-no"}`}>{device.behavior_supported ? "Yes" : "No"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length === 0 && <div className="compact-empty">No matching devices.</div>}
      </div>
      {selectedDevice && (
        <aside className="inline-inspector" aria-label="Selected device details">
          <header>
            <div className="inspector-title">
              <strong className="mono">{selectedDevice.entity_id}</strong>
              <span className="inspector-badges">
                {selectedDevice.is_attacker && <span className="badge badge-smoke" style={{ fontSize: "0.60rem" }}>Attacker</span>}
                {selectedDevice.is_protected_asset && <span className="badge badge-device-only" style={{ fontSize: "0.60rem" }}>Protected</span>}
              </span>
            </div>
            <button className="icon-button" onClick={() => setSelected(null)} aria-label="Close device details">×</button>
          </header>
          <dl className="metadata-list metadata-list--columns">
            <Metadata label="Network observed" value={String(selectedDevice.network_observed)} />
            <Metadata label="Behavior observed" value={String(selectedDevice.behavior_observed)} />
            <Metadata label="Behavior supported" value={String(selectedDevice.behavior_supported)} />
            <Metadata label="Propagated risk" value={formatRisk(selectedDevice.propagated_risk, true)} />
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
