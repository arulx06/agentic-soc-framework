import {
  MODEL_COLORS,
  createOwnedMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type { ModelBuilder } from "./modelTypes";
import { addModelPart, geo } from "./modelUtils";

const HALF_PI = Math.PI / 2;

export const buildAccelerometerSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(1.15, 0.12, 0.9), createStateMaterial(MODEL_COLORS.pcb), {
    position: [0, -0.25, 0],
  });
  addModelPart(ctx, geo.box(0.42, 0.18, 0.42), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.1, 0],
  });
  addModelPart(ctx, geo.box(0.55, 0.05, 0.05), createOwnedMaterial(MODEL_COLORS.copper), {
    position: [0.45, -0.08, 0],
  });
  addModelPart(ctx, geo.box(0.05, 0.05, 0.55), createOwnedMaterial(MODEL_COLORS.copper), {
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
      geo.cylinder(0.035, 0.035, 0.12),
      createOwnedMaterial(MODEL_COLORS.brass),
      { position: [x, -0.31, z] }
    );
  }
};

export const buildFlameSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.52, 0.6, 0.26), createStateMaterial(MODEL_COLORS.bodyMid), {
    position: [0, -0.62, 0],
  });
  addModelPart(ctx, geo.cylinder(0.44, 0.44, 0.6), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.19, 0],
  });
  addModelPart(ctx, geo.torus(0.44, 0.04), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.09, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cone(0.44, 0.24), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.3, 0],
  });
  addModelPart(ctx, geo.cylinder(0.14, 0.14, 0.06), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [0, -0.19, 0.46],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cone(0.28, 0.5), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [0, 0.66, 0],
  });
  addModelPart(ctx, geo.cone(0.14, 0.26), createOwnedMaterial(MODEL_COLORS.orange), {
    position: [0, 0.82, 0],
  });
};

export const buildGasSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.58, 0.58, 0.95), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.12, 0],
  });
  addModelPart(ctx, geo.cylinder(0.5, 0.56, 0.16), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.68, 0],
  });
  addModelPart(ctx, geo.torus(0.5, 0.06), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.1, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.torus(0.5, 0.06), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.3, 0],
    rotation: [HALF_PI, 0, 0],
  });
  for (let k = 0; k < 6; k += 1) {
    const angle = (k / 6) * Math.PI * 2;
    addModelPart(
      ctx,
      geo.sphere(0.075, 8, 6),
      createOwnedMaterial(MODEL_COLORS.bodyDark),
      { position: [Math.cos(angle) * 0.5, 0.2, Math.sin(angle) * 0.5] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.22, 0.22, 0.22), createOwnedMaterial(MODEL_COLORS.copper), {
    position: [0, 0.53, 0],
  });
  addModelPart(ctx, geo.cone(0.24, 0.16), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.71, 0],
  });
};

export const buildLightSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(0.85, 0.26, 0.85), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.45, 0],
  });
  addModelPart(ctx, geo.cylinder(0.34, 0.4, 0.16), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, -0.27, 0],
  });
  addModelPart(
    ctx,
    geo.sphere(0.55, 14, 8),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, -0.22, 0], scale: [1, 0.6, 1] }
  );
  addModelPart(ctx, geo.box(0.22, 0.05, 0.22), createOwnedMaterial(MODEL_COLORS.teal), {
    position: [0.33, -0.29, 0.28],
  });
};

export const buildMotionSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(0.95, 1.15, 0.16), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.05, -0.28],
  });
  addModelPart(
    ctx,
    geo.hemisphere(0.6, 10, 5),
    createStateMaterial(MODEL_COLORS.white),
    {
      position: [0, 0.02, 0.02],
      rotation: [HALF_PI, 0, 0],
      scale: [1, 1, 0.78],
    }
  );
  addModelPart(ctx, geo.box(0.5, 0.12, 0.3), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, -0.74, -0.12],
  });
  addModelPart(ctx, geo.sphere(0.05, 8, 6), createOwnedMaterial(MODEL_COLORS.red), {
    position: [-0.3, -0.52, -0.18],
  });
};

export const buildProximityCollisionSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(0.78, 0.5, 0.85), createStateMaterial(MODEL_COLORS.bodyLight), {
    position: [0, -0.08, 0],
  });
  addModelPart(ctx, geo.cylinder(0.13, 0.13, 0.12), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [-0.18, 0.04, 0.46],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.cylinder(0.13, 0.13, 0.12), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0.18, 0.04, 0.46],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.box(0.5, 0.08, 0.32), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, -0.4, 0.24],
  });
  addModelPart(ctx, geo.box(0.12, 0.34, 0.5), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [-0.44, -0.15, 0],
  });
  addModelPart(ctx, geo.box(0.12, 0.34, 0.5), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0.44, -0.15, 0],
  });
  addModelPart(ctx, geo.sphere(0.06, 8, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.26, 0.29, 0],
  });
};

