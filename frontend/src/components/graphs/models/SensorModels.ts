import {
  MODEL_COLORS,
  createGlassMaterial,
  createGlossMaterial,
  createMetalMaterial,
  createOwnedMaterial,
  createRubberMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type { ModelBuilder } from "./modelTypes";
import { addModelPart, geo } from "./modelUtils";

const HALF_PI = Math.PI / 2;

export const buildAccelerometerSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.15, 0.12, 0.9, 0.03),
    createStateMaterial(MODEL_COLORS.pcb),
    { position: [0, -0.25, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.42, 0.16, 0.42, 0.02),
    createStateMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.11, 0] }
  );
  addModelPart(ctx, geo.box(0.18, 0.02, 0.18), createGlossMaterial(MODEL_COLORS.steel), {
    position: [0, -0.02, 0],
  });
  addModelPart(ctx, geo.box(0.09, 0.04, 0.05), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [-0.28, -0.16, 0.24],
  });
  addModelPart(ctx, geo.box(0.09, 0.04, 0.05), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [0.27, -0.16, -0.25],
  });
  addModelPart(ctx, geo.box(0.5, 0.05, 0.05), createOwnedMaterial(MODEL_COLORS.copper), {
    position: [0.45, -0.08, 0],
  });
  addModelPart(ctx, geo.box(0.05, 0.05, 0.5), createOwnedMaterial(MODEL_COLORS.copper), {
    position: [0, -0.08, 0.45],
  });
  addModelPart(ctx, geo.cylinder(0.03, 0.03, 0.55), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.2, 0],
  });
  for (const [x, z] of [
    [-0.45, -0.32],
    [0.45, -0.32],
    [-0.45, 0.32],
    [0.45, 0.32],
  ]) {
    addModelPart(
      ctx,
      geo.cylinder(0.035, 0.035, 0.1),
      createMetalMaterial(MODEL_COLORS.brass),
      { position: [x, -0.31, z] }
    );
  }
};

export const buildFlameSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.52, 0.6, 0.26), createStateMaterial(MODEL_COLORS.bodyMid), {
    position: [0, -0.6, 0],
  });
  addModelPart(ctx, geo.cylinder(0.66, 0.66, 0.06), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.74, 0],
  });
  for (const x of [-0.4, 0.4]) {
    addModelPart(
      ctx,
      geo.cylinder(0.03, 0.03, 0.05),
      createMetalMaterial(MODEL_COLORS.bodyDark),
      { position: [x, -0.74, 0.3] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.44, 0.44, 0.6), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.17, 0],
  });
  addModelPart(ctx, geo.torus(0.44, 0.02), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.04, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.torus(0.16, 0.035), createMetalMaterial(MODEL_COLORS.brass), {
    position: [0, -0.17, 0.46],
  });
  addModelPart(ctx, geo.cylinder(0.12, 0.12, 0.1), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, -0.17, 0.44],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.03), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [0, -0.17, 0.49],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cone(0.44, 0.24), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, 0.26, 0],
  });
  addModelPart(ctx, geo.cone(0.24, 0.42, 8), createGlossMaterial(MODEL_COLORS.amber), {
    position: [0, 0.58, 0],
  });
  addModelPart(ctx, geo.cone(0.12, 0.22, 8), createGlossMaterial(MODEL_COLORS.orange), {
    position: [0, 0.72, 0],
  });
};

export const buildGasSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.58, 0.58, 0.95), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.12, 0],
  });
  addModelPart(ctx, geo.cylinder(0.62, 0.64, 0.1), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.64, 0],
  });
  addModelPart(ctx, geo.cylinder(0.34, 0.42, 0.14), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, 0.52, 0],
  });
  addModelPart(ctx, geo.torus(0.5, 0.06), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.08, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.torus(0.5, 0.06), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.28, 0],
    rotation: [HALF_PI, 0, 0],
  });
  for (let k = 0; k < 6; k += 1) {
    const angle = (k / 6) * Math.PI * 2;
    addModelPart(
      ctx,
      geo.sphere(0.07, 8, 6),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [Math.cos(angle) * 0.5, 0.18, Math.sin(angle) * 0.5] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.22, 0.22, 0.2), createMetalMaterial(MODEL_COLORS.copper), {
    position: [0, 0.68, 0],
  });
  addModelPart(ctx, geo.torus(0.2, 0.025), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.72, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cone(0.23, 0.14), createMetalMaterial(MODEL_COLORS.steel, 0.5), {
    position: [0, 0.85, 0],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.92, 0.12, 0.92, 0.03),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.76, 0] }
  );
};

