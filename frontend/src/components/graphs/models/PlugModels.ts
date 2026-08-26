import {
  MODEL_COLORS,
  createOwnedMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type { ModelBuilder } from "./modelTypes";
import { addModelPart, geo } from "./modelUtils";

const HALF_PI = Math.PI / 2;

function buildPlugChassis(ctx: Parameters<ModelBuilder>[0]) {
  addModelPart(ctx, geo.box(0.78, 0.48, 0.56), createStateMaterial(MODEL_COLORS.bodyMid), {
    position: [0, -0.32, 0],
  });
  addModelPart(ctx, geo.box(0.66, 0.05, 0.45), createStateMaterial(MODEL_COLORS.bodyLight), {
    position: [0, -0.055, 0],
  });
  for (const x of [-0.09, 0.09]) {
    addModelPart(
      ctx,
      geo.box(0.05, 0.16, 0.02),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [x, -0.3, 0.29] }
    );
  }
  addModelPart(ctx, geo.box(0.05, 0.05, 0.02), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, -0.44, 0.29],
  });
  addModelPart(ctx, geo.sphere(0.04, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.31, -0.16, 0.29],
  });
  addModelPart(ctx, geo.box(0.26, 0.22, 0.16), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.36, -0.36],
  });
  for (const x of [-0.07, 0.07]) {
    addModelPart(
      ctx,
      geo.box(0.04, 0.12, 0.04),
      createOwnedMaterial(MODEL_COLORS.brass),
      { position: [x, -0.5, -0.4], rotation: [0.5, 0, 0] }
    );
  }
}

export const buildPlugAllCamerasModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.cylinder(0.13, 0.15, 0.05), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [-0.08, -0.005, 0],
  });
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.03), createOwnedMaterial(MODEL_COLORS.lensGlass), {
    position: [-0.08, -0.005, 0.03],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.box(0.26, 0.025, 0.04), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [-0.08, 0.1, 0],
  });
};

export const buildPlugAllRpbModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.box(0.32, 0.045, 0.32), createOwnedMaterial(MODEL_COLORS.pcb), {
    position: [0, -0.01, 0],
  });
  addModelPart(ctx, geo.box(0.15, 0.06, 0.15), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, 0.03, 0],
  });
  for (const z of [-0.12, 0.12]) {
    addModelPart(
      ctx,
      geo.box(0.3, 0.02, 0.03),
      createOwnedMaterial(MODEL_COLORS.brass),
      { position: [0, 0.008, z] }
    );
  }
};

export const buildPlugAllSensorsModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.sphere(0.055, 8, 6), createOwnedMaterial(MODEL_COLORS.teal), {
    position: [0, 0.01, 0],
  });
  addModelPart(ctx, geo.box(0.34, 0.025, 0.025), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.01, 0],
  });
  addModelPart(
    ctx,
    geo.box(0.34, 0.025, 0.025),
    createOwnedMaterial(MODEL_COLORS.steel),
    { position: [0, 0.01, 0], rotation: [0, HALF_PI, 0] }
  );
};

export const buildPlugCamerasDekcoBluramsModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  for (const x of [-0.14, 0.14]) {
    addModelPart(
      ctx,
      geo.cylinder(0.09, 0.11, 0.05),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [x, -0.01, 0] }
    );
    addModelPart(
      ctx,
      geo.cylinder(0.05, 0.05, 0.03),
      createOwnedMaterial(MODEL_COLORS.lensGlass),
      { position: [x, -0.01, 0.03], rotation: [HALF_PI, 0, 0] }
    );
  }
};

export const buildPlugCamerasGeeniModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.box(0.2, 0.12, 0.2), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, 0.01, 0],
  });
  addModelPart(ctx, geo.cylinder(0.05, 0.05, 0.03), createOwnedMaterial(MODEL_COLORS.lensGlass), {
    position: [0, 0.01, 0.115],
    rotation: [HALF_PI, 0, 0],
  });
};

export const buildPlugCamerasYiModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.sphere(0.075, 10, 8), createOwnedMaterial(MODEL_COLORS.white), {
    position: [0, 0.09, 0],
  });
  addModelPart(ctx, geo.cylinder(0.018, 0.018, 0.1), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, -0.01, 0],
  });
  addModelPart(ctx, geo.cylinder(0.06, 0.075, 0.03), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.07, 0],
  });
};

export const buildPlugEdge1Model: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.box(0.26, 0.05, 0.2), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, 0.0, 0],
  });
  addModelPart(ctx, geo.box(0.22, 0.05, 0.17), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.07, 0],
  });
  addModelPart(ctx, geo.sphere(0.03, 6, 6), createOwnedMaterial(MODEL_COLORS.teal), {
    position: [0.08, 0.0, 0.11],
  });
};

export const buildPlugFlameModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.cylinder(0.1, 0.12, 0.03), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.02, 0],
  });
  addModelPart(ctx, geo.cone(0.075, 0.15, 8), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [0, 0.07, 0],
  });
  addModelPart(ctx, geo.cone(0.035, 0.07, 8), createOwnedMaterial(MODEL_COLORS.orange), {
    position: [0, 0.16, 0],
  });
};

export const buildPlugMotionModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.box(0.22, 0.05, 0.18), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.02, 0],
  });
  addModelPart(ctx, geo.hemisphere(0.09, 10, 5), createOwnedMaterial(MODEL_COLORS.white), {
    position: [0, 0.005, 0],
  });
};

export const buildPlugMqttModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.cylinder(0.11, 0.11, 0.09, 6), createOwnedMaterial(MODEL_COLORS.teal), {
    position: [0, 0.01, 0],
  });
  for (const [x, z] of [
    [-0.18, -0.1],
    [0.18, 0.1],
  ]) {
    addModelPart(
      ctx,
      geo.sphere(0.03, 6, 6),
      createOwnedMaterial(MODEL_COLORS.steel),
      { position: [x, 0.01, z] }
    );
  }
};

export const buildPlugProximityModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.torus(0.06, 0.02, 6, 14), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [-0.1, 0.005, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.torus(0.06, 0.02, 6, 14), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0.1, 0.005, 0],
    rotation: [HALF_PI, 0, 0],
  });
};

export const buildPlugRfidModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  for (const [radius, tilt] of [
    [0.09, 0.2],
    [0.15, -0.15],
  ]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.018, 6, 14, Math.PI),
      createOwnedMaterial(MODEL_COLORS.steel),
      { position: [0, 0.02, 0], rotation: [0, 0, tilt] }
    );
  }
};

export const buildPlugVibrationModel: ModelBuilder = (ctx) => {
  buildPlugChassis(ctx);
  addModelPart(ctx, geo.torus(0.08, 0.018, 6, 14), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.005, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.torus(0.14, 0.018, 6, 16), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.005, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.sphere(0.03, 6, 6), createOwnedMaterial(MODEL_COLORS.copper), {
    position: [0, 0.02, 0],
  });
};
