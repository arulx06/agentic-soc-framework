import {
  MODEL_COLORS,
  createGlossMaterial,
  createMetalMaterial,
  createOwnedMaterial,
  createRubberMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type { ModelBuilder } from "./modelTypes";
import { addModelPart, geo } from "./modelUtils";

const HALF_PI = Math.PI / 2;

export const buildAccessPointModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.82, 0.86, 0.2), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.35, 0],
  });
  addModelPart(ctx, geo.torus(0.83, 0.02, 6, 32), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.35, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cylinder(0.66, 0.74, 0.12), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.5, 0],
  });
  addModelPart(ctx, geo.cylinder(0.72, 0.78, 0.05), createRubberMaterial(), {
    position: [0, -0.58, 0],
  });
  addModelPart(ctx, geo.torus(0.14, 0.03), createGlossMaterial(MODEL_COLORS.teal), {
    position: [0, -0.24, 0],
    rotation: [HALF_PI, 0, 0],
  });
  const leds: Array<[number, string]> = [
    [-0.24, MODEL_COLORS.green],
    [0, MODEL_COLORS.teal],
    [0.24, MODEL_COLORS.amber],
  ];
  leds.forEach(([x, color]) => {
    addModelPart(
      ctx,
      geo.sphere(0.04, 6, 6),
      createOwnedMaterial(color),
      { position: [x, -0.23, 0.34] }
    );
  });
  for (const rotation of [
    [HALF_PI, 0, 0],
    [HALF_PI, 0, HALF_PI],
  ]) {
    addModelPart(
      ctx,
      geo.torus(0.62, 0.028, 6, 20, Math.PI),
      createGlossMaterial(MODEL_COLORS.cloud),
      { position: [0, -0.2, 0], rotation: rotation as [number, number, number] }
    );
  }
};

export const buildRouterModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.5, 0.26, 0.98, 0.05),
    createStateMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.3, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(1.36, 0.06, 0.84, 0.03),
    createStateMaterial(MODEL_COLORS.bodyMid),
    { position: [0, -0.14, 0] }
  );
  addModelPart(ctx, geo.box(1.2, 0.015, 0.02), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, -0.108, 0.2],
  });
  const antennas: Array<[number, number, number]> = [
    [-0.6, 0.25, -0.38],
    [0.6, 0.25, -0.38],
    [0, 0.3, -0.42],
  ];
  antennas.forEach(([x, y, z], index) => {
    addModelPart(
      ctx,
      geo.cylinder(0.06, 0.07, 0.09),
      createMetalMaterial(MODEL_COLORS.bodyDark),
      { position: [x, y - 0.28, z], rotation: index === 2 ? [-0.12, 0, 0] : [0, 0, x < 0 ? 0.3 : -0.3] }
    );
    addModelPart(
      ctx,
      geo.cylinder(0.04, 0.04, 0.8),
      createMetalMaterial(MODEL_COLORS.steel),
      {
        position: [x, y, z],
        rotation: index === 2 ? [-0.12, 0, 0] : [0, 0, x < 0 ? 0.3 : -0.3],
      }
    );
  });
  for (const x of [-0.45, -0.15, 0.15, 0.45]) {
    addModelPart(
      ctx,
      geo.cylinder(0.045, 0.045, 0.03),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [x, -0.115, 0.42] }
    );
    addModelPart(
      ctx,
      geo.sphere(0.028, 6, 6),
      createOwnedMaterial(x > 0.3 ? MODEL_COLORS.amber : MODEL_COLORS.green),
      { position: [x, -0.1, 0.42] }
    );
  }
  for (const x of [-0.4, 0, 0.4]) {
    addModelPart(
      ctx,
      geo.box(0.16, 0.08, 0.04),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [x, -0.32, -0.52] }
    );
  }
};

export const buildNetworkSwitchModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.8, 0.38, 0.88, 0.05),
    createStateMaterial(MODEL_COLORS.bodyMid),
    { position: [0, -0.25, 0] }
  );
  addModelPart(ctx, geo.box(1.7, 0.3, 0.06), createGlossMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.26, 0.44],
  });
  for (let k = 0; k < 6; k += 1) {
    addModelPart(
      ctx,
      geo.box(0.13, 0.11, 0.08),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [-0.65 + k * 0.26, -0.27, 0.46] }
    );
  }
  addModelPart(ctx, geo.box(1.56, 0.025, 0.025), createMetalMaterial(MODEL_COLORS.brass), {
    position: [0, -0.13, 0.46],
  });
  for (const x of [-0.8, -0.68]) {
    addModelPart(
      ctx,
      geo.sphere(0.03, 6, 6),
      createOwnedMaterial(MODEL_COLORS.green),
      { position: [x, -0.05, 0.46] }
    );
  }
  for (const z of [-0.2, 0.2]) {
    addModelPart(
      ctx,
      geo.box(0.03, 0.16, 0.3),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [0.92, -0.25, z] }
    );
  }
  for (const x of [-0.6, 0.6]) {
    addModelPart(
      ctx,
      geo.roundedBox(0.18, 0.06, 0.18, 0.02),
      createRubberMaterial(),
      { position: [x, -0.48, 0] }
    );
  }
};

