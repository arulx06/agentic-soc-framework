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

function addLensAssembly(
  ctx: Parameters<ModelBuilder>[0],
  position: [number, number, number],
  radius: number,
  rotation: [number, number, number] = [HALF_PI, 0, 0],
  withPupil = false
) {
  const forward = newForwardOffset(rotation);
  addModelPart(
    ctx,
    geo.cylinder(radius + 0.035, radius + 0.035, 0.06),
    createMetalMaterial(MODEL_COLORS.steel),
    {
      position: [position[0] + forward[0] * 0.04, position[1] + forward[1] * 0.04, position[2] + forward[2] * 0.04],
      rotation,
    }
  );
  addModelPart(
    ctx,
    geo.cylinder(radius, radius + 0.012, 0.12),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position, rotation }
  );
  addModelPart(
    ctx,
    geo.cylinder(radius * 0.72, radius * 0.72, 0.05),
    createOwnedMaterial(MODEL_COLORS.obsidian),
    {
      position: [position[0] + forward[0] * 0.045, position[1] + forward[1] * 0.045, position[2] + forward[2] * 0.045],
      rotation,
    }
  );
  addModelPart(
    ctx,
    geo.cylinder(radius * 0.52, radius * 0.52, 0.03),
    createGlassMaterial(),
    {
      position: [position[0] + forward[0] * 0.068, position[1] + forward[1] * 0.068, position[2] + forward[2] * 0.068],
      rotation,
    }
  );
  if (withPupil) {
    addModelPart(
      ctx,
      geo.cylinder(radius * 0.22, radius * 0.22, 0.015),
      createGlossMaterial(MODEL_COLORS.cloud),
      {
        position: [position[0] + forward[0] * 0.085, position[1] + forward[1] * 0.085, position[2] + forward[2] * 0.085],
        rotation,
      }
    );
  }
}

function newForwardOffset(rotation: [number, number, number]): [number, number, number] {
  const [x, y, z] = rotation;
  const sinY = Math.sin(y);
  const cosY = Math.cos(y);
  const sinX = Math.sin(x);
  const cosX = Math.cos(x);
  const sinZ = Math.sin(z);
  const cosZ = Math.cos(z);
  const local = [0, 1, 0];
  const afterZ = [
    local[0] * cosZ - local[1] * sinZ,
    local[0] * sinZ + local[1] * cosZ,
    local[2],
  ];
  const afterX = [
    afterZ[0],
    afterZ[1] * cosX - afterZ[2] * sinX,
    afterZ[1] * sinX + afterZ[2] * cosX,
  ];
  const afterY = [
    afterX[0] * cosY + afterX[2] * sinY,
    afterX[1],
    -afterX[0] * sinY + afterX[2] * cosY,
  ];
  return [afterY[0], afterY[1], afterY[2]];
}

export const buildBluramsCameraModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.92, 0.2, 0.92, 0.05),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, -0.48, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.78, 0.07, 0.78, 0.03),
    createRubberMaterial(),
    { position: [0, -0.6, 0] }
  );
  addModelPart(ctx, geo.cylinder(0.17, 0.21, 0.14), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.33, 0],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.72, 0.5, 0.6, 0.09),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.02, 0.02] }
  );
  for (const x of [-0.41, 0.41]) {
    addModelPart(
      ctx,
      geo.cylinder(0.07, 0.07, 0.1),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [x, 0.02, 0], rotation: [0, 0, HALF_PI] }
    );
  }
  addLensAssembly(ctx, [0, 0.02, 0.34], 0.19, [HALF_PI, 0, 0], true);
  addModelPart(ctx, geo.sphere(0.03, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.24, 0.3, 0.31],
  });
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
    geo.cylinder(0.36, 0.36, 0.4),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [0.34, 0.29, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(ctx, geo.torus(0.31, 0.03), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0.63, 0.25, 0],
    rotation: [0, HALF_PI, 0],
  });
  addLensAssembly(ctx, [0.68, 0.25, 0], 0.2, [0, 0, -HALF_PI]);
  addModelPart(
    ctx,
    geo.cylinder(0.24, 0.28, 0.14),
    createOwnedMaterial(MODEL_COLORS.bodyMid),
    { position: [-0.56, 0.25, 0], rotation: [0, 0, HALF_PI] }
  );
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.12), createOwnedMaterial(MODEL_COLORS.rubber), {
    position: [-0.65, 0.25, 0],
    rotation: [0, 0, HALF_PI],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.12, 0.4, 0.18, 0.03),
    createMetalMaterial(MODEL_COLORS.steel),
    { position: [-0.15, -0.08, 0], rotation: [0, 0, 0.5] }
  );
  addModelPart(ctx, geo.sphere(0.06, 8, 6), createMetalMaterial(MODEL_COLORS.bodyDark), {
    position: [-0.24, -0.26, 0],
  });
  addModelPart(ctx, geo.box(0.12, 0.34, 0.16), createMetalMaterial(MODEL_COLORS.steel), {
    position: [-0.28, -0.45, 0],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.36, 0.07, 0.36, 0.02),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [-0.28, -0.64, 0] }
  );
};

