import {
  MODEL_COLORS,
  createOwnedMaterial,
  createStateMaterial,
} from "./modelMaterials";
import type { ModelBuilder } from "./modelTypes";
import { addModelPart, geo } from "./modelUtils";

const HALF_PI = Math.PI / 2;

export const buildAttacker0Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.octahedron(0.55, 0),
    createStateMaterial(MODEL_COLORS.obsidian),
    { position: [0, 0.05, 0], scale: [1, 1.3, 1] }
  );
  const fins: Array<[number, number, number, number, [number, number, number]]> = [
    [0.5, 0.05, 0.18, 0.4, [0.35, 0.3, 0.1]],
    [0.34, 0.05, 0.16, -0.9, [-0.3, -0.15, -0.15]],
    [0.26, 0.05, 0.14, 2.2, [-0.1, 0.5, -0.3]],
  ];
  fins.forEach(([w, h, d, yaw, pos]) => {
    addModelPart(
      ctx,
      geo.box(w, h, d),
      createOwnedMaterial(MODEL_COLORS.ember),
      {
        position: pos as [number, number, number],
        rotation: [0.2, yaw, 0],
      }
    );
  });
  addModelPart(ctx, geo.tetrahedron(0.13), createOwnedMaterial(MODEL_COLORS.rose), {
    position: [0.32, -0.48, 0.26],
    rotation: [0.7, 0.3, 0.5],
  });
};

export const buildAttacker1Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.icosahedron(0.48, 0),
    createStateMaterial(MODEL_COLORS.obsidian),
    {}
  );
  const spikeDirs: Array<[number, number, number, [number, number, number]]> = [
    [0.56, 0, 0, [0, 0, HALF_PI]],
    [-0.56, 0, 0, [0, 0, -HALF_PI]],
    [0, 0.56, 0, [0, 0, 0]],
    [0, -0.56, 0, [Math.PI, 0, 0]],
    [0, 0, 0.56, [HALF_PI, 0, 0]],
    [0, 0, -0.56, [-HALF_PI, 0, 0]],
    [0.42, 0.42, 0, [0, 0, 0.78]],
    [-0.42, -0.42, 0, [Math.PI, 0, -0.78]],
  ];
  spikeDirs.forEach(([x, y, z, rot]) => {
    addModelPart(
      ctx,
      geo.cone(0.08, 0.28, 6),
      createOwnedMaterial(MODEL_COLORS.ember),
      { position: [x, y, z], rotation: rot }
    );
  });
};

export const buildAttacker2Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.box(0.62, 0.62, 0.62),
    createStateMaterial(MODEL_COLORS.obsidian),
    { rotation: [0.2, 0.5, 0.1] }
  );
  const fragments: Array<[number, [number, number, number], [number, number, number]]> = [
    [0.2, [0.58, 0.36, 0.12], [0.4, 0.3, 0.2]],
    [-0.52, [0.4, -0.45, 0.3], [0.8, 0.2, 0.4]],
    [-0.46, [-0.5, 0.42, -0.2], [0.3, 0.9, 0.1]],
    [-0.38, [0.34, -0.56, -0.34], [1.1, 0.4, 0.6]],
  ];
  fragments.forEach(([size, pos, rot]) => {
    addModelPart(
      ctx,
      size > 0.18 ? geo.box(size, size, size) : geo.tetrahedron(0.14),
      createOwnedMaterial(size > 0.18 ? MODEL_COLORS.ember : MODEL_COLORS.rose),
      { position: pos as [number, number, number], rotation: rot as [number, number, number] }
    );
  });
};

export const buildAttacker3Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.tetrahedron(0.6),
    createStateMaterial(MODEL_COLORS.obsidian),
    { rotation: [0.35, 0.6, 0] }
  );
  addModelPart(
    ctx,
    geo.tetrahedron(0.28),
    createOwnedMaterial(MODEL_COLORS.ember),
    { rotation: [-0.35, -0.6, 0.4] }
  );
  addModelPart(
    ctx,
    geo.torus(0.72, 0.03, 6, 24),
    createOwnedMaterial(MODEL_COLORS.ember),
    { position: [0, 0.05, 0], rotation: [1.15, 0.25, 0] }
  );
  addModelPart(ctx, geo.sphere(0.08, 6, 6), createOwnedMaterial(MODEL_COLORS.rose), {
    position: [0.68, 0.28, 0.12],
  });
};

export const buildAttacker4Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.dodecahedron(0.44),
    createStateMaterial(MODEL_COLORS.obsidian),
    {}
  );
  for (let k = 0; k < 6; k += 1) {
    const angle = (k / 6) * Math.PI * 2;
    addModelPart(
      ctx,
      geo.box(0.09, 0.24, 0.09),
      createOwnedMaterial(MODEL_COLORS.ember),
      { position: [Math.cos(angle) * 0.56, 0, Math.sin(angle) * 0.56] }
    );
  }
  for (const y of [-0.14, 0.14]) {
    addModelPart(
      ctx,
      geo.torus(0.5, 0.04, 6, 20),
      createOwnedMaterial(MODEL_COLORS.bodyLight),
      { position: [0, y, 0], rotation: [HALF_PI, 0, 0] }
    );
  }
};

export const buildAttacker5Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.octahedron(0.4, 0),
    createStateMaterial(MODEL_COLORS.obsidian),
    { scale: [0.85, 1.7, 0.85] }
  );
  addModelPart(
    ctx,
    geo.torus(0.55, 0.025, 6, 24),
    createOwnedMaterial(MODEL_COLORS.violet),
    { rotation: [1.35, 0, 0.2] }
  );
  addModelPart(
    ctx,
    geo.torus(0.74, 0.022, 6, 24),
    createOwnedMaterial(MODEL_COLORS.ember),
    { rotation: [1.05, 0, -0.35] }
  );
  for (const [x, y, z] of [
    [0.62, 0.3, -0.2],
    [-0.55, -0.35, 0.25],
    [0.1, 0.55, 0.55],
  ]) {
    addModelPart(
      ctx,
      geo.tetrahedron(0.1),
      createOwnedMaterial(MODEL_COLORS.rose),
      { position: [x, y, z], rotation: [0.5, 0.7, 0.2] }
    );
  }
};