export const buildLightSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.85, 0.28, 0.85, 0.04),
    createStateMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.45, 0] }
  );
  addModelPart(ctx, geo.cylinder(0.34, 0.4, 0.14), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.26, 0],
  });
  addModelPart(
    ctx,
    geo.hemisphere(0.54, 14, 8),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, -0.24, 0], scale: [1, 0.62, 1] }
  );
  addModelPart(ctx, geo.torus(0.5, 0.03), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.22, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.box(0.2, 0.06, 0.2), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0.33, -0.29, 0.29],
  });
  addModelPart(ctx, geo.box(0.14, 0.03, 0.14), createOwnedMaterial(MODEL_COLORS.teal), {
    position: [0.33, -0.255, 0.29],
  });
  addModelPart(ctx, geo.box(0.07, 0.03, 0.11), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [-0.32, -0.29, 0.3],
  });
};

export const buildMotionSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.95, 1.15, 0.16, 0.04),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, -0.05, -0.3] }
  );
  for (const [x, y] of [
    [-0.36, 0.42],
    [0.36, -0.52],
  ]) {
    addModelPart(
      ctx,
      geo.cylinder(0.03, 0.03, 0.04),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [x, y, -0.21], rotation: [HALF_PI, 0, 0] }
    );
  }
  addModelPart(
    ctx,
    geo.torus(0.63, 0.055, 8, 24),
    createGlossMaterial(MODEL_COLORS.white),
    { position: [0, 0.02, 0.0] }
  );
  addModelPart(
    ctx,
    geo.hemisphere(0.6, 10, 5),
    createStateMaterial(MODEL_COLORS.white),
    {
      position: [0, 0.02, 0.04],
      rotation: [HALF_PI, 0, 0],
      scale: [1, 1, 0.95],
    }
  );
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.04), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [-0.3, -0.5, -0.19],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.sphere(0.04, 6, 6), createOwnedMaterial(MODEL_COLORS.red), {
    position: [-0.3, -0.5, -0.17],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.5, 0.12, 0.3, 0.03),
    createMetalMaterial(MODEL_COLORS.steel),
    { position: [0, -0.74, -0.14] }
  );
};

export const buildProximityCollisionSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.78, 0.5, 0.85, 0.05),
    createStateMaterial(MODEL_COLORS.bodyLight),
    { position: [0, -0.08, 0] }
  );
  for (const x of [-0.18, 0.18]) {
    addModelPart(
      ctx,
      geo.torus(0.155, 0.025),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [x, 0.04, 0.47] }
    );
    addModelPart(
      ctx,
      geo.cylinder(0.13, 0.13, 0.1),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [x, 0.04, 0.44], rotation: [HALF_PI, 0, 0] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.09, 0.09, 0.04), createGlossMaterial(MODEL_COLORS.amber), {
    position: [-0.18, 0.04, 0.5],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.roundedBox(0.5, 0.08, 0.34, 0.02), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.4, 0.24],
  });
  for (const x of [-0.44, 0.44]) {
    addModelPart(
      ctx,
      geo.roundedBox(0.1, 0.34, 0.5, 0.03),
      createOwnedMaterial(MODEL_COLORS.bodyDark),
      { position: [x, -0.15, 0] }
    );
  }
  addModelPart(ctx, geo.sphere(0.05, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.26, 0.28, 0],
  });
};

