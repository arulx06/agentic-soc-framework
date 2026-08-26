import {
  MODEL_COLORS,
  createGlossMaterial,
  createMetalMaterial,
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
  addModelPart(
    ctx,
    geo.octahedron(0.4, 0),
    createMetalMaterial(MODEL_COLORS.bodyLight),
    { position: [0, 0.05, 0], scale: [1.05, 1.05, 1.05], rotation: [0, 0.55, 0] }
  );
  addModelPart(ctx, geo.dodecahedron(0.16), createGlossMaterial(MODEL_COLORS.ember), {
    position: [0, 0.32, 0.28],
  });
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
    addModelPart(
      ctx,
      geo.box(w * 0.4, h + 0.03, d * 1.4),
      createMetalMaterial(MODEL_COLORS.bodyDark),
      {
        position: [(pos as [number, number, number])[0] * 0.72, (pos as [number, number, number])[1] * 0.72, (pos as [number, number, number])[2] * 0.72],
        rotation: [0.2, yaw, 0],
      }
    );
  });
  addModelPart(ctx, geo.tetrahedron(0.13), createGlossMaterial(MODEL_COLORS.rose), {
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
  addModelPart(
    ctx,
    geo.torus(0.49, 0.03, 6, 24),
    createMetalMaterial(MODEL_COLORS.bodyLight),
    { rotation: [HALF_PI, 0, 0.3] }
  );
  const spikeDirs: Array<[number, number, number, [number, number, number]]> = [
    [0.56, 0, 0, [0, 0, HALF_PI]],
    [-0.56, 0, 0, [0, 0, -HALF_PI]],
    [0, 0.56, 0, [0, 0, 0]],
    [0, -0.56, 0, [Math.PI, 0, 0]],
    [0, 0, 0.56, [HALF_PI, 0, 0]],
    [0, 0, -0.56, [-HALF_PI, 0, 0]],
  ];
  spikeDirs.forEach(([x, y, z, rot]) => {
    addModelPart(
      ctx,
      geo.cylinder(0.075, 0.095, 0.08),
      createMetalMaterial(MODEL_COLORS.bodyDark),
      { position: [x * 0.88, y * 0.88, z * 0.88], rotation: rot }
    );
    addModelPart(
      ctx,
      geo.cone(0.08, 0.26, 6),
      createOwnedMaterial(MODEL_COLORS.ember),
      {
        position: [x * 1.06, y * 1.06, z * 1.06],
        rotation: rot,
      }
    );
  });
};

export const buildAttacker2Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.roundedBox(0.5, 0.5, 0.5, 0.04),
    createStateMaterial(MODEL_COLORS.obsidian),
    { rotation: [0.2, 0.5, 0.1] }
  );
  addModelPart(
    ctx,
    geo.roundedBox(0.34, 0.34, 0.34, 0.03),
    createMetalMaterial(MODEL_COLORS.bodyDark),
    { rotation: [0.2, 0.5, 0.1] }
  );
  addModelPart(ctx, geo.icosahedron(0.17, 0), createGlossMaterial(MODEL_COLORS.ember), {});
  const fragments: Array<[number, [number, number, number], [number, number, number]]> = [
    [0.2, [0.62, 0.42, 0.14], [0.4, 0.3, 0.2]],
    [-0.52, [0.46, -0.5, 0.34], [0.8, 0.2, 0.4]],
    [-0.46, [-0.56, 0.46, -0.22], [0.3, 0.9, 0.1]],
    [-0.38, [0.38, -0.6, -0.38], [1.1, 0.4, 0.6]],
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
    geo.tetrahedron(0.68),
    createStateMaterial(MODEL_COLORS.obsidian),
    { rotation: [0.35, 0.6, 0] }
  );
  const capDirs: Array<[number, number, number]> = [
    [0, 0.68, 0],
    [0.64, -0.34, 0.37],
    [-0.64, -0.34, 0.37],
    [0, -0.34, -0.74],
  ];
  capDirs.forEach(([x, y, z]) => {
    addModelPart(
      ctx,
      geo.sphere(0.07, 8, 6),
      createMetalMaterial(MODEL_COLORS.steel),
      { position: [x * 0.96, y * 0.96, z * 0.96] }
    );
  });
  addModelPart(
    ctx,
    geo.tetrahedron(0.3),
    createGlossMaterial(MODEL_COLORS.ember),
    { rotation: [-0.35, -0.6, 0.4] }
  );
  addModelPart(
    ctx,
    geo.torus(0.74, 0.028, 6, 24),
    createMetalMaterial(MODEL_COLORS.steel),
    { position: [0, 0.05, 0], rotation: [1.15, 0.25, 0] }
  );
  addModelPart(ctx, geo.sphere(0.08, 6, 6), createGlossMaterial(MODEL_COLORS.rose), {
    position: [0.7, 0.3, 0.12],
  });
};

export const buildAttacker4Model: ModelBuilder = (ctx) => {
  addModelPart(ctx, geo.cylinder(0.3, 0.3, 0.5), createStateMaterial(MODEL_COLORS.obsidian), {});
  addModelPart(ctx, geo.cylinder(0.36, 0.36, 0.08), createMetalMaterial(MODEL_COLORS.bodyLight), {
    position: [0, 0.29, 0],
  });
  addModelPart(ctx, geo.cylinder(0.36, 0.36, 0.08), createMetalMaterial(MODEL_COLORS.bodyLight), {
    position: [0, -0.29, 0],
  });
  for (let k = 0; k < 6; k += 1) {
    const angle = (k / 6) * Math.PI * 2;
    const x = Math.cos(angle);
    const z = Math.sin(angle);
    addModelPart(
      ctx,
      geo.roundedBox(0.13, 0.26, 0.13, 0.025),
      createOwnedMaterial(MODEL_COLORS.ember),
      { position: [x * 0.58, 0, z * 0.58], rotation: [0, -angle + HALF_PI, 0] }
    );
    addModelPart(
      ctx,
      geo.box(0.05, 0.1, 0.05),
      createMetalMaterial(MODEL_COLORS.bodyDark),
      { position: [x * 0.42, 0, z * 0.42] }
    );
  }
};

export const buildAttacker5Model: ModelBuilder = (ctx) => {
  addModelPart(
    ctx,
    geo.octahedron(0.42, 0),
    createStateMaterial(MODEL_COLORS.obsidian),
    { scale: [0.85, 1.35, 0.85] }
  );
  addModelPart(
    ctx,
    geo.octahedron(0.24, 0),
    createGlossMaterial(MODEL_COLORS.ember),
    { scale: [0.85, 1.9, 0.85] }
  );
  addModelPart(
    ctx,
    geo.torus(0.55, 0.024, 6, 24),
    createMetalMaterial(MODEL_COLORS.violet),
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
      createGlossMaterial(MODEL_COLORS.rose),
      { position: [x, y, z], rotation: [0.5, 0.7, 0.2] }
    );
  }
};
