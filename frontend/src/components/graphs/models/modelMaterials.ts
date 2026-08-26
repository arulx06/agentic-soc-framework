import { MeshBasicMaterial } from "three";
import type { Material, MeshBasicMaterial as MeshBasicMaterialType } from "three";

export const MODEL_COLORS = {
  bodyDark: "#243247",
  bodyMid: "#334155",
  bodyLight: "#475569",
  steel: "#94a3b8",
  white: "#e2e8f0",
  lensGlass: "#0ea5e9",
  copper: "#c2703d",
  brass: "#caa54a",
  green: "#34d399",
  teal: "#2dd4bf",
  amber: "#f59e0b",
  orange: "#f97316",
  red: "#ef4444",
  rose: "#fb7185",
  violet: "#8b5cf6",
  cloud: "#7dd3fc",
  pcb: "#166534",
  obsidian: "#111827",
  ember: "#f43f5e",
} as const;

export const STATE_OPACITY = 0.96;
export const STATE_DIMMED_OPACITY = 0.16;
export const ACCENT_DIMMED_OPACITY = 0.08;

export function createOwnedMaterial(
  color: string,
  opacity = 1
): MeshBasicMaterialType {
  return new MeshBasicMaterial({ color, transparent: true, opacity });
}

export function createStateMaterial(color: string): MeshBasicMaterialType {
  const material = createOwnedMaterial(color, STATE_OPACITY);
  material.userData.stateRole = true;
  return material;
}

export function isStateMaterial(material: Material): boolean {
  return material.userData?.stateRole === true;
}

export interface StateVisualInput {
  color: string;
  dimmed: boolean;
}

export function applyNodeVisualState(
  materials: MeshBasicMaterialType[],
  state: StateVisualInput
) {
  materials.forEach((material) => {
    material.color.set(state.color);
    material.opacity = state.dimmed ? STATE_DIMMED_OPACITY : STATE_OPACITY;
  });
}

export function applyAccentDimming(
  materials: MeshBasicMaterialType[],
  dimmed: boolean
) {
  materials.forEach((material) => {
    material.opacity = dimmed ? ACCENT_DIMMED_OPACITY : 1;
  });
}