export const buildRfidSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(1.15, 0.9, 0.13), createStateMaterial(MODEL_COLORS.bodyMid), {
    position: [0, 0.05, 0],
  });
  addModelPart(ctx, geo.box(0.5, 0.5, 0.05), createOwnedMaterial(MODEL_COLORS.teal), {
    position: [0, 0.05, 0.08],
  });
  for (const radius of [0.3, 0.44, 0.58]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.035, 6, 20, Math.PI),
      createOwnedMaterial(MODEL_COLORS.steel),
      { position: [0, 0.05, 0.14], scale: [1, 1, 1] }
    );
  }
  addModelPart(ctx, geo.box(0.9, 0.12, 0.55), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.62, -0.18],
    rotation: [0.45, 0, 0],
  });
};

export const buildSoilSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(0.55, 0.48, 0.42), createStateMaterial(MODEL_COLORS.green), {
    position: [0, 0.72, 0],
  });
  addModelPart(ctx, geo.box(0.4, 0.07, 0.28), createOwnedMaterial(MODEL_COLORS.pcb), {
    position: [0, 1.0, 0],
  });
  addModelPart(ctx, geo.cylinder(0.025, 0.025, 0.3), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 1.18, 0],
  });
  addModelPart(ctx, geo.box(0.42, 0.07, 0.09), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.08, 0],
  });
  for (const x of [-0.15, 0.15]) {
    addModelPart(
      ctx,
      geo.cylinder(0.085, 0.085, 1.5),
      createStateMaterial(MODEL_COLORS.steel),
      { position: [x, -0.85, 0] }
    );
    addModelPart(
      ctx,
      geo.cone(0.085, 0.24),
      createOwnedMaterial(MODEL_COLORS.copper),
      { position: [x, -1.72, 0], rotation: [Math.PI, 0, 0] }
    );
  }
};

export const buildSoundSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.52, 0.6, 0.24), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.6, 0],
  });
  addModelPart(ctx, geo.cylinder(0.38, 0.38, 0.75), createStateMaterial(MODEL_COLORS.bodyMid), {
    position: [0, -0.1, 0],
  });
  addModelPart(ctx, geo.hemisphere(0.38, 12, 6), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.27, 0],
  });
  addModelPart(ctx, geo.torus(0.39, 0.03), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.1, 0],
    rotation: [HALF_PI, 0, 0],
  });
  for (const radius of [0.28, 0.42]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.028, 6, 18, Math.PI),
      createOwnedMaterial(MODEL_COLORS.cloud),
      { position: [0.34, 0.42, 0], rotation: [0, 0, -0.6] }
    );
  }
  addModelPart(ctx, geo.cylinder(0.44, 0.5, 0.1), createOwnedMaterial(MODEL_COLORS.bodyLight), {
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
  addModelPart(ctx, geo.cylinder(0.4, 0.4, 0.26), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [0, 0.42, 0],
  });
  addModelPart(ctx, geo.cone(0.4, 0.2), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.64, 0],
  });
  addModelPart(ctx, geo.cylinder(0.09, 0.09, 0.32), createOwnedMaterial(MODEL_COLORS.copper), {
    position: [0.48, 0.12, 0],
    rotation: [0, 0, -0.9],
  });
  for (const [radius, offset] of [
    [0.16, 0.12],
    [0.26, -0.08],
  ]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.026, 6, 16, Math.PI),
      createOwnedMaterial(MODEL_COLORS.cloud),
      { position: [offset * 0.5, 0.92 + offset * 0.6, 0], rotation: [0, 0, 0.35] }
    );
  }
};

export const buildUltrasonicSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(1.25, 0.9, 0.12), createStateMaterial(MODEL_COLORS.pcb), {});
  for (const x of [-0.33, 0.33]) {
    addModelPart(
      ctx,
      geo.cylinder(0.26, 0.26, 0.24),
      createOwnedMaterial(MODEL_COLORS.bodyDark),
      { position: [x, 0.12, 0.14], rotation: [HALF_PI, 0, 0] }
    );
    addModelPart(
      ctx,
      geo.cylinder(0.2, 0.2, 0.06),
      createOwnedMaterial(MODEL_COLORS.steel),
      { position: [x, 0.12, 0.29], rotation: [HALF_PI, 0, 0] }
    );
  }
  addModelPart(ctx, geo.box(0.16, 0.1, 0.08), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, -0.18, 0.1],
  });
  addModelPart(ctx, geo.box(0.5, 0.06, 0.06), createOwnedMaterial(MODEL_COLORS.brass), {
    position: [0, -0.5, 0.02],
  });
};

