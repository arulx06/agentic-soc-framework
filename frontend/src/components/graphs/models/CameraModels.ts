import {
  MODEL_COLORS,
  createOwnedMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type { ModelBuilder } from "./modelTypes";
import { addModelPart, geo } from "./modelUtils";

const HALF_PI = Math.PI / 2;

function addLensBarrel(
  ctx: Parameters<ModelBuilder>[0],
  position: [number, number, number],
  rotation: [number, number, number] = [HALF_PI, 0, 0],
  ringRadius = 0.17
) {
  addModelPart(
    ctx,
    geo.cylinder(ringRadius, ringRadius + 0.02, 0.1),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position, rotation }
  );
  addModelPart(
    ctx,
    geo.cylinder(ringRadius * 0.66, ringRadius * 0.66, 0.04),
    createOwnedMaterial(MODEL_COLORS.lensGlass),
    {
      position: [position[0], position[1], position[2] + 0.055],
      rotation,
    }
  );
}

export const buildBluramsCameraModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.62, 0.68, 0.2), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.55, 0],
  });
  addModelPart(ctx, geo.cylinder(0.16, 0.2, 0.28), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.34, 0],
  });
  addModelPart(
    ctx,
    geo.sphere(0.42, 14, 10),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.04, 0.05], scale: [1.15, 0.8, 0.9] }
  );
  for (const x of [-0.5, 0.5]) {
    addModelPart(
      ctx,
      geo.cylinder(0.07, 0.07, 0.12),
      createOwnedMaterial(MODEL_COLORS.bodyDark),
      { position: [x, 0.06, 0], rotation: [0, 0, HALF_PI] }
    );
  }
  const lensPos: [number, number, number] = [0, 0.06, 0.44];
  addModelPart(
    ctx,
    geo.cylinder(0.18, 0.2, 0.12),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: lensPos, rotation: [-0.15, 0, 0] }
  );
  addModelPart(
    ctx,
    geo.cylinder(0.12, 0.12, 0.04),
    createOwnedMaterial(MODEL_COLORS.lensGlass),
    { position: [lensPos[0], lensPos[1], lensPos[2] + 0.06] }
  );
};

export const buildDekcoCameraModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.cylinder(0.28, 0.31, 1.1),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0.05, 0.25, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(
    ctx,
    geo.cylinder(0.34, 0.34, 0.36),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0.38, 0.25, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(
    ctx,
    geo.cylinder(0.3, 0.28, 0.14),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0.66, 0.25, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(
    ctx,
    geo.cylinder(0.16, 0.16, 0.05),
    createOwnedMaterial(MODEL_COLORS.lensGlass),
    { position: [0.75, 0.25, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(
    ctx,
    geo.cylinder(0.24, 0.28, 0.14),
    createOwnedMaterial(MODEL_COLORS.bodyMid),
    { position: [-0.56, 0.25, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(ctx, geo.box(0.12, 0.62, 0.18), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [-0.15, -0.22, 0],
  });
  addModelPart(ctx, geo.box(0.34, 0.08, 0.34), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [-0.15, -0.58, 0],
  });
};

export const buildGeeniCameraModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(0.74, 0.56, 0.5), createStateMaterial(MODEL_COLORS.white), {
    position: [0, 0.15, 0],
  });
  addLensBarrel(ctx, [0, 0.15, 0.29]);
  addModelPart(ctx, geo.sphere(0.035, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.27, 0.36, 0.24],
  });
  addModelPart(ctx, geo.box(0.16, 0.4, 0.14), createOwnedMaterial(MODEL_COLORS.bodyMid), {
    position: [0, -0.3, 0],
  });
  addModelPart(ctx, geo.cylinder(0.32, 0.36, 0.1), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.57, 0],
  });
};

export const buildMyqCameraModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.box(1.02, 0.58, 0.46), createStateMaterial(MODEL_COLORS.white), {
    position: [0, 0.2, 0],
  });
  addLensBarrel(ctx, [0.3, 0.2, 0.27], [HALF_PI, 0, 0], 0.16);
  addModelPart(ctx, geo.box(0.2, 0.12, 0.04), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [-0.26, 0.2, 0.25],
  });
  addModelPart(ctx, geo.sphere(0.03, 6, 6), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [-0.02, 0.53, 0.2],
  });
  addModelPart(
    ctx,
    geo.box(0.1, 0.6, 0.14),
    createOwnedMaterial(MODEL_COLORS.steel),
    { position: [-0.12, -0.32, 0], rotation: [0, 0, 0.55] }
  );
  addModelPart(ctx, geo.box(0.5, 0.08, 0.4), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [-0.4, -0.6, 0],
  });
};

export const buildWisenetCameraModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.72, 0.78, 0.16), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.5, 0],
  });
  addModelPart(ctx, geo.torus(0.64, 0.03), createOwnedMaterial(MODEL_COLORS.steel), {
    position: [0, -0.41, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(
    ctx,
    geo.hemisphere(0.58, 14, 7),
    createStateMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.4, 0], scale: [1, 0.85, 1] }
  );
  addModelPart(ctx, geo.sphere(0.2, 10, 8), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, -0.28, 0.22],
  });
  addModelPart(ctx, geo.cylinder(0.09, 0.09, 0.05), createOwnedMaterial(MODEL_COLORS.lensGlass), {
    position: [0, -0.26, 0.4],
    rotation: [HALF_PI, 0, 0],
  });
};

export const buildYiCameraModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.sphere(0.44, 16, 12),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.42, 0], scale: [1, 0.92, 0.95] }
  );
  addLensBarrel(ctx, [0, 0.42, 0.38], [HALF_PI, 0, 0], 0.19);
  addModelPart(ctx, geo.sphere(0.03, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.22, 0.58, 0.3],
  });
  addModelPart(ctx, geo.cylinder(0.08, 0.1, 0.5), createOwnedMaterial(MODEL_COLORS.bodyMid), {
    position: [0, 0.02, 0],
  });
  addModelPart(ctx, geo.cylinder(0.38, 0.42, 0.12), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.32, 0],
  });
  addModelPart(ctx, geo.cylinder(0.3, 0.32, 0.06), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.41, 0],
  });
};