export const buildRfidSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.15, 0.9, 0.13, 0.04),
    createStateMaterial(MODEL_COLORS.bodyMid),
    { position: [0, 0.05, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(1.0, 0.76, 0.06, 0.035),
    createStateMaterial(MODEL_COLORS.bodyLight),
    { position: [0, 0.05, 0.07] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.56, 0.56, 0.05, 0.03),
    createOwnedMaterial(MODEL_COLORS.obsidian),
    { position: [0, 0.05, 0.1] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.42, 0.42, 0.03, 0.025),
    createOwnedMaterial(MODEL_COLORS.teal),
    { position: [0, 0.05, 0.125] }
  );
  for (const radius of [0.3, 0.46]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.03, 6, 20, Math.PI),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [0, 0.05, 0.16] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.07, 0.09, 0.16), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0.38, -0.48, -0.05],
    rotation: [0.9, 0, 0],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.9, 0.12, 0.5, 0.03),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.62, -0.18], rotation: [0.45, 0, 0] }
  );
};

export const buildSoilSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.55, 0.48, 0.42, 0.05),
    createStateMaterial(MODEL_COLORS.green),
    { position: [0, 0.72, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.45, 0.06, 0.34, 0.02),
    createGlossMaterial(MODEL_COLORS.bodyLight),
    { position: [0, 0.99, 0] }
  );
  addModelPart(ctx, geo.box(0.3, 0.03, 0.2), createOwnedMaterial(MODEL_COLORS.pcb), {
    position: [0, 1.04, 0],
  });
  addModelPart(ctx, geo.cylinder(0.025, 0.025, 0.28), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, 1.2, 0],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.4, 0.16, 0.3, 0.04),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0, 0.42, 0] }
  );
  for (const x of [-0.15, 0.15]) {
    addModelPart(
      ctx,
      geo.cylinder(0.11, 0.11, 0.14),
      createMetalMaterial(MODEL_COLORS.bodyLight),
      { position: [x, 0.28, 0] }
    );
  }
  for (const x of [-0.15, 0.15]) {
    addModelPart(
      ctx,
      geo.cylinder(0.095, 0.095, 1.45),
      createMetalMaterial(MODEL_COLORS.steel, 0.28),
      { position: [x, -0.55, 0] }
    );
    addModelPart(
      ctx,
      geo.cone(0.095, 0.24),
      createOwnedMaterial(MODEL_COLORS.copper),
      { position: [x, -1.4, 0], rotation: [Math.PI, 0, 0] }
    );
  }
  addModelPart(ctx, geo.box(0.42, 0.07, 0.09), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.12, 0],
  });
};

export const buildSoundSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.52, 0.6, 0.24), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.6, 0],
  });
  addModelPart(ctx, geo.torus(0.52, 0.02), createMetalMaterial(MODEL_COLORS.brass), {
    position: [0, -0.49, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cylinder(0.38, 0.38, 0.75), createMetalMaterial(MODEL_COLORS.steel, 0.42), {
    position: [0, -0.1, 0],
  });
  addModelPart(
    ctx,
    geo.hemisphere(0.36, 12, 6),
    createOwnedMaterial(MODEL_COLORS.obsidian),
    { position: [0, 0.27, 0] }
  );
  addModelPart(ctx, geo.torus(0.37, 0.02), createMetalMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.27, 0],
    rotation: [HALF_PI, 0, 0],
  });
  for (const radius of [0.28, 0.42]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.026, 6, 18, Math.PI),
      createGlossMaterial(MODEL_COLORS.cloud),
      { position: [0.34, 0.44, 0], rotation: [0, 0, -0.6] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.08, 0.08, 0.14), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [-0.48, -0.32, 0],
    rotation: [0, 0, HALF_PI],
  });
  addModelPart(ctx, geo.cylinder(0.44, 0.5, 0.08), createOwnedMaterial(MODEL_COLORS.rubber), {
    position: [0, -0.76, 0],
  });
};