export const buildVibrationSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.48, 0.54, 0.2), createStateMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.62, 0],
  });
  for (const radius of [0.34, 0.44]) {
    addModelPart(
      ctx,
      geo.torus(radius, 0.02, 6, 20),
      createOwnedMaterial(MODEL_COLORS.steel),
      { position: [0, -0.51, 0], rotation: [HALF_PI, 0, 0] }
    );
  }
  for (const y of [-0.36, -0.24, -0.12]) {
    addModelPart(
      ctx,
      geo.torus(0.2, 0.04, 6, 14),
      createOwnedMaterial(MODEL_COLORS.steel),
      { position: [0, y, 0], rotation: [HALF_PI, 0, 0] }
    );
  }
  addModelPart(ctx, geo.icosahedron(0.28, 0), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [0, 0.14, 0],
  });
  addModelPart(ctx, geo.cylinder(0.1, 0.1, 0.1), createOwnedMaterial(MODEL_COLORS.bodyLight), {
    position: [0, 0.46, 0],
  });
};

export const buildWaterSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.58, 0.64, 0.2), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.45, 0],
  });
  addModelPart(ctx, geo.cylinder(0.46, 0.46, 0.08), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.37, 0],
  });
  for (const x of [-0.14, 0.14]) {
    addModelPart(
      ctx,
      geo.cylinder(0.045, 0.045, 0.3),
      createOwnedMaterial(MODEL_COLORS.brass),
      { position: [x, -0.18, 0] }
    );
  }
  addModelPart(
    ctx,
    geo.octahedron(0.15, 0),
    createOwnedMaterial(MODEL_COLORS.lensGlass),
    { position: [0, 0.04, 0], scale: [1, 1.35, 1] }
  );
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.2), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.48, 0.56],
    rotation: [HALF_PI, 0, 0],
  });
};

export const buildWeatherSensorModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.16, 0.18, 0.18), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.55, 0],
  });
  const legs: Array<[number, number, number, number]> = [
    [0.3, -0.93, 0, -0.38],
    [-0.16, -0.93, 0.27, 0.31],
    [-0.16, -0.93, -0.27, 0.31],
  ];
  legs.forEach(([x, y, z, tilt]) => {
    addModelPart(
      ctx,
      geo.cylinder(0.045, 0.045, 0.75),
      createOwnedMaterial(MODEL_COLORS.steel),
      {
        position: [x, y, z],
        rotation: [z === 0 ? 0 : tilt, 0, z === 0 ? tilt : tilt * 0.6],
      }
    );
  });
  addModelPart(ctx, geo.cylinder(0.06, 0.075, 1.7), createStateMaterial(MODEL_COLORS.steel), {
    position: [0, 0.35, 0],
  });
  addModelPart(ctx, geo.box(0.3, 0.06, 0.06), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 0.35, 0.12],
  });
  addModelPart(ctx, geo.box(0.34, 0.5, 0.34), createStateMaterial(MODEL_COLORS.white), {
    position: [0, 0.35, 0.34],
  });
  addModelPart(ctx, geo.cylinder(0.03, 0.03, 0.28), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, 1.34, 0],
  });
  addModelPart(ctx, geo.box(0.62, 0.04, 0.04), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 1.5, 0],
  });
  for (const x of [-0.31, 0.31]) {
    addModelPart(
      ctx,
      geo.sphere(0.07, 8, 6),
      createOwnedMaterial(MODEL_COLORS.amber),
      { position: [x, 1.47, 0] }
    );
  }
  addModelPart(ctx, geo.box(0.03, 0.14, 0.34), createOwnedMaterial(MODEL_COLORS.orange), {
    position: [0, 1.16, -0.2],
  });
  addModelPart(ctx, geo.cylinder(0.02, 0.02, 0.22), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [-0.3, 0.05, 0],
    rotation: [0, 0, HALF_PI],
  });
  addModelPart(
    ctx,
    geo.cylinder(0.16, 0.1, 0.18),
    createOwnedMaterial(MODEL_COLORS.cloud),
    { position: [-0.44, 0.05, 0] }
  );
};
