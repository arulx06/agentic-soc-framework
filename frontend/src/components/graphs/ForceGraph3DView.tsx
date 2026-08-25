import { useEffect, useRef } from "react";
import ForceGraph3D, {
  type ForceGraph3DInstance,
  type LinkObject,
  type NodeObject,
} from "3d-force-graph";
import {
  CanvasTexture,
  Color,
  Group,
  Mesh,
  MeshBasicMaterial,
  OctahedronGeometry,
  SphereGeometry,
  Sprite,
  SpriteMaterial,
  TorusGeometry,
} from "three";
import { useElementSize } from "../../hooks/useElementSize";
import { GRAPH_COLORS } from "./graphPalette";
import type {
  GraphKind,
  LabelMode,
  PresentationGraphData,
  PresentationLink,
  PresentationNode,
} from "./graphModel";

interface Props {
  data: PresentationGraphData;
  kind: GraphKind;
  topology: string;
  valueSignal: string;
  selectedNodeId: string | null;
  selectedLinkId: string | null;
  neighbourIds: Set<string>;
  incidentLinkIds: Set<string>;
  labelMode: LabelMode;
  cameraSignal: number;
  layoutSignal: number;
  onNodeSelect: (nodeId: string) => void;
  onLinkSelect: (linkId: string) => void;
}

interface NodeVisual {
  group: Group;
  core: Mesh;
  coreMaterial: MeshBasicMaterial;
  halo?: Mesh;
  haloMaterial?: MeshBasicMaterial;
  label: Sprite;
  labelMaterial: SpriteMaterial;
  labelTexture?: CanvasTexture;
}

type GraphInstance = ForceGraph3DInstance;

