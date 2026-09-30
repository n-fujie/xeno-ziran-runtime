// Monochrome base; hue only where it marks an operational distinction.
export type RGBA = [number, number, number, number];

export const C = {
  bg: [0, 0, 0, 255] as RGBA,
  land: [14, 14, 16, 255] as RGBA,
  landLine: [48, 48, 54, 255] as RGBA,
  edge: [200, 200, 205] as [number, number, number],
  gated: [110, 140, 190] as [number, number, number], // permeability reduced by a boundary
  transformEdge: [165, 150, 200] as [number, number, number],
  ignition: [255, 255, 255] as [number, number, number],
  penetration: [160, 225, 255] as [number, number, number],
  cut: [255, 92, 72] as [number, number, number],
  newConn: [120, 230, 150] as [number, number, number],
  reconf: [190, 140, 255] as [number, number, number],
  ret: [255, 190, 90] as [number, number, number],
  frozen: [90, 110, 150] as [number, number, number],
  selected: [255, 255, 255] as [number, number, number],
};

// low-saturation hues for the opaque difference forms (relation scale only)
export const FORMS: [number, number, number][] = [[200, 200, 200], [150, 190, 220], [210, 180, 150], [170, 205, 170],
  [200, 160, 200], [190, 190, 150], [150, 200, 200], [210, 160, 160]];

export const NODE_CLASS_COLOR: Record<number, [number, number, number]> = {
  1: [120, 230, 150], // newly reached
  2: [255, 92, 72], // no longer reached
  3: [255, 190, 90], // loop gained
  4: [150, 110, 220], // loop lost
  5: [160, 225, 255], // ignites more
  6: [80, 100, 150], // ignites less
};

export const EDGE_CLASS_COLOR: Record<number, [number, number, number]> = {
  1: [150, 110, 220], 2: [255, 92, 72], 3: [120, 230, 150], 4: [70, 130, 90], 5: [190, 140, 255], 6: [110, 80, 160],
  7: [110, 160, 230],
};