export const buildGeeniCameraModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.74, 0.54, 0.48, 0.09),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.18, 0] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.6, 0.42, 0.06, 0.05),
    createGlossMaterial(MODEL_COLORS.bodyLight),
    { position: [0, 0.18, 0.24] }
  );
  addLensAssembly(ctx, [0, 0.18, 0.29], 0.17);
  addModelPart(ctx, geo.sphere(0.09, 10, 8), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.16, 0],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.15, 0.34, 0.13, 0.04),
    createOwnedMaterial(MODEL_COLORS.bodyMid),
    { position: [0, -0.4, 0] }
  );
  addModelPart(ctx, geo.cylinder(0.32, 0.36, 0.1), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.62, 0],
  });
  addModelPart(ctx, geo.cylinder(0.26, 0.28, 0.05), createRubberMaterial(), {
    position: [0, -0.7, 0],
  });
  addModelPart(ctx, geo.sphere(0.032, 6, 6), createOwnedMaterial(MODEL_COLORS.green), {
    position: [0.26, 0.38, 0.23],
  });
};

export const buildMyqCameraModel: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(1.02, 0.58, 0.46, 0.07),
    createStateMaterial(MODEL_COLORS.white),
    { position: [0, 0.2, 0] }
  );
  for (const y of [0.44, -0.04]) {
    addModelPart(
      ctx,
      geo.roundedBox(0.94, 0.08, 0.42, 0.03),
      createOwnedMaterial(MODEL_COLORS.bodyDark),
      { position: [0, y, 0] }
    );
  }
  addLensAssembly(ctx, [0.3, 0.2, 0.27], 0.19);
  addModelPart(ctx, geo.box(0.22, 0.14, 0.05), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [-0.24, 0.2, 0.235],
  });
  addModelPart(ctx, geo.sphere(0.032, 6, 6), createOwnedMaterial(MODEL_COLORS.amber), {
    position: [-0.02, 0.5, 0.2],
  });
  addModelPart(ctx, geo.cylinder(0.07, 0.07, 0.12), createMetalMaterial(MODEL_COLORS.steel), {
    position: [-0.3, -0.14, 0],
    rotation: [0, 0, HALF_PI],
  });
  addModelPart(
    ctx,
    geo.roundedBox(0.11, 0.55, 0.14, 0.03),
    createMetalMaterial(MODEL_COLORS.steel),
    { position: [-0.16, -0.4, 0], rotation: [0, 0, 0.55] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.52, 0.08, 0.42, 0.02),
    createOwnedMaterial(MODEL_COLORS.bodyDark),
    { position: [-0.42, -0.66, 0] }
  );
  for (const x of [-0.56, -0.28]) {
    addModelPart(
      ctx,
      geo.cylinder(0.03, 0.03, 0.04),
      createMetalMaterial(MODEL_COLORS.brass),
      { position: [x, -0.66, 0.16], rotation: [HALF_PI, 0, 0] }
    );
  }
};

export const buildWisenetCameraModel: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.72, 0.78, 0.16), createMetalMaterial(MODEL_COLORS.bodyLight), {
    position: [0, -0.5, 0],
  });
  for (let k = 0; k < 3; k += 1) {
    const angle = (k / 3) * Math.PI * 2 + 0.5;
    addModelPart(
      ctx,
      geo.cylinder(0.028, 0.028, 0.05),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [Math.cos(angle) * 0.62, -0.41, Math.sin(angle) * 0.62] }
    );
  }
  addModelPart(ctx, geo.torus(0.6, 0.035), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.4, 0],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(
    ctx,
    geo.hemisphere(0.58, 14, 7),
    createStateMaterial(MODEL_COLORS.bodyDark),
    { position: [0, -0.4, 0], scale: [1, 0.85, 1] }
  );
  addModelPart(ctx, geo.cylinder(0.3, 0.36, 0.12), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, -0.32, 0.1],
    rotation: [HALF_PI, 0, 0],
  });
  addModelPart(ctx, geo.sphere(0.19, 10, 8), createOwnedMaterial(MODEL_COLORS.obsidian), {
    position: [0, -0.3, 0.2],
  });
  addModelPart(ctx, geo.torus(0.17, 0.015, 6, 16), createGlossMaterial(MODEL_COLORS.cloud), {
    position: [0, -0.28, 0.37],
  });
  addModelPart(ctx, geo.cylinder(0.08, 0.08, 0.04), createGlassMaterial(), {
    position: [0, -0.28, 0.38],
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
  addLensAssembly(ctx, [0, 0.42, 0.35], 0.18, [HALF_PI, 0, 0], true);
  addModelPart(ctx, geo.sphere(0.09, 8, 6), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, 0.16, -0.06],
  });
  addModelPart(ctx, geo.torus(0.1, 0.02, 6, 14), createMetalMaterial(MODEL_COLORS.steel), {
    position: [0, -0.06, 0],
  });
  addModelPart(ctx, geo.cylinder(0.07, 0.085, 0.46), createOwnedMaterial(MODEL_COLORS.bodyMid), {
    position: [0, -0.16, 0],
  });
  addModelPart(ctx, geo.cylinder(0.12, 0.14, 0.06), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.4, 0],
  });
  addModelPart(ctx, geo.cylinder(0.38, 0.43, 0.12), createStateMaterial(MODEL_COLORS.white), {
    position: [0, -0.5, 0],
  });
  addModelPart(ctx, geo.cylinder(0.31, 0.33, 0.07), createOwnedMaterial(MODEL_COLORS.bodyDark), {
    position: [0, -0.59, 0],
  });
  addModelPart(ctx, geo.cylinder(0.25, 0.25, 0.04), createRubberMaterial(), {
    position: [0, -0.65, 0],
  });
};
