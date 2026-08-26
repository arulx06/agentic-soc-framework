import { describe, expect, it } from "vitest";
import type { Mesh } from "three";
import {
  KNOWN_NODE_IDS,
  NODE_MODEL_BY_ID,
  resolveNodeModelKind,
  type NodeModelHints,
} from "../components/graphs/models/nodeModelRegistry";
import { createNodeModel } from "../components/graphs/models/NodeModelFactory";
import { applyAccentDimming, applyNodeVisualState } from "../components/graphs/models/modelMaterials";
import type { BuiltNodeModel, NodeModelKind } from "../components/graphs/models/modelTypes";
import modelTypesSource from "../components/graphs/models/modelTypes.ts?raw";
import modelMaterialsSource from "../components/graphs/models/modelMaterials.ts?raw";
import modelUtilsSource from "../components/graphs/models/modelUtils.ts?raw";
import nodeModelRegistrySource from "../components/graphs/models/nodeModelRegistry.ts?raw";
import nodeModelFactorySource from "../components/graphs/models/NodeModelFactory.ts?raw";
import sensorModelsSource from "../components/graphs/models/SensorModels.ts?raw";
import cameraModelsSource from "../components/graphs/models/CameraModels.ts?raw";
import networkModelsSource from "../components/graphs/models/NetworkModels.ts?raw";
import plugModelsSource from "../components/graphs/models/PlugModels.ts?raw";
import attackerModelsSource from "../components/graphs/models/AttackerModels.ts?raw";

function hints(partial: NodeModelHints): NodeModelHints {
  return partial;
}

describe("node model registry", () => {
  it("contains exactly the 45 known device IDs without duplicates", () => {
    expect(KNOWN_NODE_IDS).toHaveLength(45);
    expect(new Set(KNOWN_NODE_IDS).size).toBe(45);
    const registryIds = Object.keys(NODE_MODEL_BY_ID);
    expect(registryIds).toHaveLength(45);
    expect(new Set(registryIds)).toEqual(new Set(KNOWN_NODE_IDS));
  });

  it("maps the required showcase IDs deterministically", () => {
    expect(resolveNodeModelKind("gas-sensor")).toBe("GasSensorModel");
    expect(resolveNodeModelKind("router")).toBe("RouterModel");
    expect(resolveNodeModelKind("switch")).toBe("NetworkSwitchModel");
    expect(resolveNodeModelKind("yi-camera")).toBe("YiCameraModel");
    expect(resolveNodeModelKind("attacker0")).toBe("Attacker0Model");
    expect(resolveNodeModelKind("attacker5")).toBe("Attacker5Model");
    expect(resolveNodeModelKind("plug-rfid")).toBe("PlugRfidModel");
    expect(resolveNodeModelKind("mqtt-broker")).toBe("MqttBrokerModel");
    expect(resolveNodeModelKind("iot-cloud")).toBe("IotCloudModel");
  });

  it("resolves every known ID away from the generic fallback, repeatedly", () => {
    KNOWN_NODE_IDS.forEach((id) => {
      const first = resolveNodeModelKind(id);
      const second = resolveNodeModelKind(id);
      expect(first).not.toBe("GenericDeviceModel");
      expect(second).toBe(first);
    });
  });

  it("resolves communication nodes that have no risk metadata at all", () => {
    expect(resolveNodeModelKind("attacker0")).toBe("Attacker0Model");
    expect(
      resolveNodeModelKind("gas-sensor", hints({ role: null, deviceType: null }))
    ).toBe("GasSensorModel");
    KNOWN_NODE_IDS.forEach((id) => {
      expect(resolveNodeModelKind(id)).toBe(NODE_MODEL_BY_ID[id]);
    });
  });

  it("is invariant to node array order", () => {
    const forward = KNOWN_NODE_IDS.map(
      (id) => [id, resolveNodeModelKind(id)] as const
    );
    const reversed = [...forward].reverse();
    reversed.forEach(([id]) => {
      const expected = forward.find(([candidateId]) => candidateId === id)![1];
      expect(resolveNodeModelKind(id)).toBe(expected);
    });
  });

  it("does not change model identity when risk values change", () => {
    KNOWN_NODE_IDS.forEach((id) => {
      const baseline = resolveNodeModelKind(id);
      const asAttackerFlagged = resolveNodeModelKind(
        id,
        hints({ isAttacker: true, role: "attacker", deviceType: "evil" })
      );
      const asSensorFlagged = resolveNodeModelKind(
        id,
        hints({ role: "sensor", deviceType: "sensor" })
      );
      expect(asAttackerFlagged).toBe(baseline);
      expect(asSensorFlagged).toBe(baseline);
    });
  });

  it("does not change model identity when packet or byte values change", () => {
    const communicationPresentation = (packets: number, bytes: number) =>
      hints({
        role: null,
        deviceType: null,
        isAttacker: packets > 9000 || bytes > 9000,
      });
    ["gas-sensor", "router", "attacker0", "yi-camera"].forEach((id) => {
      const baseline = resolveNodeModelKind(id);
      expect(resolveNodeModelKind(id, communicationPresentation(0, 0))).toBe(
        baseline
      );
      expect(
        resolveNodeModelKind(id, communicationPresentation(23961, 91))
      ).toBe(baseline);
    });
  });

  it("uses the same model for an ID in both graph modes", () => {
    ["ap", "soil-sensor", "plug-motion", "attacker3"].forEach((id) => {
      const riskMode = resolveNodeModelKind(id);
      const communicationMode = resolveNodeModelKind(id);
      expect(riskMode).toBe(communicationMode);
      expect(riskMode).toBe(NODE_MODEL_BY_ID[id as keyof typeof NODE_MODEL_BY_ID]);
    });
  });

  it("falls back safely for unknown IDs without stealing existing models", () => {
    expect(resolveNodeModelKind("mystery-box")).toBe("GenericDeviceModel");
    expect(
      resolveNodeModelKind("future-cam", hints({ role: "camera" }))
    ).toBe("GenericCameraModel");
    expect(
      resolveNodeModelKind("future-sensor", hints({ deviceType: "sensor" }))
    ).toBe("GenericSensorModel");
    expect(
      resolveNodeModelKind("future-plug", hints({ role: "smart plug" }))
    ).toBe("GenericPlugModel");
    expect(
      resolveNodeModelKind("future-ap", hints({ role: "access point" }))
    ).toBe("GenericNetworkDeviceModel");
    expect(
      resolveNodeModelKind("future-attacker", hints({ isAttacker: true }))
    ).toBe("GenericAttackerModel");
  });
});

