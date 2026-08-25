import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);
vi.stubGlobal("matchMedia", vi.fn(() => ({
  matches: false,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
})));

const graphMethods = {
  backgroundColor: vi.fn(), showNavInfo: vi.fn(), nodeId: vi.fn(),
  nodeThreeObject: vi.fn(), nodeLabel: vi.fn(), onNodeClick: vi.fn(),
  onNodeDragEnd: vi.fn(), onLinkClick: vi.fn(), linkColor: vi.fn(),
  linkWidth: vi.fn(), linkOpacity: vi.fn(), linkDirectionalParticles: vi.fn(),
  linkDirectionalParticleWidth: vi.fn(), linkDirectionalParticleSpeed: vi.fn(),
  linkDirectionalParticleColor: vi.fn(), warmupTicks: vi.fn(), cooldownTicks: vi.fn(),
  cooldownTime: vi.fn(), d3AlphaDecay: vi.fn(), d3VelocityDecay: vi.fn(),
  enableNavigationControls: vi.fn(), enableNodeDrag: vi.fn(), onEngineStop: vi.fn(),
  width: vi.fn(), height: vi.fn(), graphData: vi.fn(), refresh: vi.fn(),
  zoomToFit: vi.fn(), cameraPosition: vi.fn(), d3ReheatSimulation: vi.fn(),
  pauseAnimation: vi.fn(), _destructor: vi.fn(),
};
Object.values(graphMethods).forEach((method) => method.mockReturnValue(graphMethods));

vi.mock("3d-force-graph", () => ({
  default: vi.fn(function ForceGraphMock() { return graphMethods; }),
}));

// Mock Cytoscape to avoid canvas requirement in jsdom
vi.mock("cytoscape", () => ({
  default: vi.fn(() => ({
    on: vi.fn(),
    batch: vi.fn((fn: () => void) => fn()),
    elements: vi.fn(() => ({ removeClass: vi.fn() })),
    getElementById: vi.fn(() => ({
      length: 0,
      data: vi.fn(),
      addClass: vi.fn(),
    })),
    destroy: vi.fn(),
    fit: vi.fn(),
  })),
}));
