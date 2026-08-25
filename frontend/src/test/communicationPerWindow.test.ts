import { describe, expect, it } from "vitest";
import { buildPresentationGraph, updatePresentationValues } from "../components/graphs/graphModel";
import type { CommunicationGraphSnapshotV1 } from "../api/contracts";
import { makeCommGraph } from "./fixtures";

// Helper mirrors ForceGraph3DView particle logic for communication
function particleCountForDelta(delta: number): number {
  if (delta <= 0) return 0;
  return Math.min(4, Math.max(1, Math.floor(Math.log10(delta + 1) * 1.2)));
}
function widthForDelta(deltaBytes: number, deltaPackets: number): number {
  if (deltaPackets === 0 && deltaBytes === 0) return 0.35;
  if (deltaBytes > 0) {
    return Math.min(2.8, Math.max(0.6, Math.log10(deltaBytes + 1) * 0.42));
  }
  return 1.0;
}

function makeCommSnapshotWithDeltas(
  edges: Array<{ src: string; dst: string; total: number; delta: number; bytesDelta?: number; protos?: string[]; window_id?: number }>
): CommunicationGraphSnapshotV1 {
  return {
    schema_version: "graph_snapshot_v1",
    replay_id: "test-replay",
    graph_kind: "communication_graph",
    logical_timestamp: "2025-01-15T21:25:43Z",
    window_id: edges[0]?.window_id ?? 5,
    nodes: Array.from(new Set(edges.flatMap((e) => [e.src, e.dst]))),
    edges: edges.map((e) => ({
      src_entity_id: e.src,
      dst_entity_id: e.dst,
      packet_count_total: e.total,
      captured_byte_total: e.total * 60,
      protocols_ever: ["tcp"],
      first_window_id: 0,
      last_window_id: e.window_id ?? 5,
      first_timestamp_utc: "2025-01-15T21:25:13Z",
      last_timestamp_utc: "2025-01-15T21:25:43Z",
      broadcast_ever: false,
      multicast_ever: false,
      packet_count_delta: e.delta,
      captured_byte_delta: e.bytesDelta ?? 0,
      protocols_in_window: e.protos ?? (e.delta > 0 ? ["tcp"] : []),
    })),
    provenance: {},
  };
}

describe("Communication per-window semantics", () => {
  it("preserves totals while delta reflects current window", () => {
    const snap = makeCommSnapshotWithDeltas([
      { src: "A", dst: "B", total: 3, delta: 3, window_id: 1 },
      { src: "B", dst: "C", total: 2, delta: 2, window_id: 1 },
    ]);
    const data = buildPresentationGraph(snap);
    expect(data.links).toHaveLength(2);
    const ab = data.links.find((l) => l.id.includes("A>B"))!;
    expect(ab.communication?.packet_count_total).toBe(3);
    expect(ab.communication?.packet_count_delta).toBe(3);

    // Window 2: A->B 0, B->C 5
    const snap2 = makeCommSnapshotWithDeltas([
      { src: "A", dst: "B", total: 3, delta: 0, window_id: 2 },
      { src: "B", dst: "C", total: 7, delta: 5, window_id: 2 },
    ]);
    const data2 = buildPresentationGraph(snap2);
    const ab2 = data2.links.find((l) => l.id.includes("A>B"))!;
    const bc2 = data2.links.find((l) => l.id.includes("B>C"))!;
    expect(ab2.communication?.packet_count_total).toBe(3);
    expect(ab2.communication?.packet_count_delta).toBe(0);
    expect(bc2.communication?.packet_count_total).toBe(7);
    expect(bc2.communication?.packet_count_delta).toBe(5);
    expect(bc2.communication?.protocols_in_window).toEqual(["tcp"]);
  });

  it("edge with delta 0 must not animate, edge with delta >0 animates", () => {
    expect(particleCountForDelta(0)).toBe(0);
    expect(particleCountForDelta(3)).toBe(1);
    expect(particleCountForDelta(91)).toBe(2); // log10(92)*1.2 ~2.3 ->2
    expect(particleCountForDelta(23961)).toBe(4); // capped
  });

  it("particle direction follows src -> dst", () => {
    const snap = makeCommSnapshotWithDeltas([{ src: "Laptop", dst: "DNS", total: 91, delta: 91 }]);
    const data = buildPresentationGraph(snap);
    const link = data.links[0];
    expect(link.source).toBe("Laptop");
    expect(link.target).toBe("DNS");
    expect(link.communication?.src_entity_id).toBe("Laptop");
    expect(link.communication?.dst_entity_id).toBe("DNS");
    // Particle would flow src->dst per ForceGraph linkDirectionalParticles
    expect(particleCountForDelta(link.communication?.packet_count_delta ?? 0)).toBeGreaterThan(0);
  });

  it("larger current-window volume produces bounded stronger visualization", () => {
    const p1 = particleCountForDelta(5);
    const p2 = particleCountForDelta(500);
    const p3 = particleCountForDelta(50000);
    expect(p2).toBeGreaterThan(p1);
    expect(p3).toBeGreaterThan(p2);
    expect(p3).toBeLessThanOrEqual(4);
    const w1 = widthForDelta(1000, 10);
    const w2 = widthForDelta(100000, 1000);
    expect(w2).toBeGreaterThan(w1);
    expect(w2).toBeLessThanOrEqual(2.8);
  });

  it("seeking window updates active traffic (snapshot swap)", () => {
    const snap1 = makeCommSnapshotWithDeltas([
      { src: "A", dst: "B", total: 10, delta: 10, window_id: 100 },
    ]);
    const data1 = buildPresentationGraph(snap1);
    expect(data1.links[0].communication?.packet_count_delta).toBe(10);
    expect(data1.links[0].communication?.packet_count_total).toBe(10);

    const snap2 = makeCommSnapshotWithDeltas([
      { src: "A", dst: "B", total: 10, delta: 0, window_id: 101 },
    ]);
    // Simulate update via updatePresentationValues (used when topology same but values change)
    const updated = updatePresentationValues(data1, snap2);
    expect(updated.links[0].communication?.packet_count_delta).toBe(0);
    expect(updated.links[0].communication?.packet_count_total).toBe(10);
    expect(particleCountForDelta(updated.links[0].communication?.packet_count_delta ?? 0)).toBe(0);
  });

  it("updatePresentationValues preserves totals while swapping deltas", () => {
    const snap = makeCommGraph();
    // Original fixture has no delta, default 0
    const data = buildPresentationGraph(snap);
    const deltaSnap = makeCommSnapshotWithDeltas([
      { src: "soil-sensor", dst: "mqtt-broker", total: 100, delta: 91, bytesDelta: 23961 },
    ]);
    // Need matching topology: nodes same, edges same src/dst
    const updated = updatePresentationValues(data, deltaSnap);
    const link = updated.links.find((l) => l.id.includes("soil-sensor>mqtt-broker"));
    expect(link?.communication?.packet_count_total).toBe(100);
    expect(link?.communication?.packet_count_delta).toBe(91);
  });
});