describe("model randomness audit", () => {
  it("never selects models via Math.random or array-order modulo", () => {
    const sources = [
      modelTypesSource,
      modelMaterialsSource,
      modelUtilsSource,
      nodeModelRegistrySource,
      nodeModelFactorySource,
      sensorModelsSource,
      cameraModelsSource,
      networkModelsSource,
      plugModelsSource,
      attackerModelsSource,
    ];
    sources.forEach((source) => {
      expect(source).not.toMatch(/Math\.random/);
      expect(source).not.toMatch(/%\s*\w*models\.length/);
    });
  });
});

describe("node model factory", () => {
  const MAX_MESHES_PER_MODEL = 20;

  function buildAndDisposeMaterials(kind: NodeModelKind): BuiltNodeModel {
    const built = createNodeModel(kind);
    built.stateMaterials.forEach((material) => material.dispose());
    built.accentMaterials.forEach((material) => material.dispose());
    return built;
  }

  function structuralSignature(kind: NodeModelKind): string {
    const built = createNodeModel(kind);
    const parts = built.content.children.map((child) => {
      const mesh = child as Mesh;
      return [
        mesh.geometry.type,
        mesh.position.x.toFixed(3),
        mesh.position.y.toFixed(3),
        mesh.position.z.toFixed(3),
        mesh.scale.x.toFixed(2),
        mesh.scale.y.toFixed(2),
        mesh.scale.z.toFixed(2),
      ].join("|");
    });
    parts.sort();
    built.stateMaterials.forEach((material) => material.dispose());
    built.accentMaterials.forEach((material) => material.dispose());
    return `${built.content.children.length}::${parts.join(";")}`;
  }

  it("builds a normalized multi-part group for every known ID and generic kind", () => {
    const kindSet = new Set<NodeModelKind>([
      ...KNOWN_NODE_IDS.map((id) => NODE_MODEL_BY_ID[id]),
      "GenericDeviceModel",
      "GenericSensorModel",
      "GenericCameraModel",
      "GenericPlugModel",
      "GenericNetworkDeviceModel",
      "GenericAttackerModel",
    ]);
    const kinds = [...kindSet];
    expect(kinds.length).toBe(51);
    kinds.forEach((kind) => {
      const built = createNodeModel(kind);
      expect(built.kind).toBe(kind);
      expect(built.content.children.length).toBeGreaterThan(0);
      expect(built.content.children.length).toBeLessThanOrEqual(
        MAX_MESHES_PER_MODEL
      );
      expect(built.stateMaterials.length).toBeGreaterThan(0);
      expect(built.bounds.radius).toBeCloseTo(1, 5);
      expect(built.bounds.top).toBeGreaterThan(0);
      built.stateMaterials.forEach((material) => material.dispose());
      built.accentMaterials.forEach((material) => material.dispose());
    });
  });

  it("gives every model kind a structurally distinct silhouette", () => {
    const signatures = new Map<string, NodeModelKind>();
    KNOWN_NODE_IDS.forEach((id) => {
      const kind = NODE_MODEL_BY_ID[id];
      const signature = structuralSignature(kind);
      const collision = signatures.get(signature);
      expect(collision).toBeUndefined();
      signatures.set(signature, kind);
    });
    [
      "GenericDeviceModel",
      "GenericSensorModel",
      "GenericCameraModel",
      "GenericPlugModel",
      "GenericNetworkDeviceModel",
      "GenericAttackerModel",
    ].forEach((kind) => {
      const signature = structuralSignature(kind as NodeModelKind);
      const collision = signatures.get(signature);
      expect(collision).toBeUndefined();
      signatures.set(signature, kind as NodeModelKind);
    });
    expect(signatures.size).toBe(51);
  });

  it("keeps per-node materials independent so visual state never bleeds", () => {
    const gas = createNodeModel("GasSensorModel");
    const router = createNodeModel("RouterModel");
    const routerColorsBefore = router.stateMaterials.map((m) =>
      m.color.getHexString()
    );
    applyNodeVisualState(gas.stateMaterials, { color: "#ff0000", dimmed: false });
    gas.stateMaterials.forEach((m) => {
      m.opacity = 0.4;
    });
    applyAccentDimming(gas.accentMaterials, true);
    router.stateMaterials.forEach((material, index) => {
      expect(material.color.getHexString()).toBe(routerColorsBefore[index]);
      expect(material.opacity).toBeCloseTo(0.96, 5);
    });
    router.accentMaterials.forEach((material) => {
      expect(material.opacity).toBe(1);
    });
    expect(gas.stateMaterials[0]).not.toBe(router.stateMaterials[0]);
    gas.stateMaterials.forEach((m) => m.dispose());
    gas.accentMaterials.forEach((m) => m.dispose());
    router.stateMaterials.forEach((m) => m.dispose());
    router.accentMaterials.forEach((m) => m.dispose());
  });

  it("reuses shared geometry instances across builds without sharing materials", () => {
    const first = createNodeModel("SoilSensorModel");
    const second = createNodeModel("SoilSensorModel");
    expect(first.content.children.length).toBe(second.content.children.length);
    first.stateMaterials.forEach((material, index) => {
      expect(material).not.toBe(second.stateMaterials[index]);
    });
    const firstGeometry = (first.content.children[0] as Mesh).geometry;
    const secondGeometry = (second.content.children[0] as Mesh).geometry;
    expect(firstGeometry).toBe(secondGeometry);
    first.stateMaterials.forEach((m) => m.dispose());
    first.accentMaterials.forEach((m) => m.dispose());
    second.stateMaterials.forEach((m) => m.dispose());
    second.accentMaterials.forEach((m) => m.dispose());
  });

  it("keeps risk-responsive state surfaces unlit MeshBasicMaterial in every model", () => {
    const kinds: NodeModelKind[] = [
      ...KNOWN_NODE_IDS.map((id) => NODE_MODEL_BY_ID[id]),
      "GenericDeviceModel",
      "GenericSensorModel",
      "GenericCameraModel",
      "GenericPlugModel",
      "GenericNetworkDeviceModel",
      "GenericAttackerModel",
    ];
    kinds.forEach((kind) => {
      const built = createNodeModel(kind);
      expect(built.stateMaterials.length).toBeGreaterThan(0);
      built.stateMaterials.forEach((material) => {
        expect(material.type).toBe("MeshBasicMaterial");
        material.dispose();
      });
      built.accentMaterials.forEach((material) => material.dispose());
    });
  });

  it("keeps the generic fallback an enclosure rather than a bare sphere", () => {
    const generic = buildAndDisposeMaterials("GenericDeviceModel");
    const geometryTypes = generic.content.children.map(
      (child) => (child as Mesh).geometry.type
    );
    const boxCount = geometryTypes.filter(
      (type) => type === "BoxGeometry" || type === "RoundedBoxGeometry"
    ).length;
    expect(boxCount).toBeGreaterThanOrEqual(3);
    expect(generic.stateMaterials.length).toBeGreaterThanOrEqual(1);
  });
});