export function ForceGraph3DView({
  data,
  kind,
  topology,
  valueSignal,
  selectedNodeId,
  selectedLinkId,
  neighbourIds,
  incidentLinkIds,
  labelMode,
  cameraSignal,
  layoutSignal,
  onNodeSelect,
  onLinkSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<GraphInstance | null>(null);
  const visualsRef = useRef(new Map<string, NodeVisual>());
  const topologyRef = useRef(topology);
  const framedTopology = useRef<string | null>(null);
  const previousCameraSignal = useRef(cameraSignal);
  const previousLayoutSignal = useRef(layoutSignal);
  const callbacksRef = useRef({ onNodeSelect, onLinkSelect });
  const interactionRef = useRef({
    kind,
    selectedNodeId,
    neighbourIds,
    incidentLinkIds,
    labelMode,
  });
  const size = useElementSize(containerRef);

  topologyRef.current = topology;
  callbacksRef.current = { onNodeSelect, onLinkSelect };
  interactionRef.current = {
    kind,
    selectedNodeId,
    neighbourIds,
    incidentLinkIds,
    labelMode,
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const graph = new ForceGraph3D(container, {
      controlType: "orbit",
    });
    graph.d3Force("origin", createOriginForce());
    graph
      .backgroundColor(GRAPH_COLORS.background)
      .showNavInfo(false)
      .nodeId("id")
      .nodeThreeObject((node) => {
        if (!isPresentationNode(node)) return new Group();
        let visual = visualsRef.current.get(node.id);
        if (!visual) {
          visual = createVisual(node);
          visualsRef.current.set(node.id, visual);
        }
        const interaction = interactionRef.current;
        updateVisual(
          visual,
          node,
          interaction.selectedNodeId,
          interaction.neighbourIds,
          interaction.labelMode
        );
        return visual.group;
      })
      .nodeLabel((node) =>
        isPresentationNode(node) ? escapeHtml(node.id) : ""
      )
      .onNodeClick((node) => {
        if (isPresentationNode(node)) callbacksRef.current.onNodeSelect(node.id);
      })
      .onNodeDragEnd((node) => {
        if (!isPresentationNode(node)) return;
        node.fx = node.x;
        node.fy = node.y;
        node.fz = node.z;
      })
      .onLinkClick((link) => {
        if (isPresentationLink(link)) callbacksRef.current.onLinkSelect(link.id);
      })
      .linkColor((link) => {
        if (!isPresentationLink(link)) return GRAPH_COLORS.dimmed;
        const interaction = interactionRef.current;
        return linkColor(
          link,
          interaction.selectedNodeId,
          interaction.incidentLinkIds
        );
      })
      .linkWidth((link) => {
        if (!isPresentationLink(link)) return 0.4;
        const interaction = interactionRef.current;
        return linkWidth(
          link,
          interaction.selectedNodeId,
          interaction.incidentLinkIds
        );
      })
      .linkOpacity(1)
      .linkDirectionalParticles((link) => {
        if (!isPresentationLink(link)) return 0;
        const interaction = interactionRef.current;
        return interaction.kind === "risk" &&
          link.risk?.evidence_type === "STRONGLY_INFERRED" &&
          (!interaction.selectedNodeId || interaction.incidentLinkIds.has(link.id))
          ? 1
          : 0;
      })
      .linkDirectionalParticleWidth(0.7)
      .linkDirectionalParticleSpeed(0.002)
      .linkDirectionalParticleColor(() => GRAPH_COLORS.inferred)
      .warmupTicks(30)
      .cooldownTicks(140)
      .cooldownTime(6000)
      .d3AlphaDecay(0.035)
      .d3VelocityDecay(0.32)
      .enableNavigationControls(true)
      .enableNodeDrag(true)
      .onEngineStop(() => {
        if (framedTopology.current === topologyRef.current) return;
        framedTopology.current = topologyRef.current;
        graph.zoomToFit(prefersReducedMotion() ? 0 : 600, 55);
      });
    graphRef.current = graph;

    return () => {
      graph.pauseAnimation();
      graph._destructor();
      graphRef.current = null;
      visualsRef.current.forEach(disposeVisual);
      visualsRef.current.clear();
      container.replaceChildren();
    };
  }, []);

  useEffect(() => {
    graphRef.current?.width(size.width).height(size.height);
  }, [size.height, size.width]);

  useEffect(() => {
    const validIds = new Set(data.nodes.map((node) => node.id));
    visualsRef.current.forEach((visual, id) => {
      if (!validIds.has(id)) {
        disposeVisual(visual);
        visualsRef.current.delete(id);
      }
    });
    framedTopology.current = null;
    graphRef.current?.graphData(data);
  }, [data, topology]);

  useEffect(() => {
    visualsRef.current.forEach((visual, id) => {
      const node = data.nodes.find((candidate) => candidate.id === id);
      if (node) {
        updateVisual(
          visual,
          node,
          selectedNodeId,
          neighbourIds,
          labelMode
        );
      }
    });
    graphRef.current?.refresh();
  }, [data.nodes, labelMode, neighbourIds, selectedNodeId, valueSignal]);

  useEffect(() => {
    if (!selectedNodeId) return;
    const node = data.nodes.find((candidate) => candidate.id === selectedNodeId);
    if (!node || node.x === undefined || node.y === undefined || node.z === undefined) {
      return;
    }
    const distance = 190;
    const magnitude = Math.hypot(node.x, node.y, node.z) || 1;
    graphRef.current?.cameraPosition(
      {
        x: node.x + (node.x / magnitude) * distance,
        y: node.y + (node.y / magnitude) * distance,
        z: node.z + (node.z / magnitude) * distance,
      },
      { x: node.x, y: node.y, z: node.z },
      prefersReducedMotion() ? 0 : 650
    );
  }, [data.nodes, selectedNodeId]);

  useEffect(() => {
    if (previousCameraSignal.current === cameraSignal) return;
    previousCameraSignal.current = cameraSignal;
    graphRef.current?.zoomToFit(prefersReducedMotion() ? 0 : 450, 50);
  }, [cameraSignal]);

  useEffect(() => {
    if (previousLayoutSignal.current === layoutSignal) return;
    previousLayoutSignal.current = layoutSignal;
    data.nodes.forEach((node) => {
      node.fx = undefined;
      node.fy = undefined;
      node.fz = undefined;
    });
    framedTopology.current = null;
    graphRef.current?.d3ReheatSimulation();
  }, [data.nodes, layoutSignal]);

  return (
    <div className="graph-canvas graph-canvas--3d">
      <div ref={containerRef} className="graph-render-surface" />
      {selectedNodeId && (
        <div className="graph-selection-label" aria-live="polite">
          {selectedNodeId}
        </div>
      )}
      {selectedLinkId && (
        <div className="graph-selection-label graph-selection-label--link">
          Link selected
        </div>
      )}
    </div>
  );
}

function createVisual(node: PresentationNode): NodeVisual {
  const group = new Group();
  const coreMaterial = new MeshBasicMaterial({
    color: GRAPH_COLORS.normal,
    transparent: true,
  });
  const geometry = node.risk?.is_attacker
    ? new OctahedronGeometry(1.25, 0)
    : new SphereGeometry(1, 18, 14);
  const core = new Mesh(geometry, coreMaterial);
  group.add(core);

  let halo: Mesh | undefined;
  let haloMaterial: MeshBasicMaterial | undefined;
  if (node.risk?.is_protected_asset) {
    haloMaterial = new MeshBasicMaterial({
      color: GRAPH_COLORS.protected,
      transparent: true,
      opacity: 0.7,
    });
    halo = new Mesh(new TorusGeometry(1.75, 0.08, 8, 28), haloMaterial);
    halo.rotation.x = Math.PI / 2;
    group.add(halo);
  }

  const { sprite: label, material: labelMaterial, texture: labelTexture } =
    createLabel(node.id);
  label.position.set(0, 3.2, 0);
  group.add(label);
  return {
    group,
    core,
    coreMaterial,
    halo,
    haloMaterial,
    label,
    labelMaterial,
    labelTexture,
  };
}

