import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type {
  CommunicationGraphSnapshotV1,
  DeviceRiskGraphSnapshotV1,
} from "../../api/contracts";
import { GraphInspector } from "./GraphInspector";
import {
  buildPresentationGraph,
  findNeighbourhood,
  searchNodes,
  topologyKey,
  updatePresentationValues,
  type GraphKind,
  type GraphSnapshot,
  type LabelMode,
  type PresentationGraphData,
} from "./graphModel";

const ForceGraph3DView = lazy(() =>
  import("./ForceGraph3DView").then((module) => ({
    default: module.ForceGraph3DView,
  }))
);
const GraphCanvas = lazy(() =>
  import("./GraphCanvas").then((module) => ({ default: module.GraphCanvas }))
);

interface Props {
  riskSnapshot: DeviceRiskGraphSnapshotV1 | null;
  communicationSnapshot: CommunicationGraphSnapshotV1 | null;
  initialKind?: GraphKind;
}

export function GraphWorkspace({
  riskSnapshot,
  communicationSnapshot,
  initialKind = "risk",
}: Props) {
  const riskData = useStableGraph(riskSnapshot);
  const communicationData = useStableGraph(communicationSnapshot);
  const [kind, setKind] = useState<GraphKind>(initialKind);
  const [mode, setMode] = useState<"3d" | "2d">("3d");
  const [labelMode, setLabelMode] = useState<LabelMode>("selected");
  const [selectedNodes, setSelectedNodes] = useState<Record<GraphKind, string | null>>({
    risk: null,
    communication: null,
  });
  const [selectedLinks, setSelectedLinks] = useState<Record<GraphKind, string | null>>({
    risk: null,
    communication: null,
  });
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [cameraSignal, setCameraSignal] = useState(0);
  const [layoutSignal, setLayoutSignal] = useState(0);

  const data = kind === "risk" ? riskData.data : communicationData.data;
  const topology = kind === "risk" ? riskData.topology : communicationData.topology;
  const valueSignal = kind === "risk" ? riskData.valueSignal : communicationData.valueSignal;
  const selectedNodeId = selectedNodes[kind];
  const selectedLinkId = selectedLinks[kind];
  const selectedNode =
    data.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedLink =
    data.links.find((link) => link.id === selectedLinkId) ?? null;
  const neighbourhood = useMemo(
    () => findNeighbourhood(data, selectedNodeId),
    [data, selectedNodeId]
  );
  const matches = useMemo(() => searchNodes(data, query), [data, query]);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  useEffect(() => {
    if (selectedNodeId && !data.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodes((current) => ({ ...current, [kind]: null }));
    }
    if (selectedLinkId && !data.links.some((link) => link.id === selectedLinkId)) {
      setSelectedLinks((current) => ({ ...current, [kind]: null }));
    }
  }, [data.links, data.nodes, kind, selectedLinkId, selectedNodeId]);

  function selectNode(nodeId: string) {
    setSelectedNodes((current) => ({ ...current, [kind]: nodeId }));
    setSelectedLinks((current) => ({ ...current, [kind]: null }));
    setQuery("");
  }

  function selectLink(linkId: string) {
    setSelectedLinks((current) => ({ ...current, [kind]: linkId }));
    setSelectedNodes((current) => ({ ...current, [kind]: null }));
  }

  function clearSelection() {
    setSelectedNodes((current) => ({ ...current, [kind]: null }));
    setSelectedLinks((current) => ({ ...current, [kind]: null }));
  }

  return (
    <section className={`graph-workspace${expanded ? " graph-workspace--expanded" : ""}`}>
      <header className="graph-workspace__header">
        <div>
          <span className="eyebrow">Topology workspace</span>
          <h2>{kind === "risk" ? "Device Risk Graph" : "Communication Graph"}</h2>
        </div>
        <div className="graph-stats" aria-label="Graph size">
          <span><strong>{data.nodes.length}</strong> nodes</span>
          <span><strong>{data.links.length}</strong> links</span>
        </div>
      </header>

      <div className="graph-toolbar" aria-label="Graph controls">
        <div className="segmented-control" aria-label="Graph dataset">
          <button
            className={kind === "risk" ? "is-active" : ""}
            onClick={() => setKind("risk")}
            aria-pressed={kind === "risk"}
          >
            Device Risk
          </button>
          <button
            className={kind === "communication" ? "is-active" : ""}
            onClick={() => setKind("communication")}
            aria-pressed={kind === "communication"}
          >
            Communication
          </button>
        </div>
        <div className="segmented-control" aria-label="Graph display mode">
          <button
            className={mode === "3d" ? "is-active" : ""}
            onClick={() => setMode("3d")}
            aria-pressed={mode === "3d"}
          >
            3D
          </button>
          <button
            className={mode === "2d" ? "is-active" : ""}
            onClick={() => setMode("2d")}
            aria-pressed={mode === "2d"}
          >
            2D
          </button>
        </div>
        <div className="graph-search">
          <label className="sr-only" htmlFor="graph-node-search">Search nodes</label>
          <input
            id="graph-node-search"
            className="control-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search node…"
            autoComplete="off"
          />
          {matches.length > 0 && (
            <div className="search-results" role="listbox">
              {matches.map((node) => (
                <button key={node.id} onClick={() => selectNode(node.id)} role="option">
                  <span className="mono">{node.id}</span>
                  {node.risk?.role && <small>{node.risk.role}</small>}
                </button>
              ))}
            </div>
          )}
        </div>
        <label className="compact-select">
          <span>Labels</span>
          <select
            value={labelMode}
            onChange={(event) => {
              const nextMode = event.target.value;
              if (isLabelMode(nextMode)) setLabelMode(nextMode);
            }}
          >
            <option value="selected">Selected</option>
            <option value="all">All</option>
            <option value="off">Off</option>
          </select>
        </label>
        <div className="graph-toolbar__actions">
          <button className="button button--ghost" onClick={() => setCameraSignal((value) => value + 1)}>
            Reset camera
          </button>
          <button className="button button--ghost" onClick={() => setLayoutSignal((value) => value + 1)}>
            Reset layout
          </button>
          <button className="button button--secondary" onClick={() => setExpanded((value) => !value)}>
            {expanded ? "Exit expanded" : "Expand"}
          </button>
        </div>
      </div>

      <div className="graph-workspace__body">
        <div className="graph-stage">
          {data.nodes.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">◎</div>
              <h3>No graph data yet</h3>
              <p>Waiting for the replay runtime.</p>
            </div>
          ) : mode === "3d" ? (
            <Suspense fallback={<div className="compact-empty graph-loading">Loading 3D workspace…</div>}>
              <ForceGraph3DView
                data={data}
                kind={kind}
                topology={topology}
                valueSignal={valueSignal}
                selectedNodeId={selectedNodeId}
                selectedLinkId={selectedLinkId}
                neighbourIds={neighbourhood.neighbours}
                incidentLinkIds={neighbourhood.links}
                labelMode={labelMode}
                cameraSignal={cameraSignal}
                layoutSignal={layoutSignal}
                onNodeSelect={selectNode}
                onLinkSelect={selectLink}
              />
            </Suspense>
          ) : (
            <Suspense fallback={<div className="compact-empty graph-loading">Loading 2D fallback…</div>}>
              <GraphCanvas
                data={data}
                kind={kind}
                topology={topology}
                valueSignal={valueSignal}
                selectedNodeId={selectedNodeId}
                neighbourIds={neighbourhood.neighbours}
                incidentLinkIds={neighbourhood.links}
                labelMode={labelMode}
                fitSignal={cameraSignal}
                layoutSignal={layoutSignal}
                onNodeSelect={selectNode}
                onLinkSelect={selectLink}
              />
            </Suspense>
          )}
          <GraphLegend kind={kind} />
        </div>
        <GraphInspector
          data={data}
          selectedNode={selectedNode}
          selectedLink={selectedLink}
          onClose={clearSelection}
        />
      </div>
    </section>
  );
}

