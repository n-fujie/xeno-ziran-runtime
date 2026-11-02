import * as THREE from 'three';
import type { Arena } from './megastructure';
import type { Frame } from './meosApi';
import { COUPLINGS, couplingDef, type CouplingId, type CouplingState } from './couplings';

// XENOSCIENCE ECOSYSTEM — the coupling layer of the 3D scene. Each of the four couplings is one pickable mesh whose state (connected, cut, unrecorded) is the record's, and which is placed between the
// recorded positions of the two operational configurations. The heights at which the four are drawn, and the lift of the exploded view, are SCHEMATIC layout offsets: they separate objects that would
// otherwise overlap and are not physical dimensions. Nothing here changes a run: a display operation (isolate, explode, baseline marker) only changes what is drawn.

export interface CouplingFrame {
  frame: Frame; states: Record<CouplingId, CouplingState>; selected: CouplingId | null;
  /** draw only this coupling (a display operation) */
  isolated: CouplingId | null;
  /** 0 = assembled, 1 = exploded: the layers are separated by a schematic vertical offset */
  exploded: number;
  /** the positions of the baseline branch at the same tick, drawn as markers */
  baseline: Record<'A1' | 'A2', { x: number; y: number; present: boolean }> | null;
}
export interface CouplingLayer {
  group: THREE.Group; pickables: THREE.Mesh[]; set(c: CouplingFrame): void; meshOf(id: CouplingId): THREE.Mesh; baselineMarkers: Record<'A1' | 'A2', THREE.Mesh>; dispose(): void;
}

const HEIGHT: Record<CouplingId, number> = { interaction_channel: 1.5, feedback: 2.3, sensor_resource: 0.9, sensor_alteration: 0.9 };
const LIFT = { couplings: 3.2, entities: 1.6 };
const MIN_LENGTH = 1.4;  // a coupling between two configurations in the same cell is still drawn, so that it can be seen and picked
const LATERAL = 0.55;  // schematic sideways offsets that keep the four couplings apart when the configurations coincide
const GROUND = 0.06;  // the height at which arena.setFrame places an entity
const COLOR = { connected: 0x9db4c8, cut: 0xd9534f, unrecorded: 0x6b7280, selected: 0xffffff, baseline: 0xe0a030 };