function updateVisual(
  visual: NodeVisual,
  node: PresentationNode,
  selectedNodeId: string | null,
  neighbourIds: Set<string>,
  labelMode: LabelMode
) {
  const selected = selectedNodeId === node.id;
  const neighbour = neighbourIds.has(node.id);
  const dimmed = Boolean(selectedNodeId) && !neighbour;
  const color = selected
    ? GRAPH_COLORS.selected
    : neighbour && selectedNodeId
      ? GRAPH_COLORS.neighbour
      : node.risk?.is_attacker
        ? GRAPH_COLORS.attacker
        : riskColor(node.risk?.systemic_risk ?? node.risk?.network_risk ?? null);
  visual.coreMaterial.color.set(color);
  visual.coreMaterial.opacity = dimmed ? 0.16 : 0.96;
  if (visual.haloMaterial) visual.haloMaterial.opacity = dimmed ? 0.1 : 0.72;
  const risk = node.risk?.systemic_risk ?? node.risk?.network_risk ?? 0;
  const scale = (node.risk?.is_attacker ? 6.2 : 5.5) + Math.max(0, risk) * 3.5;
  visual.core.scale.setScalar(scale);
  visual.halo?.scale.setScalar(scale / 1.5);
  visual.label.visible =
    labelMode === "all" || (labelMode === "selected" && selected);
  visual.labelMaterial.opacity = dimmed ? 0.15 : 0.95;
}

function createLabel(text: string) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 96;
  const context = canvas.getContext("2d");
  let texture: CanvasTexture | undefined;
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.font = "600 34px system-ui";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = GRAPH_COLORS.text;
    context.fillText(truncate(text, 28), canvas.width / 2, canvas.height / 2);
    texture = new CanvasTexture(canvas);
  }
  const material = new SpriteMaterial({ map: texture, transparent: true });
  const sprite = new Sprite(material);
  sprite.scale.set(24, 4.5, 1);
  return { sprite, material, texture };
}

function disposeVisual(visual: NodeVisual) {
  visual.core.geometry.dispose();
  visual.coreMaterial.dispose();
  visual.halo?.geometry.dispose();
  visual.haloMaterial?.dispose();
  visual.labelTexture?.dispose();
  visual.labelMaterial.dispose();
  visual.group.clear();
}

function linkColor(
  link: PresentationLink,
  selectedNodeId: string | null,
  incidentLinkIds: Set<string>
) {
  if (selectedNodeId && !incidentLinkIds.has(link.id)) return GRAPH_COLORS.dimmed;
  if (link.kind === "communication") return GRAPH_COLORS.communication;
  return link.risk?.evidence_type === "DOCUMENTED"
    ? GRAPH_COLORS.documented
    : GRAPH_COLORS.inferred;
}

function linkWidth(
  link: PresentationLink,
  selectedNodeId: string | null,
  incidentLinkIds: Set<string>
) {
  if (selectedNodeId && incidentLinkIds.has(link.id)) return 2.4;
  if (link.communication) {
    return Math.min(
      2.2,
      Math.max(
        0.25,
        Math.log10(link.communication.packet_count_total + 1) * 0.48
      )
    );
  }
  return link.risk?.evidence_type === "DOCUMENTED" ? 1.1 : 0.42;
}

function riskColor(value: number | null) {
  if (value === null) return GRAPH_COLORS.normal;
  const bounded = Math.min(1, Math.max(0, value));
  return new Color(GRAPH_COLORS.lowRisk)
    .lerp(new Color(GRAPH_COLORS.highRisk), bounded)
    .getStyle();
}

function truncate(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    };
    return entities[character];
  });
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function isPresentationNode(node: NodeObject): node is PresentationNode {
  return (
    typeof node.id === "string" &&
    "kind" in node &&
    (node.kind === "risk" || node.kind === "communication")
  );
}

function isPresentationLink(link: LinkObject): link is PresentationLink {
  return (
    "id" in link &&
    typeof link.id === "string" &&
    "kind" in link &&
    (link.kind === "risk" || link.kind === "communication")
  );
}

function createOriginForce() {
  let nodes: NodeObject[] = [];
  const force = (alpha: number) => {
    nodes.forEach((node) => {
      node.vx = (node.vx ?? 0) - (node.x ?? 0) * 0.012 * alpha;
      node.vy = (node.vy ?? 0) - (node.y ?? 0) * 0.012 * alpha;
      node.vz = (node.vz ?? 0) - (node.z ?? 0) * 0.012 * alpha;
    });
  };
  force.initialize = (nextNodes: NodeObject[]) => {
    nodes = nextNodes;
  };
  return force;
}
