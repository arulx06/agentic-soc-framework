import type {
  PresentationGraphData,
  PresentationLink,
  PresentationNode,
} from "./graphModel";

interface Props {
  data: PresentationGraphData;
  selectedNode: PresentationNode | null;
  selectedLink: PresentationLink | null;
  onClose: () => void;
}

export function GraphInspector({ data, selectedNode, selectedLink, onClose }: Props) {
  if (!selectedNode && !selectedLink) {
    return (
      <aside className="graph-inspector graph-inspector--empty">
        <span className="eyebrow">Inspector</span>
        <h3>Select a node or link</h3>
        <p>Selection details remain textual and use backend fields verbatim.</p>
      </aside>
    );
  }

  return (
    <aside className="graph-inspector" aria-label="Graph detail inspector">
      <div className="inspector-heading">
        <div>
          <span className="eyebrow">Inspector</span>
          <h3>{selectedNode?.id ?? "Communication link"}</h3>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close inspector">
          ×
        </button>
      </div>
      {selectedNode ? (
        selectedNode.risk ? (
          <RiskNodeDetails node={selectedNode} />
        ) : (
          <dl className="metadata-list">
            <Metadata label="Entity" value={selectedNode.id} mono />
            <Metadata
              label="Connected links"
              value={String(
                data.links.filter((link) => {
                  const source =
                    typeof link.source === "string" ? link.source : link.source.id;
                  const target =
                    typeof link.target === "string" ? link.target : link.target.id;
                  return source === selectedNode.id || target === selectedNode.id;
                }).length
              )}
            />
          </dl>
        )
      ) : selectedLink?.communication ? (
        <CommunicationLinkDetails link={selectedLink} />
      ) : (
        <dl className="metadata-list">
          <Metadata label="Source" value={endpoint(selectedLink?.source)} mono />
          <Metadata label="Destination" value={endpoint(selectedLink?.target)} mono />
          <Metadata label="Evidence" value={selectedLink?.risk?.evidence_type ?? "—"} />
          <Metadata label="Relationship" value={selectedLink?.risk?.relationship ?? "—"} />
        </dl>
      )}
    </aside>
  );
}

function RiskNodeDetails({ node }: { node: PresentationNode }) {
  const risk = node.risk;
  if (!risk) return null;
  return (
    <dl className="metadata-list">
      <Metadata label="Entity" value={risk.entity_id} mono />
      <Metadata label="Role" value={risk.role ?? "—"} />
      <Metadata label="Device type" value={risk.device_type ?? "—"} />
      <Metadata label="Network observed" value={yesNo(risk.network_observed)} />
      <Metadata label="Behaviour observed" value={yesNo(risk.behavior_observed)} />
      <Metadata label="Behaviour supported" value={yesNo(risk.behavior_supported)} />
      <Metadata label="Network risk" value={riskValue(risk.network_risk)} mono />
      <Metadata label="Behaviour risk" value={riskValue(risk.behavior_risk)} mono />
      <Metadata label="Propagated risk" value={riskValue(risk.propagated_risk)} mono />
      <Metadata label="Systemic risk" value={riskValue(risk.systemic_risk)} mono />
      <Metadata label="Attacker" value={yesNo(risk.is_attacker)} />
      <Metadata label="Protected asset" value={yesNo(risk.is_protected_asset)} />
    </dl>
  );
}

function CommunicationLinkDetails({ link }: { link: PresentationLink }) {
  const communication = link.communication;
  if (!communication) return null;
  const winPackets = (communication as unknown as { packet_count_delta?: number }).packet_count_delta ?? 0;
  const winBytes = (communication as unknown as { captured_byte_delta?: number }).captured_byte_delta ?? 0;
  const winProtos =
    (communication as unknown as { protocols_in_window?: string[] }).protocols_in_window ?? [];
  return (
    <dl className="metadata-list">
      <Metadata label="Source" value={communication.src_entity_id} mono />
      <Metadata label="Destination" value={communication.dst_entity_id} mono />
      <Metadata label="Current window packets" value={String(winPackets)} mono />
      <Metadata label="Current window bytes" value={String(winBytes)} mono />
      <Metadata label="Current window protocols" value={winProtos.join(", ") || "—"} />
      <Metadata label="Total packets" value={String(communication.packet_count_total)} mono />
      <Metadata label="Total bytes" value={String(communication.captured_byte_total)} mono />
      <Metadata label="Protocols ever" value={communication.protocols_ever.join(", ") || "—"} />
      <Metadata label="First window" value={nullable(communication.first_window_id)} />
      <Metadata label="Last window" value={nullable(communication.last_window_id)} />
      <Metadata label="Broadcast" value={yesNo(communication.broadcast_ever)} />
      <Metadata label="Multicast" value={yesNo(communication.multicast_ever)} />
    </dl>
  );
}

function Metadata({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{value}</dd>
    </div>
  );
}

function endpoint(value: string | PresentationNode | undefined) {
  if (!value) return "—";
  return typeof value === "string" ? value : value.id;
}

function yesNo(value: boolean) {
  return value ? "Yes" : "No";
}

function riskValue(value: number | null) {
  return value === null ? "N/A" : value.toFixed(4);
}

function nullable(value: number | null) {
  return value === null ? "—" : String(value);
}