export const buildSteamSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.5, 0.56, 0.3), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.55, 0],
  });
  addModelPart(
    ctx,
    geo.capsule(0.34, 0.55),
    createStateMaterial(MODEL_COLORS.steel),
    { position: [0, -0.05, 0], rotation: [0, 0, HALF_PI] }
  );
  for (const x of [-0.58, 0.58]) {
    addModelPart(
      ctx,
      geo.torus(0.33, 0.035, 8, 20),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [x, -0.05, 0], rotation: [0, HALF_PI, 0] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.4, 0.4, 0.26), createMetalMaterial(MODEL_COLORS.brass), {
    position: [0, 0.42, 0],
  });
  addModelPart(ctx, geo.torus(0.4, 0.025), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.31, 0],
    rotation: [HALF_PI, 0, 0],
  });
  for (const angle of [0.4, 1.9, 3.6]) {
    addModelPart(
      ctx,
      geo.box(0.1, 0.06, 0.04),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      {
        position: [Math.cos(angle) * 0.4, 0.42, Math.sin(angle) * 0.4],
        rotation: [0, -angle + HALF_PI, 0],
      }
    );
  }
  addModelPart(ctx, geo.cone(0.4, 0.2), createMetalMaterial(MODEL_COLORS.steel, 0.5), {
    position: [0, 0.64, 0],
  });
  addModelPart(ctx, geo.cylinder(0.09, 0.09, 0.32), createMetalMaterial(MODEL_COLORS.copper), {
    position: [0.5, 0.14, 0],
    rotation: [0, 0, -0.9],
  });
  for (const [radius, offset] of [
    [0.15, 0.12],
    [0.25, -0.08],
  ]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.024, 6, 16, Math.PI),
      createGlossMaterial(MODEL_COLORS.cloud),
      { position: [offset * 0.5, 0.9 + offset * 0.6, 0], rotation: [0, 0, 0.35] }
    );
  }
};

export const buildUltrasonicSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.25, 0.9, 0.12, 0.035),
    createStateMaterial(MODEL_COLORS.pcb),
    {}
  );
  for (const x of [-0.33, 0.33]) {
    addModelPart(
      ctx,
      geo.cylinder(0.26, 0.26, 0.22),
      createMetalMaterial(MODEL_COLORS.steel, 0.4),
      { position: [x, 0.12, 0.13], rotation: [HALF_PI, 0, 0] }
    );
    addModelPart(
      ctx,
      geo.cylinder(0.19, 0.19, 0.05),
      createOwnedMaterial(MODEL_COLORS.obsidian),
      { position: [x, 0.12, 0.255], rotation: [HALF_PI, 0, 0] }
    );
    addModelPart(
      ctx,
      geo.torus(0.21, 0.02, 6, 18),
      createMetalMaterial(MODEL_COLORS.bodyLight),
      { position: [x, 0.12, 0.245] }
    );
  }
  addModelPart(ctx, geo.box(0.16, 0.1, 0.08), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.16, 0.1],
  });
  addModelPart(ctx, geo.box(0.34, 0.12, 0.08), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0.42, -0.3, 0.06],
  });
  addModelPart(ctx, geo.box(0.3, 0.04, 0.04), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [-0.35, -0.5, 0.03],
  });
  for (const x of [-0.56, 0.56]) {
    addModelPart(
      ctx,
      geo.cylinder(0.035, 0.035, 0.06),
      createMetalMaterial(MODEL_COLORS.brass),
      { position: [x, -0.38, 0], rotation: [HALF_PI, 0, 0] }
    );
  }
};

export const buildVibrationSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.95, 0.2, 0.95, 0.04),
    createStateMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.62, 0] }
  );
  for (const x of [-0.32, 0.32]) {
    addModelPart(
      ctx,
      geo.roundedBox(0.18, 0.07, 0.18, 0.025),
      createRubberMaterial(),
      { position: [x, -0.74, 0] }
    );
  }
  for (const radius of [0.34, 0.46]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.018, 6, 20),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [0, -0.51, 0], rotation: [HALF_PI, 0, 0] }
    );
  }
  for (const y of [-0.36, -0.24, -0.12]) {
    addModelPart(
      ctx,
      geo.torus(0.19, 0.038, 6, 14),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [0, y, 0], rotation: [HALF_PI, 0, 0] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.16, 0.2, 0.1), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.0, 0],
  });
  addModelPart(ctx, geo.icosahedron(0.27, 0), createMetalMaterial(MODEL_COLORS.brass), {
    position: [0, 0.18, 0],
  });
  addModelPart(ctx, geo.cylinder(0.09, 0.09, 0.08), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, 0.46, 0],
  });
};