export function buildCouplingLayer(arena: Arena): CouplingLayer {
  const group = new THREE.Group(); group.name = 'couplings';
  const unit = new THREE.CylinderGeometry(1, 1, 1, 10), head = new THREE.ConeGeometry(1, 1, 10), ring = new THREE.TorusGeometry(1.3, 0.05, 8, 28);
  const owned: Array<THREE.BufferGeometry | THREE.Material> = [unit, head, ring];
  const meshes = {} as Record<CouplingId, THREE.Mesh>, heads = {} as Record<CouplingId, THREE.Mesh>, pickables: THREE.Mesh[] = [];
  for (const c of COUPLINGS) {
    const mat = new THREE.MeshStandardMaterial({ color: COLOR.connected, emissive: 0x000000, roughness: 0.5, metalness: 0.1, transparent: true });
    const hmat = mat.clone(); owned.push(mat, hmat);
    const body = new THREE.Mesh(unit, mat), tip = new THREE.Mesh(head, hmat);
    body.userData = tip.userData = { coupling: c.id }; body.name = `coupling:${c.id}`; tip.name = `coupling-head:${c.id}`;
    group.add(body, tip); meshes[c.id] = body; heads[c.id] = tip; pickables.push(body, tip);
  }
  const bm = {} as Record<'A1' | 'A2', THREE.Mesh>;
  for (const k of ['A1', 'A2'] as const) {
    const mat = new THREE.MeshBasicMaterial({ color: COLOR.baseline, transparent: true, opacity: 0.8, depthWrite: false }); owned.push(mat);
    const m = new THREE.Mesh(ring, mat); m.rotation.x = Math.PI / 2; m.visible = false; m.name = `baseline-marker:${k}`; group.add(m); bm[k] = m;
  }
  arena.group.add(group);

  const from = new THREE.Vector3(), to = new THREE.Vector3(), dir = new THREE.Vector3(), mid = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), q = new THREE.Quaternion();
  const segment = (body: THREE.Mesh, tip: THREE.Mesh, a: THREE.Vector3, b: THREE.Vector3, radius: number): void => {
    dir.subVectors(b, a); const len = Math.max(MIN_LENGTH, dir.length());
    if (dir.lengthSq() < 1e-8) dir.set(1, 0, 0); else dir.normalize();  // two configurations in one cell: the coupling is drawn along a fixed schematic direction
    q.setFromUnitVectors(up, dir);
    const tipLen = Math.min(0.9, len * 0.35), bodyLen = Math.max(0.05, len - tipLen);
    mid.copy(a).addScaledVector(dir, bodyLen / 2); body.position.copy(mid); body.quaternion.copy(q); body.scale.set(radius, bodyLen, radius);
    mid.copy(a).addScaledVector(dir, bodyLen + tipLen / 2); tip.position.copy(mid); tip.quaternion.copy(q); tip.scale.set(radius * 2.4, tipLen, radius * 2.4);
  };

  const set = (c: CouplingFrame): void => {
    const e = Math.max(0, Math.min(1, c.exploded)), a1 = c.frame.A1, a2 = c.frame.A2;
    const p1 = arena.local(a1.x, a1.y), p2 = arena.local(a2.x, a2.y);
    // the entity groups are placed by arena.setFrame at ground level; the exploded view raises them (a display offset)
    arena.entities.A1.position.y = GROUND + LIFT.entities * e; arena.entities.A2.position.y = GROUND + LIFT.entities * e;
    for (const def of COUPLINGS) {
      const body = meshes[def.id], tip = heads[def.id], state = c.states[def.id];
      const endpoints = a1.present && a2.present;
      const visible = (c.isolated === null || c.isolated === def.id) && (def.id === 'sensor_resource' ? a1.present : def.id === 'sensor_alteration' ? a2.present : endpoints);
      body.visible = tip.visible = visible;
      if (!visible) continue;
      const lift = LIFT.couplings * e, h = HEIGHT[def.id] + lift;
      if (def.id === 'interaction_channel') { from.set(p1.x, h, p1.z - LATERAL); to.set(p2.x, h, p2.z - LATERAL); }
      else if (def.id === 'feedback') { from.set(p2.x, h, p2.z + LATERAL); to.set(p1.x, h, p1.z + LATERAL); }
      else { const p = def.id === 'sensor_resource' ? p1 : p2, sx = def.id === 'sensor_resource' ? 1.2 : -1.2; from.set(p.x + sx, 0.15 + lift, p.z + 1.1); to.set(p.x + sx, h, p.z + 1.1); }
      const selected = c.selected === def.id;
      segment(body, tip, from, to, (state === 'cut' ? 0.05 : 0.09) * (selected ? 1.9 : 1));
      for (const m of [body, tip]) {
        const mat = m.material as THREE.MeshStandardMaterial;
        mat.color.set(state === 'cut' ? COLOR.cut : state === 'unrecorded' ? COLOR.unrecorded : COLOR.connected);
        mat.emissive.set(selected ? COLOR.selected : state === 'cut' ? COLOR.cut : 0x000000); mat.emissiveIntensity = selected ? 0.55 : state === 'cut' ? 0.8 : 0;
        mat.opacity = state === 'cut' ? 0.4 : 1;
      }
    }
    for (const k of ['A1', 'A2'] as const) {
      const b = c.baseline?.[k], m = bm[k];
      m.visible = !!b && b.present;
      if (b && b.present) { const p = arena.local(b.x, b.y); m.position.set(p.x, 0.12 + LIFT.entities * e, p.z); }
    }
  };
  const dispose = (): void => { group.removeFromParent(); for (const o of owned) o.dispose(); };
  return { group, pickables, set, meshOf: (id) => meshes[id], baselineMarkers: bm, dispose };
}

export const couplingOfObject = (o: THREE.Object3D | undefined): CouplingId | null => {
  const id = (o?.userData as { coupling?: CouplingId } | undefined)?.coupling;
  return id && COUPLINGS.some((c) => c.id === id) ? couplingDef(id).id : null;
};
