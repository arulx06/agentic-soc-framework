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
  Sprite,
  SpriteMaterial,
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
import {
  applyAccentDimming,
  applyNodeVisualState,
} from "./models/modelMaterials";
import type { ModelBounds, NodeModelKind } from "./models/modelTypes";
import {
  LABEL_MARGIN,
  MIN_LABEL_HEIGHT,
  createHaloMesh,
  disposeObjectTree,
  geo,
} from "./models/modelUtils";
import { createNodeModel } from "./models/NodeModelFactory";
import { resolveNodeModelKind } from "./models/nodeModelRegistry";

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
  isRunning?: boolean;
}

interface NodeVisual {
  id: string;
  kind: NodeModelKind;
  group: Group;
  content: Group;
  stateMaterials: MeshBasicMaterial[];
  accentMaterials: MeshBasicMaterial[];
  bounds: ModelBounds;
  halo?: Mesh;
  haloMaterial?: MeshBasicMaterial;
  hitbox?: Mesh;
  hitboxMaterial?: MeshBasicMaterial;
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
  isRunning = false,
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
    isRunning,
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
    isRunning,
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
        // Freeze animation when not RUNNING (PAUSED/COMPLETED etc.)
        if (!interaction.isRunning) return 0;
        const incident =
          !interaction.selectedNodeId || interaction.incidentLinkIds.has(link.id);
        if (!incident) return 0;
        if (
          interaction.kind === "risk" &&
          link.risk?.evidence_type === "STRONGLY_INFERRED"
        )
          return 1;
        if (
          interaction.kind === "communication" &&
          link.communication &&
          (link.communication.packet_count_delta ?? 0) > 0
        ) {
          const delta = link.communication.packet_count_delta ?? 0;
          return Math.min(
            4,
            Math.max(1, Math.floor(Math.log10(delta + 1) * 1.2))
          );
        }
        return 0;
      })
      .linkDirectionalParticleWidth((link: unknown) => {
        if (
          isPresentationLink(link as LinkObject) &&
          (link as PresentationLink).kind === "communication"
        ) {
          const delta = (link as PresentationLink).communication?.packet_count_delta ?? 0;
          // Size subtlely reflects current-window byte volume if available
          const byteDelta = (link as PresentationLink).communication?.captured_byte_delta ?? 0;
          const base = byteDelta > 0 ? Math.log10(byteDelta + 1) * 0.35 + 0.7 : 0.9;
          return Math.min(1.6, Math.max(0.9, base));
        }
        return 0.7;
      })
      .linkDirectionalParticleSpeed((link: unknown) => {
        if (
          isPresentationLink(link as LinkObject) &&
          (link as PresentationLink).kind === "communication"
        ) {
          const delta = (link as PresentationLink).communication?.packet_count_delta ?? 0;
          // Clamped speed encodes intensity, not latency
          return Math.min(0.012, Math.max(0.006, 0.006 + Math.log10(delta + 1) * 0.0015));
        }
        return 0.002;
      })
      .linkDirectionalParticleColor((link: unknown) =>
        isPresentationLink(link as LinkObject) &&
        (link as PresentationLink).kind === "communication"
          ? GRAPH_COLORS.communicationParticle
          : GRAPH_COLORS.inferred
      )
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
    graphRef.current?.refresh();
  }, [isRunning]);

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
  const kind = resolveNodeModelKind(
    node.id,
    node.risk
      ? {
          deviceType: node.risk.device_type,
          role: node.risk.role,
          isAttacker: node.risk.is_attacker,
        }
      : undefined
  );
  const built = createNodeModel(kind);
  const group = new Group();

  const hitboxMaterial = new MeshBasicMaterial({
    colorWrite: false,
    depthWrite: false,
    transparent: true,
    opacity: 0,
  });
  const hitbox = new Mesh(
    geo.sphere(built.bounds.radius, 12, 8),
    hitboxMaterial
  );
  built.content.add(hitbox);

  group.add(built.content);

  let halo: Mesh | undefined;
  let haloMaterial: MeshBasicMaterial | undefined;
  if (node.risk?.is_protected_asset) {
    const haloResult = createHaloMesh(GRAPH_COLORS.protected, built.bounds.radius);
    halo = haloResult.mesh;
    haloMaterial = haloResult.material;
    group.add(halo);
  }

  const { sprite: label, material: labelMaterial, texture: labelTexture } =
    createLabel(node.id);
  group.add(label);
  return {
    id: node.id,
    kind,
    group,
    content: built.content,
    stateMaterials: built.stateMaterials,
    accentMaterials: built.accentMaterials,
    bounds: built.bounds,
    halo,
    haloMaterial,
    hitbox,
    hitboxMaterial,
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
  applyNodeVisualState(visual.stateMaterials, { color, dimmed });
  applyAccentDimming(visual.accentMaterials, dimmed);
  const risk = node.risk?.systemic_risk ?? node.risk?.network_risk ?? 0;
  const scale = (node.risk?.is_attacker ? 6.2 : 5.5) + Math.max(0, risk) * 3.5;
  visual.content.scale.setScalar(scale);
  if (visual.halo && visual.haloMaterial) {
    visual.halo.scale.setScalar(scale);
    visual.haloMaterial.opacity = dimmed ? 0.1 : 0.72;
  }
  visual.label.position.set(
    0,
    Math.max((visual.bounds.top + LABEL_MARGIN) * scale, MIN_LABEL_HEIGHT),
    0
  );
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
  disposeObjectTree(visual.group);
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
    const deltaPackets = link.communication.packet_count_delta ?? 0;
    const deltaBytes = link.communication.captured_byte_delta ?? 0;
    if (deltaPackets === 0 && deltaBytes === 0) return 0.35;
    if (deltaBytes > 0) {
      return Math.min(2.8, Math.max(0.6, Math.log10(deltaBytes + 1) * 0.42));
    }
    // Active edge but no captured bytes observed: small fixed width, no byte estimation
    return 1.0;
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