export const buildWaterSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.0, 0.28, 0.78, 0.05),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, -0.42, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.84, 0.1, 0.64, 0.04),
    createOwnedMaterial(MODEL_COLORS.obsidian),
    { position: [0, -0.33, 0] }
  );
  for (const x of [-0.17, 0.17]) {
    addModelPart(
      ctx,
      geo.box(0.05, 0.06, 0.6),
      createMetalMaterial(MODEL_COLORS.steel, 0.25),
      { position: [x, -0.26, 0] }
    );
  }
  addModelPart(ctx, geo.octahedron(0.14, 0), createGlassMaterial("#38bdf8"), {
    position: [0, -0.1, 0],
    scale: [1, 1.4, 1],
  });
  for (const x of [-0.42, 0.42]) {
    addModelPart(
      ctx,
      geo.cylinder(0.035, 0.035, 0.05),
      createMetalMaterial(MODEL_COLORS.brass),
      { position: [x, -0.29, 0.3], rotation: [HALF_PI, 0, 0] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.18), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.46, 0.46],
    rotation: [HALF_PI, 0, 0],
  });
};

export const buildWeatherSensorModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.34, 0.14, 0.34, 0.03),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.55, 0] }
  );
  const legs: Array<[number, number, number, number]> = [
    [0.3, -0.93, 0, -0.38],
    [-0.16, -0.93, 0.27, 0.31],
    [-0.16, -0.93, -0.27, 0.31],
  ];
  legs.forEach(([x, y, z, tilt]) => {
    addModelPart(
      ctx,
      geo.cylinder(0.045, 0.045, 0.75),
      createMetalMaterial(MODEL_COLORS.steel),
      {
        position: [x, y, z],
        rotation: [z === 0 ? 0 : tilt, 0, z === 0 ? tilt : tilt * 0.6],
      }
    );
  });
  addModelPart(ctx, geo.cylinder(0.06, 0.075, 0.95), createStateMaterial(MODEL_COLORS.steel), {
    position: [0, -0.02, 0],
  });
  addModelPart(ctx, geo.cylinder(0.09, 0.09, 0.12), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.48, 0],
  });
  addModelPart(ctx, geo.cylinder(0.055, 0.055, 0.75), createStateMaterial(MODEL_COLORS.steel), {
    position: [0, 0.9, 0],
  });
  addModelPart(ctx, geo.box(0.3, 0.05, 0.05), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, 0.35, 0.1],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.36, 0.07, 0.36, 0.02),
    createGlossMaterial(MODEL_COLORS.white),
    { position: [0, 0.24, 0.32] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.33, 0.22, 0.33, 0.03),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.38, 0.32] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.36, 0.07, 0.36, 0.02),
    createGlossMaterial(MODEL_COLORS.white),
    { position: [0, 0.52, 0.32] }
  );
  addModelPart(ctx, geo.cylinder(0.03, 0.03, 0.26), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, 1.4, 0],
  });
  addModelPart(ctx, geo.cylinder(0.05, 0.05, 0.08), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 1.54, 0],
  });
  addModelPart(ctx, geo.box(0.62, 0.035, 0.035), createMetalMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 1.6, 0],
  });
  for (const x of [-0.31, 0.31]) {
    addModelPart(
      ctx,
      geo.sphere(0.07, 8, 6),
      createOwnedMaterial(MODEL_COLORS.amber),
      { position: [x, 1.57, 0] }
    );
  }
  addModelPart(ctx, geo.box(0.028, 0.13, 0.32), createOwnedMaterial(MODEL_COLORS.orange), {
    position: [0, 1.22, -0.2],
  });
  addModelPart(ctx, geo.cylinder(0.02, 0.02, 0.22), createMetalMaterial(MODEL_COLORS.steel), {
    position: [-0.3, 0.05, 0],
    rotation: [0, 0, HALF_PI],
  });
  addModelPart(
    ctx,
    geo.cylinder(0.15, 0.09, 0.17),
    createGlossMaterial(MODEL_COLORS.cloud),
    { position: [-0.44, 0.05, 0] }
  );
};
