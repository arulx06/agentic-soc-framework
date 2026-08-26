import {
  Box3,
  BoxGeometry,
  ConeGeometry,
  CylinderGeometry,
  CapsuleGeometry,
  DodecahedronGeometry,
  Group,
  IcosahedronGeometry,
  Mesh,
  MeshBasicMaterial,
  OctahedronGeometry,
  SphereGeometry,
  Sphere,
  TetrahedronGeometry,
  TorusGeometry,
  Vector3,
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import type { BufferGeometry, Material } from "three";
import { isStateMaterial } from "./modelMaterials";
import type { ModelBounds, ModelBuildContext } from "./modelTypes";

export const CANONICAL_RADIUS = 1;
export const LABEL_MARGIN = 0.45;
export const MIN_LABEL_HEIGHT = 3.2;

const geometryCache = new Map<string, BufferGeometry>();

function cached<T extends BufferGeometry>(key: string, factory: () => T): T {
  let geometry = geometryCache.get(key);
  if (!geometry || geometry.userData.shared !== true) {
    geometry = factory();
    geometry.userData.shared = true;
    geometryCache.set(key, geometry);
  }
  return geometry as T;
}

export const geo = {
  sphere: (r = 1, ws = 18, hs = 12) =>
    cached(`sphere(${r},${ws},${hs})`, () => new SphereGeometry(r, ws, hs)),
  box: (w: number, h: number, d: number) =>
    cached(`box(${w},${h},${d})`, () => new BoxGeometry(w, h, d)),
  roundedBox: (w: number, h: number, d: number, radius = 0.05, seg = 2) =>
    cached(
      `rbox(${w},${h},${d},${radius},${seg})`,
      () => new RoundedBoxGeometry(w, h, d, seg, radius)
    ),
  cylinder: (rt = 0.5, rb = 0.5, h = 1, s = 16) =>
    cached(`cyl(${rt},${rb},${h},${s})`, () => new CylinderGeometry(rt, rb, h, s)),
  cone: (r = 0.5, h = 1, s = 16) =>
    cached(`cone(${r},${h},${s})`, () => new ConeGeometry(r, h, s)),
  octahedron: (r = 1, d = 0) =>
    cached(`oct(${r},${d})`, () => new OctahedronGeometry(r, d)),
  tetrahedron: (r = 1) =>
    cached(`tet(${r})`, () => new TetrahedronGeometry(r)),
  icosahedron: (r = 1, d = 0) =>
    cached(`ico(${r},${d})`, () => new IcosahedronGeometry(r, d)),
  dodecahedron: (r = 1) =>
    cached(`dod(${r})`, () => new DodecahedronGeometry(r)),
  capsule: (r = 0.5, len = 1, cs = 8, rs = 16) =>
    cached(`cap(${r},${len},${cs},${rs})`, () => new CapsuleGeometry(r, len, cs, rs)),
  torus: (r = 0.6, t = 0.08, rs = 8, ts = 24, arc?: number) =>
    cached(
      arc === undefined
        ? `torus(${r},${t},${rs},${ts})`
        : `torus(${r},${t},${rs},${ts},${arc})`,
      () =>
        arc === undefined
          ? new TorusGeometry(r, t, rs, ts)
          : new TorusGeometry(r, t, rs, ts, arc)
    ),
  hemisphere: (r = 0.5, ws = 14, hs = 8) =>
    cached(
      `hemi(${r},${ws},${hs})`,
      () => new SphereGeometry(r, ws, hs, 0, Math.PI * 2, 0, Math.PI / 2)
    ),
};

export function isSharedGeometry(geometry: BufferGeometry): boolean {
  return geometry.userData.shared === true;
}

export interface PartSpec {
  position?: [number, number, number];
  rotation?: [number, number, number];
  scale?: [number, number, number] | number;
}

export function addModelPart(
  ctx: ModelBuildContext,
  geometry: BufferGeometry,
  material: Material,
  spec: PartSpec = {},
  role?: "state" | "accent"
): Mesh {
  const mesh = new Mesh(geometry, material);
  if (spec.position) mesh.position.set(spec.position[0], spec.position[1], spec.position[2]);
  if (spec.rotation) mesh.rotation.set(spec.rotation[0], spec.rotation[1], spec.rotation[2]);
  if (spec.scale !== undefined) {
    if (typeof spec.scale === "number") mesh.scale.setScalar(spec.scale);
    else mesh.scale.set(spec.scale[0], spec.scale[1], spec.scale[2]);
  }
  ctx.content.add(mesh);
  const resolvedRole =
    role ?? (isStateMaterial(material) ? "state" : "accent");
  if (resolvedRole === "state") ctx.stateMeshes.push(mesh);
  else ctx.accentMeshes.push(mesh);
  return mesh;
}

const boundsBox = new Box3();
const boundsSphere = new Sphere();
const boundsCenter = new Vector3();

export function normalizeGroup(
  group: Group,
  targetRadius = CANONICAL_RADIUS
): ModelBounds {
  boundsBox.setFromObject(group);
  if (boundsBox.isEmpty()) return { radius: targetRadius, top: targetRadius };
  boundsBox.getBoundingSphere(boundsSphere);
  const rawRadius = boundsSphere.radius || 1;
  const scaleFactor = targetRadius / rawRadius;
  boundsBox.getCenter(boundsCenter);
  group.children.forEach((child) => {
    child.position.set(
      (child.position.x - boundsCenter.x) * scaleFactor,
      (child.position.y - boundsCenter.y) * scaleFactor,
      (child.position.z - boundsCenter.z) * scaleFactor
    );
    child.scale.multiplyScalar(scaleFactor);
  });
  return {
    radius: targetRadius,
    top: Math.max((boundsBox.max.y - boundsCenter.y) * scaleFactor, 0),
  };
}

export function createHaloMesh(
  color: string,
  modelRadius: number
): { mesh: Mesh; material: MeshBasicMaterial } {
  const radius = modelRadius * 1.22;
  const material = new MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.72,
  });
  const mesh = new Mesh(geo.torus(radius, 0.08, 8, 28), material);
  mesh.rotation.x = Math.PI / 2;
  return { mesh, material };
}

export function disposeObjectTree(root: Group) {
  root.traverse((object) => {
    const candidate = object as Mesh | { material?: unknown };
    const material = candidate.material as
      | (Material & { map?: { dispose(): void } })
      | undefined;
    if (material && typeof material.dispose === "function") {
      if (material.map) material.map.dispose();
      material.dispose();
    }
    if ((object as Mesh).isMesh) {
      const mesh = object as Mesh;
      if (mesh.geometry && !isSharedGeometry(mesh.geometry)) {
        mesh.geometry.dispose();
      }
    }
  });
  root.clear();
}