export const buildMqttBrokerModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.52, 0.52, 0.72, 6), createStateMaterial(MODEL_COLORS.bodyMid), {});
  addModelPart(ctx, geo.cylinder(0.36, 0.36, 0.76, 6), createOwnedMaterial(MODEL_COLORS.bodyDark), {});
  addModelPart(ctx, geo.cylinder(0.26, 0.26, 0.8, 6), createGlossMaterial(MODEL_COLORS.teal), {});
  addModelPart(
    ctx,
    geo.torus(0.38, 0.05, 6, 6),
    createMetalMaterial(MODEL_COLORS.steel),
    { position: [0, 0.44, 0], rotation: [HALF_PI, 0, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.95, 0.14, 0.95, 0.04),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.48, 0] }
  );
  const nodeAngles = [0, HALF_PI, Math.PI, -HALF_PI];
  nodeAngles.forEach((angle, index) => {
    const dirX = Math.cos(angle);
    const dirZ = Math.sin(angle);
    const y = index % 2 === 0 ? -0.02 : 0.18;
    addModelPart(
      ctx,
      geo.cylinder(0.11, 0.13, 0.16, 6),
      createMetalMaterial(MODEL_COLORS.steel),
      {
        position: [dirX * 0.76, y, dirZ * 0.76],
        rotation: dirZ === 0 ? [0, 0, HALF_PI] : [HALF_PI, 0, 0],
      }
    );
    addModelPart(
      ctx,
      geo.cylinder(0.028, 0.028, 0.34),
      createMetalMaterial(MODEL_COLORS.bodyLight),
      {
        position: [dirX * 0.57, y, dirZ * 0.57],
        rotation: dirZ === 0 ? [0, 0, HALF_PI] : [HALF_PI, 0, 0],
      }
    );
  });
};

export const buildEdgeNodeModel: ModelBuilder = (ctx) => {
  const slabColors = [
    MODEL_COLORS.bodyMid,
    MODEL_COLORS.bodyDark,
    MODEL_COLORS.bodyMid,
  ];
  const slabYs = [-0.42, -0.04, 0.34];
  slabYs.forEach((y, index) => {
    addModelPart(
      ctx,
      geo.roundedBox(0.92, 0.28, 0.78, 0.04),
      createStateMaterial(slabColors[index]),
      { position: [0, y, 0] }
    );
    addModelPart(
      ctx,
      geo.box(0.05, 0.14, 0.5),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [0.47, y, 0] }
    );
  });
  addModelPart(ctx, geo.box(0.3, 0.12, 0.05), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [-0.2, -0.42, 0.41],
  });
  addModelPart(ctx, geo.sphere(0.03, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [-0.34, -0.42, 0.42],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.2, 0.2, 0.2, 0.03),
    createGlossMaterial(MODEL_COLORS.teal),
    { position: [0.26, 0.58, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.84, 0.09, 0.7, 0.03),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.61, 0] }
  );
  for (const x of [-0.3, 0.3]) {
    addModelPart(
      ctx,
      geo.roundedBox(0.14, 0.05, 0.14, 0.015),
      createRubberMaterial(),
      { position: [x, -0.68, 0] }
    );
  }
};

export const buildIotCloudModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.icosahedron(0.48, 0), createStateMaterial(MODEL_COLORS.cloud), {
    position: [-0.34, -0.05, 0],
  });
  addModelPart(ctx, geo.icosahedron(0.38, 0), createStateMaterial(MODEL_COLORS.white), {
    position: [0.14, 0.2, 0],
  });
  addModelPart(ctx, geo.icosahedron(0.33, 0), createStateMaterial(MODEL_COLORS.cloud), {
    position: [0.48, -0.12, 0.05],
  });
  addModelPart(ctx, geo.icosahedron(0.26, 0), createStateMaterial(MODEL_COLORS.white), {
    position: [-0.02, 0.44, 0.08],
  });
  addModelPart(ctx, geo.cylinder(0.03, 0.03, 0.5), createMetalMaterial(MODEL_COLORS.bodyLight), {
    position: [-0.1, 0.08, 0.04],
    rotation: [0, 0, 0.9],
  });
  addModelPart(ctx, geo.cylinder(0.025, 0.025, 0.55), createMetalMaterial(MODEL_COLORS.bodyLight), {
    position: [0.3, 0.05, 0.03],
    rotation: [0.25, 0, -1.1],
  });
  addModelPart(ctx, geo.icosahedron(0.17, 1), createGlossMaterial(MODEL_COLORS.teal), {
    position: [0.08, 0.02, 0.22],
  });
};
