import type {
  CommunicationEdgeV1,
  CommunicationGraphSnapshotV1,
  DeviceRiskEdgeV1,
  DeviceRiskGraphSnapshotV1,
  DeviceRiskNodeV1,
} from "../../api/contracts";

export type GraphKind = "risk" | "communication";
export type LabelMode = "selected" | "all" | "off";

export interface CommunicationNodeValue {
  entity_id: string;
}

export interface PresentationNode {
  id: string;
  kind: GraphKind;
  risk?: DeviceRiskNodeV1;
  communication?: CommunicationNodeValue;
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
  fx?: number;
  fy?: number;
  fz?: number;
}

export interface PresentationLink {
  id: string;
  source: string | PresentationNode;
  target: string | PresentationNode;
  kind: GraphKind;
  risk?: DeviceRiskEdgeV1;
  communication?: CommunicationEdgeV1;
}

export interface PresentationGraphData {
  nodes: PresentationNode[];
  links: PresentationLink[];
}

export type GraphSnapshot =
  | DeviceRiskGraphSnapshotV1
  | CommunicationGraphSnapshotV1;

export function topologyKey(snapshot: GraphSnapshot | null): string {
  if (!snapshot) return "empty";
  const nodes =
    snapshot.graph_kind === "device_risk_graph"
      ? snapshot.nodes.map((node) => node.entity_id)
      : snapshot.nodes;
  const edges = snapshot.edges.map(
    (edge) => `${edge.src_entity_id}>${edge.dst_entity_id}`
  );
  return `${snapshot.graph_kind}:${[...nodes].sort().join("|")}::${edges
    .sort()
    .join("|")}`;
}

export function buildPresentationGraph(
  snapshot: GraphSnapshot | null,
  previous?: PresentationGraphData
): PresentationGraphData {
  if (!snapshot) return { nodes: [], links: [] };
  const previousNodes = new Map(previous?.nodes.map((node) => [node.id, node]));

  if (snapshot.graph_kind === "device_risk_graph") {
    const nodes = snapshot.nodes.map((risk) =>
      preservePosition(
        { id: risk.entity_id, kind: "risk", risk },
        previousNodes.get(risk.entity_id)
      )
    );
    const links = snapshot.edges.map((risk, index) => ({
      id: `risk:${risk.src_entity_id}>${risk.dst_entity_id}:${index}`,
      source: risk.src_entity_id,
      target: risk.dst_entity_id,
      kind: "risk" as const,
      risk,
    }));
    return { nodes, links };
  }

  const nodes = snapshot.nodes.map((entityId) =>
    preservePosition(
      {
        id: entityId,
        kind: "communication",
        communication: { entity_id: entityId },
      },
      previousNodes.get(entityId)
    )
  );
  const links = snapshot.edges.map((communication, index) => ({
    id: `communication:${communication.src_entity_id}>${communication.dst_entity_id}:${index}`,
    source: communication.src_entity_id,
    target: communication.dst_entity_id,
    kind: "communication" as const,
    communication,
  }));
  return { nodes, links };
}

export function updatePresentationValues(
  current: PresentationGraphData,
  snapshot: GraphSnapshot
): PresentationGraphData {
  if (snapshot.graph_kind === "device_risk_graph") {
    const values = new Map(snapshot.nodes.map((node) => [node.entity_id, node]));
    current.nodes.forEach((node) => {
      node.risk = values.get(node.id);
    });
    const edges = new Map(
      snapshot.edges.map((edge) => [
        `${edge.src_entity_id}>${edge.dst_entity_id}`,
        edge,
      ])
    );
    current.links.forEach((link) => {
      link.risk = edges.get(`${sourceId(link.source)}>${sourceId(link.target)}`);
    });
  } else {
    const edges = new Map(
      snapshot.edges.map((edge) => [
        `${edge.src_entity_id}>${edge.dst_entity_id}`,
        edge,
      ])
    );
    current.links.forEach((link) => {
      link.communication = edges.get(
        `${sourceId(link.source)}>${sourceId(link.target)}`
      );
    });
  }
  return current;
}

export function sourceId(endpoint: string | PresentationNode): string {
  return typeof endpoint === "string" ? endpoint : endpoint.id;
}

export function findNeighbourhood(
  data: PresentationGraphData,
  selectedId: string | null
) {
  const neighbours = new Set<string>();
  const links = new Set<string>();
  if (!selectedId) return { neighbours, links };
  neighbours.add(selectedId);
  data.links.forEach((link) => {
    const source = sourceId(link.source);
    const target = sourceId(link.target);
    if (source === selectedId || target === selectedId) {
      neighbours.add(source);
      neighbours.add(target);
      links.add(link.id);
    }
  });
  return { neighbours, links };
}

export function searchNodes(data: PresentationGraphData, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return [];
  return data.nodes
    .filter((node) => {
      const role = node.risk?.role ?? "";
      const deviceType = node.risk?.device_type ?? "";
      return `${node.id} ${role} ${deviceType}`.toLowerCase().includes(normalized);
    })
    .slice(0, 8);
}

function preservePosition(
  node: PresentationNode,
  previous: PresentationNode | undefined
) {
  if (!previous) return node;
  return {
    ...node,
    x: previous.x,
    y: previous.y,
    z: previous.z,
    vx: previous.vx,
    vy: previous.vy,
    vz: previous.vz,
    fx: previous.fx,
    fy: previous.fy,
    fz: previous.fz,
  };
}
