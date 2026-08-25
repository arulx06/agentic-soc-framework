/** Typed Cytoscape fallback; presentation coordinates never enter backend state. */
import { useEffect, useRef } from "react";
import cytoscape, {
  type ElementDefinition,
  type StylesheetJson,
} from "cytoscape";
import type {
  GraphKind,
  LabelMode,
  PresentationGraphData,
} from "./graphModel";

interface Props {
  data: PresentationGraphData;
  kind: GraphKind;
  topology: string;
  valueSignal: string;
  selectedNodeId: string | null;
  neighbourIds: Set<string>;
  incidentLinkIds: Set<string>;
  labelMode: LabelMode;
  fitSignal: number;
  layoutSignal: number;
  onNodeSelect: (nodeId: string) => void;
  onLinkSelect: (linkId: string) => void;
}

export function GraphCanvas({
  data,
  kind,
  topology,
  valueSignal,
  selectedNodeId,
  neighbourIds,
  incidentLinkIds,
  labelMode,
  fitSignal,
  layoutSignal,
  onNodeSelect,
  onLinkSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const nodeSelectRef = useRef(onNodeSelect);
  const linkSelectRef = useRef(onLinkSelect);
  nodeSelectRef.current = onNodeSelect;
  linkSelectRef.current = onLinkSelect;

  useEffect(() => {
    if (!containerRef.current) return;
    const positions = gridPositions(data.nodes.length, 820, 520);
    let nodeIndex = 0;
    const elements: ElementDefinition[] = [
      ...data.nodes.map((node) => ({
        data: {
          id: node.id,
          label: node.id,
          risk: node.risk?.systemic_risk ?? node.risk?.network_risk ?? 0,
        },
        position: positions[nodeIndex++],
      })),
      ...data.links.map((link) => ({
        data: {
          id: link.id,
          source:
            typeof link.source === "string" ? link.source : link.source.id,
          target:
            typeof link.target === "string" ? link.target : link.target.id,
          packets: link.communication?.packet_count_delta ?? 0,
          bytes: link.communication?.captured_byte_delta ?? 0,
          evidence: link.risk?.evidence_type ?? "",
        },
      })),
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: graphStyles(kind),
      layout: { name: "preset" },
      wheelSensitivity: 0.2,
    });
    cy.on("tap", "node", (event) => nodeSelectRef.current(event.target.id()));
    cy.on("tap", "edge", (event) => linkSelectRef.current(event.target.id()));
    cy.fit(undefined, 36);
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data.links, data.nodes, kind, layoutSignal, topology]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      data.nodes.forEach((node) => {
        const element = cy.getElementById(node.id);
        if (!element.length) return;
        element.data({
          ...element.data(),
          risk: node.risk?.systemic_risk ?? node.risk?.network_risk ?? 0,
        });
      });
      data.links.forEach((link) => {
        const element = cy.getElementById(link.id);
        if (!element.length) return;
        element.data({
          ...element.data(),
          packets: link.communication?.packet_count_delta ?? 0,
          bytes: link.communication?.captured_byte_delta ?? 0,
        });
      });
    });
  }, [data.links, data.nodes, valueSignal]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("is-selected is-neighbour is-dimmed is-incident label-visible");
    data.nodes.forEach((node) => {
      const element = cy.getElementById(node.id);
      if (selectedNodeId === node.id) element.addClass("is-selected");
      else if (selectedNodeId && neighbourIds.has(node.id)) {
        element.addClass("is-neighbour");
      } else if (selectedNodeId) element.addClass("is-dimmed");
      if (labelMode === "all" || (labelMode === "selected" && selectedNodeId === node.id)) {
        element.addClass("label-visible");
      }
    });
    data.links.forEach((link) => {
      const element = cy.getElementById(link.id);
      if (selectedNodeId && incidentLinkIds.has(link.id)) element.addClass("is-incident");
      else if (selectedNodeId) element.addClass("is-dimmed");
    });
  }, [data.links, data.nodes, incidentLinkIds, labelMode, neighbourIds, selectedNodeId]);

  useEffect(() => {
    cyRef.current?.fit(undefined, 36);
  }, [fitSignal]);

  return <div ref={containerRef} className="graph-canvas graph-canvas--2d" />;
}

export function gridPositions(nodeCount: number, width: number, height: number) {
  if (nodeCount === 0) return [];
  const columns = Math.max(
    1,
    Math.ceil(Math.sqrt(nodeCount * (width / Math.max(1, height))))
  );
  const rows = Math.max(1, Math.ceil(nodeCount / columns));
  const cellWidth = width / (columns + 1);
  const cellHeight = height / (rows + 1);
  return Array.from({ length: nodeCount }, (_, index) => ({
    x: cellWidth * ((index % columns) + 1),
    y: cellHeight * (Math.floor(index / columns) + 1),
  }));
}

function graphStyles(kind: GraphKind): StylesheetJson {
  return [
    {
      selector: "node",
      style: {
        label: "",
        width: "mapData(risk, 0, 1, 18, 34)",
        height: "mapData(risk, 0, 1, 18, 34)",
        "background-color": kind === "risk" ? "#4f8ff7" : "#2dd4bf",
        "border-width": 1,
        "border-color": "#93c5fd",
        color: "#dbeafe",
        "font-size": 9,
        "text-background-color": "#0b1220",
        "text-background-opacity": 0.9,
        "text-background-padding": "4px",
      },
    },
    { selector: "node.label-visible", style: { label: "data(label)" } },
    {
      selector: "node.is-selected",
      style: { "border-width": 4, "border-color": "#e2f3ff" },
    },
    {
      selector: "node.is-neighbour",
      style: { "border-width": 3, "border-color": "#67e8f9" },
    },
    { selector: ".is-dimmed", style: { opacity: 0.12 } },
    {
      selector: "edge",
      style: {
        width:
          kind === "communication"
            ? "mapData(packets, 0, 1000, 0.8, 4)"
            : 1,
        "line-color": kind === "risk" ? "#64748b" : "#4b7f7a",
        "target-arrow-shape": "triangle",
        "target-arrow-color": kind === "risk" ? "#64748b" : "#4b7f7a",
        "curve-style": "bezier",
        opacity: kind === "communication" ? 0.28 : 0.5,
      },
    },
    {
      selector: 'edge[packets > 0]',
      style: {
        "line-color": "#2dd4bf",
        "target-arrow-color": "#2dd4bf",
        opacity: 0.9,
        width: "mapData(packets, 1, 1000, 1.2, 4)",
      },
    },
    {
      selector: 'edge[evidence = "STRONGLY_INFERRED"]',
      style: { "line-style": "dashed", opacity: 0.28 },
    },
    {
      selector: "edge.is-incident",
      style: { width: 3, opacity: 0.95, "line-color": "#67e8f9" },
    },
  ];
}