function useStableGraph(snapshot: GraphSnapshot | null) {
  const cache = useRef<{
    topology: string;
    valueSignal: string;
    data: PresentationGraphData;
  }>();
  const nextTopology = topologyKey(snapshot);
  const valueSignal = snapshot
    ? `${snapshot.replay_id}:${snapshot.window_id ?? "none"}:${snapshot.logical_timestamp ?? "none"}`
    : "empty";
  if (!cache.current || cache.current.topology !== nextTopology) {
    cache.current = {
      topology: nextTopology,
      valueSignal,
      data: buildPresentationGraph(snapshot, cache.current?.data),
    };
  } else if (snapshot) {
    updatePresentationValues(cache.current.data, snapshot);
    cache.current.valueSignal = valueSignal;
  }
  return cache.current;
}

function GraphLegend({ kind }: { kind: GraphKind }) {
  return (
    <div className="graph-legend" aria-label="Graph legend">
      {kind === "risk" ? (
        <>
          <span><i className="legend-dot legend-dot--attacker" /> Attacker</span>
          <span><i className="legend-ring" /> Protected asset</span>
          <span><i className="legend-line" /> DOCUMENTED</span>
          <span><i className="legend-line legend-line--faint" /> STRONGLY_INFERRED</span>
        </>
      ) : (
        <>
          <span><i className="legend-line legend-line--communication" /> Backend aggregate</span>
          <span>Line width maps bounded packet count</span>
        </>
      )}
    </div>
  );
}

function isLabelMode(value: string): value is LabelMode {
  return value === "selected" || value === "all" || value === "off";
}
