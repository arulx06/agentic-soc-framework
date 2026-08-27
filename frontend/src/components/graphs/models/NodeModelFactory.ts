import { Group } from "three";
import type { Mesh, MeshBasicMaterial } from "three";
import {
  MODEL_COLORS,
  createGlossMaterial,
  createOwnedMaterial,
  createRubberMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type {
  BuiltNodeModel,
  ModelBuildContext,
  ModelBuilder,
  ModelBounds,
  NodeModelKind,
} from "./modelTypes";
import { addModelPart, geo, normalizeGroup } from "./modelUtils";
import {
  buildAccelerometerSensorModel,
  buildFlameSensorModel,
  buildGasSensorModel,
  buildLightSensorModel,
  buildMotionSensorModel,
  buildProximityCollisionSensorModel,
  buildRfidSensorModel,
  buildSoilSensorModel,
  buildSoundSensorModel,
  buildSteamSensorModel,
  buildUltrasonicSensorModel,
  buildVibrationSensorModel,
  buildWaterSensorModel,
  buildWeatherSensorModel,
} from "./SensorModels";
import {
  buildBluramsCameraModel,
  buildDekcoCameraModel,
  buildGeeniCameraModel,
  buildMyqCameraModel,
  buildWisenetCameraModel,
  buildYiCameraModel,
} from "./CameraModels";
import {
  buildAccessPointModel,
  buildEdgeNodeModel,
  buildIotCloudModel,
  buildMqttBrokerModel,
  buildNetworkSwitchModel,
  buildRouterModel,
} from "./NetworkModels";
import {
  buildPlugAllCamerasModel,
  buildPlugAllRpbModel,
  buildPlugAllSensorsModel,
  buildPlugCamerasDekcoBluramsModel,
  buildPlugCamerasGeeniModel,
  buildPlugCamerasYiModel,
  buildPlugEdge1Model,
  buildPlugFlameModel,
  buildPlugMotionModel,
  buildPlugMqttModel,
  buildPlugProximityModel,
  buildPlugRfidModel,
  buildPlugVibrationModel,
} from "./PlugModels";
import {
  buildAttacker0Model,
  buildAttacker1Model,
  buildAttacker2Model,
  buildAttacker3Model,
  buildAttacker4Model,
  buildAttacker5Model,
} from "./AttackerModels";

const buildGenericDeviceModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.85, 0.5, 0.62, 0.06),
    createStateMaterial(MODEL_COLORS.bodyMid),
    { position: [0, -0.05, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.73, 0.05, 0.5, 0.02),
    createGlossMaterial(MODEL_COLORS.bodyLight),
    { position: [0, 0.22, 0] }
  );
  addModelPart(ctx, geo.box(0.4, 0.03, 0.03), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [-0.1, -0.1, 0.33],
  });
  addModelPart(ctx, geo.sphere(0.04, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.28, -0.02, 0.32],
  });
  for (const x of [-0.3, 0.3]) {
    addModelPart(
      ctx,
      geo.roundedBox(0.14, 0.06, 0.14, 0.02),
      createRubberMaterial(),
      { position: [x, -0.34, 0] }
    );
  }
};

const buildGenericSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.42, 0.5, 1), createStateMaterial(MODEL_COLORS.green), {
    position: [0, -0.2, 0],
  });
  addModelPart(
    ctx,
    geo.sphere(0.5, 16, 10),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.45, 0], scale: [1, 0.6, 1] }
  );
};

const buildGenericCameraModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(1, 0.8, 0.9), createStateMaterial(MODEL_COLORS.bodyMid), {
    position: [0, 0.05, 0],
  });
  addModelPart(ctx, geo.cylinder(0.26, 0.26, 0.24), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.05, 0.52],
    rotation: [Math.PI / 2, 0, 0],
  });
  addModelPart(ctx, geo.cylinder(0.13, 0.13, 0.08), createOwnedMaterial(MODEL_COLORS.lensGlass), {
    position: [0, 0.05, 0.66],
    rotation: [Math.PI / 2, 0, 0],
  });
};

const buildGenericPlugModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.6, 0.66, 0.4), createStateMaterial(MODEL_COLORS.bodyLight), {
    position: [0, -0.3, 0],
  });
  addModelPart(ctx, geo.box(0.12, 0.38, 0.12), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [-0.18, 0, 0],
  });
  addModelPart(ctx, geo.box(0.12, 0.38, 0.12), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [0.18, 0, 0],
  });
};

const buildGenericNetworkDeviceModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(1.3, 0.5, 0.95), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.2, 0],
  });
  addModelPart(ctx, geo.cylinder(0.05, 0.05, 1.1), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0.45, 0.55, -0.25],
    rotation: [0, 0, -0.24],
  });
};

const buildGenericAttackerModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.octahedron(0.8, 0),
    createStateMaterial(MODEL_COLORS.rose),
    {}
  );
  addModelPart(ctx, geo.tetrahedron(0.28), createOwnedMaterial(MODEL_COLORS.red), {
    position: [0.7, 0.15, 0],
    rotation: [0.6, 0.4, 0.3],
  });
};

const BUILDERS: Record<NodeModelKind, ModelBuilder> = {
  AccelerometerSensorModel: buildAccelerometerSensorModel,
  AccessPointModel: buildAccessPointModel,
  Attacker0Model: buildAttacker0Model,
  Attacker1Model: buildAttacker1Model,
  Attacker2Model: buildAttacker2Model,
  Attacker3Model: buildAttacker3Model,
  Attacker4Model: buildAttacker4Model,
  Attacker5Model: buildAttacker5Model,
  BluramsCameraModel: buildBluramsCameraModel,
  DekcoCameraModel: buildDekcoCameraModel,
  EdgeNodeModel: buildEdgeNodeModel,
  FlameSensorModel: buildFlameSensorModel,
  GasSensorModel: buildGasSensorModel,
  GeeniCameraModel: buildGeeniCameraModel,
  IotCloudModel: buildIotCloudModel,
  LightSensorModel: buildLightSensorModel,
  MotionSensorModel: buildMotionSensorModel,
  MqttBrokerModel: buildMqttBrokerModel,
  MyqCameraModel: buildMyqCameraModel,
  PlugAllCamerasModel: buildPlugAllCamerasModel,
  PlugAllRpbModel: buildPlugAllRpbModel,
  PlugAllSensorsModel: buildPlugAllSensorsModel,
  PlugCamerasDekcoBluramsModel: buildPlugCamerasDekcoBluramsModel,
  PlugCamerasGeeniModel: buildPlugCamerasGeeniModel,
  PlugCamerasYiModel: buildPlugCamerasYiModel,
  PlugEdge1Model: buildPlugEdge1Model,
  PlugFlameModel: buildPlugFlameModel,
  PlugMotionModel: buildPlugMotionModel,
  PlugMqttModel: buildPlugMqttModel,
  PlugProximityModel: buildPlugProximityModel,
  PlugRfidModel: buildPlugRfidModel,
  PlugVibrationModel: buildPlugVibrationModel,
  ProximityCollisionSensorModel: buildProximityCollisionSensorModel,
  RfidSensorModel: buildRfidSensorModel,
  RouterModel: buildRouterModel,
  SoilSensorModel: buildSoilSensorModel,
  SoundSensorModel: buildSoundSensorModel,
  SteamSensorModel: buildSteamSensorModel,
  NetworkSwitchModel: buildNetworkSwitchModel,
  UltrasonicSensorModel: buildUltrasonicSensorModel,
  VibrationSensorModel: buildVibrationSensorModel,
  WaterSensorModel: buildWaterSensorModel,
  WeatherSensorModel: buildWeatherSensorModel,
  WisenetCameraModel: buildWisenetCameraModel,
  YiCameraModel: buildYiCameraModel,
  GenericDeviceModel: buildGenericDeviceModel,
  GenericSensorModel: buildGenericSensorModel,
  GenericCameraModel: buildGenericCameraModel,
  GenericPlugModel: buildGenericPlugModel,
  GenericNetworkDeviceModel: buildGenericNetworkDeviceModel,
  GenericAttackerModel: buildGenericAttackerModel,
};

function collectMaterials(ctx: {
  stateMeshes: Mesh[];
  accentMeshes: Mesh[];
}): {
  stateMaterials: MeshBasicMaterial[];
  accentMaterials: MeshBasicMaterial[];
} {
  const seen = new Set<MeshBasicMaterial>();
  const stateMaterials: MeshBasicMaterial[] = [];
  ctx.stateMeshes.forEach((mesh) => {
    const material = mesh.material as MeshBasicMaterial;
    if (!seen.has(material)) {
      seen.add(material);
      stateMaterials.push(material);
    }
  });
  const accentMaterials: MeshBasicMaterial[] = [];
  ctx.accentMeshes.forEach((mesh) => {
    const material = mesh.material as MeshBasicMaterial;
    if (!seen.has(material)) {
      seen.add(material);
      accentMaterials.push(material);
    }
  });
  return { stateMaterials, accentMaterials };
}

export function createNodeModel(kind: NodeModelKind): BuiltNodeModel & {
  bounds: ModelBounds;
} {
  const builder = BUILDERS[kind];
  if (!builder) throw new Error(`No model builder registered for ${kind}`);
  const content = new Group();
  const ctx: ModelBuildContext = {
    content,
    stateMeshes: [],
    accentMeshes: [],
  };
  builder(ctx);
  if (ctx.stateMeshes.length === 0) {
    throw new Error(`Model ${kind} has no risk-responsive mesh`);
  }
  const bounds = normalizeGroup(content);
  const { stateMaterials, accentMaterials } = collectMaterials(ctx);
  return { kind, content, stateMaterials, accentMaterials, bounds };
}
