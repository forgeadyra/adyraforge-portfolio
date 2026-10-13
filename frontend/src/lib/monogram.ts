/**
 * AF monogram outlines in scene units (height 2, centred). Shared by the WebGL
 * hero and the static SVG poster so both show the identical silhouette.
 */
export type Point = readonly [number, number];

export const A_OUTER: Point[] = [
  [-1.2, -1],
  [-0.55, 1],
  [-0.15, 1],
  [0.5, -1],
  [0.1, -1],
  [-0.05, -0.45],
  [-0.65, -0.45],
  [-0.8, -1],
];
export const A_COUNTER: Point[] = [
  [-0.53, -0.1],
  [-0.17, -0.1],
  [-0.35, 0.55],
];
export const F_OUTER: Point[] = [
  [0.6, -1],
  [0.98, -1],
  [0.98, -0.12],
  [1.4, -0.12],
  [1.4, 0.24],
  [0.98, 0.24],
  [0.98, 0.62],
  [1.6, 0.62],
  [1.6, 1],
  [0.6, 1],
];
/** Horizontal offset that centres the pair. */
export const MONOGRAM_SHIFT_X = -0.2;
