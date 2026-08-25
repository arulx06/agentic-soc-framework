import { describe, expect, it } from "vitest";
import {
  buildPresentationGraph,
  findNeighbourhood,
  searchNodes,
  topologyKey,
  updatePresentationValues,
} from "../components/graphs/graphModel";
import { makeCommGraph, makeRiskGraph } from "./fixtures";

describe("graph presentation model", () => {
  it("keeps coordinates while backend values change without topology changes", () => {
    const first = makeRiskGraph();
    const data = buildPresentationGraph(first);
    data.nodes[0].x = 42;
    data.nodes[0].y = -7;
    const second = makeRiskGraph();
    second.window_id = 1;
    second.nodes[0].systemic_risk = 0.91;

    expect(topologyKey(second)).toBe(topologyKey(first));
    const updated = updatePresentationValues(data, second);
    expect(updated).toBe(data);
    expect(updated.nodes[0].x).toBe(42);
    expect(updated.nodes[0].y).toBe(-7);
    expect(updated.nodes[0].risk?.systemic_risk).toBe(0.91);
  });

  it("identifies only the selected node neighbourhood and incident links", () => {
    const data = buildPresentationGraph(makeRiskGraph());
    const result = findNeighbourhood(data, "soil-sensor");
    expect(result.neighbours).toEqual(
      new Set(["soil-sensor", "mqtt-broker", "ap"])
    );
    expect(result.links.size).toBe(2);
  });

  it("searches backend IDs and metadata without changing graph data", () => {
    const data = buildPresentationGraph(makeRiskGraph());
    expect(searchNodes(data, "mqtt").map((node) => node.id)).toEqual([
      "mqtt-broker",
    ]);
    expect(searchNodes(data, "sensor").map((node) => node.id)).toContain(
      "soil-sensor"
    );
  });

  it("keeps risk and communication topology namespaces separate", () => {
    expect(topologyKey(makeRiskGraph())).not.toBe(topologyKey(makeCommGraph()));
  });
});
