// Coordinate mapping between the MuJoCo laboratory (backend/xzr/lab/physics.py) and the Three.js view.
//
// MuJoCo world: right-handed, z up, metres. A chamber record's `position` is [x, height, z] in view terms; physics uses
// its (position[0], position[2]) as the chamber centre in the MuJoCo x-y plane (physics.py `_xy`). Chamber floors are
// boxes whose top is at z = 0.05; samples rest at z = 0.05 + 0.15 (half size).
//
// View: Three.js, y up. The mapping is a fixed rigid transform with no scaling:
//     view = (x_phys, z_phys + PHYS_Y0, y_phys)          PHYS_Y0 = 0.25
// so a chamber floor top (z = 0.05) is drawn at view y = 0.30 (FLOOR_Y). Every physically simulated object (sample,
// tool tip, carriage, wall, floor, port) is placed by this function from its recorded or layout position, never by hand.
// The swap of y and z is a proper rotation composed with a reflection (x, y, z) -> (x, z, y); it is applied to
// positions only (samples are drawn axis-aligned: the record keeps positions, not orientations — see LIMITS below).

export const PHYS_Y0 = 0.25;
export const FLOOR_TOP_PHYS = 0.05;
export const FLOOR_Y = FLOOR_TOP_PHYS + PHYS_Y0;

export type V3 = [number, number, number];

export function physToView(p: V3): V3 {
  return [p[0], p[2] + PHYS_Y0, p[1]];
}

export function viewToPhys(v: V3): V3 {
  return [v[0], v[2], v[1] - PHYS_Y0];
}

/** Physics-plane point (x, y) at physics height z, in view coordinates. */
export function planeToView(xy: [number, number], z = FLOOR_TOP_PHYS): V3 {
  return physToView([xy[0], xy[1], z]);
}

/** Chamber centre on the floor, in view coordinates, from the chamber record (physics.py `_xy`). */
export function chamberFloor(position: V3): V3 {
  return planeToView([position[0], position[2]]);
}

/** Rendering-only interpolation between two recorded positions (the recorded trajectory stays authoritative). */
export function lerp3(a: V3, b: V3, f: number): V3 {
  const k = Math.min(1, Math.max(0, f));
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
}

// Constants of the MuJoCo model (physics.py) needed to draw its collision geometry at the right size.
export const PHYS = {
  CH: 1.3,  // chamber floor half size
  WALL_H: 0.7,  // chamber wall height
  WALL_T: 0.03,  // wall half thickness
  HALF: 0.15,  // sample half size
  PORT: 0.75,  // port table half size
  SAFE_Z: 1.4,  // travel height of the tool tip
  TIP_OFFSET: 0.3,  // tool tip below the carriage origin
  REACH: 7.5,  // slide range of each gantry axis from its bay centre
} as const;

// LIMITS of the mapping, stated so rendered detail is not read as simulation fidelity:
//  * the record stores sample positions, not orientations: samples are drawn axis-aligned;
//  * gantry carriages and tools have no collision geometry in MuJoCo (contype 0); their drawn housings are visual;
//  * the overhead rails, bridge and mast of a gantry represent its x, y and z slide joints (positions derived from the
//    recorded tool tip); MuJoCo models the joints, not rails.
