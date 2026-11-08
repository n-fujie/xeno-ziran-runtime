import * as THREE from 'three';
import { EDGES, NODES, PATHS, RELATIONS, nodeValue, relationAt, stepReached, type NodeId, type PathId, type RelationId, type TERun } from './truthError';

// TRUTH-ERROR DYNAMICS in the 3D scene: the operational chain (subject -> sensors -> classifier / warrant -> acceptance -> score -> gates -> resources -> subject) as selectable objects. The brightness of every object is a
// plain function of the engine's record of ONE sample subject at ONE period (``nodeValue``); the positions are SCHEMATIC layout coordinates, not physical ones. Each object carries two small markers, the baseline run's value
// and the branch's, so that the two can be seen together. The pose frames are an abstract axis frame (three arrows), not a face: they show the reference pose and the pose a sensor measured, as rotations of that frame.
// The four PATHS (judgement, effect, correction, subsequent) are drawn along the edges of the chain, one coloured line per step that is a transition on an edge, for the baseline and (a little below) the branch. A segment is lit
// when that step holds for the selected subject at the selected period (``stepReached``: a variable or event the engine recorded); a segment that is not lit is dark. A line is never drawn for a step the model has no transition for.
// SYNTHETIC only: no real person is represented.

export interface TruthFrame { run: TERun; branch: TERun | null; k: number; t: number; selected: NodeId | null; relation?: RelationId | null }
export interface TruthLayer {
  group: THREE.Group; pickables: THREE.Mesh[]; meshOf(id: NodeId): THREE.Mesh; poseRef: THREE.Group; poseMeasured: THREE.Group; edgeLines: THREE.LineSegments; set(f: TruthFrame): void; dispose(): void;
  pathLines: THREE.LineSegments; pathLinesBranch: THREE.LineSegments; pathSegments: PathSegment[]; relationLines: THREE.LineSegments; targetBar: THREE.Mesh; labelShiftMarker: THREE.Mesh;
}
export const RELATION_COLORS = { holds: 0x4caf50, fails: 0xe53935, open: 0xdddddd } as const;
/** The height of the bar beside the subject is the model's own |state - counterfactual state| (capped for display at 3 and scaled by this); the marker above it is lit when the subject's current label differs from its counterfactual label. Both are read from the record, not animated. */
export const TARGET_BAR_UNIT = 0.9;
export interface PathSegment { path: PathId; step: string; edge: [NodeId, NodeId] }
export const PATH_COLORS: Record<PathId, number> = { judgement: 0xe0a030, effect: 0xd9534f, correction: 0x35b6a8, subsequent: 0x9b7fe0 };
const DARK = new THREE.Color(0x23282e);

const SHAPE: Record<string, () => THREE.BufferGeometry> = {
  state: () => new THREE.SphereGeometry(0.55, 20, 14), sensor: () => new THREE.ConeGeometry(0.5, 1.0, 16), rule: () => new THREE.OctahedronGeometry(0.62), institution: () => new THREE.BoxGeometry(0.95, 0.95, 0.95),
  store: () => new THREE.CylinderGeometry(0.5, 0.5, 0.9, 20), effect: () => new THREE.IcosahedronGeometry(0.58),  // solid: a shape with a hole would miss a click at its centre
};
const UNIT = 1.25;  // world units per layout unit (schematic)
const rad = (d: number) => (d * Math.PI) / 180;

/** The pose frame: three arrows along the axes of a frame, drawn in the scene as the rotation of a head's axes (yaw about the vertical axis, pitch about the lateral, roll about the frontal; order YXZ). */
function poseFrame(color: number, opacity: number, owned: Array<THREE.BufferGeometry | THREE.Material>): THREE.Group {
  const g = new THREE.Group(), mat = new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, depthWrite: opacity >= 1 });
  const shaft = new THREE.CylinderGeometry(0.04, 0.04, 1, 8), head = new THREE.ConeGeometry(0.11, 0.28, 10);
  owned.push(shaft, head, mat);
  const arrow = (dir: THREE.Vector3, len: number): void => {
    const a = new THREE.Group(), s = new THREE.Mesh(shaft, mat), h = new THREE.Mesh(head, mat);
    s.scale.y = len; s.position.y = len / 2; h.position.y = len + 0.14; a.add(s, h);
    a.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    g.add(a);
  };
  arrow(new THREE.Vector3(0, 1, 0), 1.0);   // the vertical axis (yaw turns about it)
  arrow(new THREE.Vector3(1, 0, 0), 0.8);   // the lateral axis (pitch turns about it)
  arrow(new THREE.Vector3(0, 0, 1), 0.9);   // the frontal axis (roll turns about it)
  return g;
}

export function buildTruthLayer(parent: THREE.Object3D, centre: THREE.Vector3, span: number): TruthLayer {
  const group = new THREE.Group(); group.name = 'truth-error';
  const owned: Array<THREE.BufferGeometry | THREE.Material> = [];
  const scale = span / (18 * UNIT);
  group.position.copy(centre); group.scale.setScalar(scale);
  const meshes = {} as Record<NodeId, THREE.Mesh>, pickables: THREE.Mesh[] = [], pips = {} as Record<NodeId, [THREE.Mesh, THREE.Mesh]>;
  const pipGeo = new THREE.SphereGeometry(0.13, 10, 8); owned.push(pipGeo);
  for (const n of NODES) {
    const geo = SHAPE[n.kind](), mat = new THREE.MeshStandardMaterial({ color: 0xb8c4d0, emissive: 0xffffff, emissiveIntensity: 0.2, roughness: 0.5, metalness: 0.1 });
    owned.push(geo, mat);
    const m = new THREE.Mesh(geo, mat); m.position.set((n.x - 9) * UNIT, n.y * UNIT, 0); m.userData = { teNode: n.id }; m.name = `truth-node:${n.id}`;
    const pm = [new THREE.Mesh(pipGeo, new THREE.MeshBasicMaterial({ color: 0x666666 })), new THREE.Mesh(pipGeo, new THREE.MeshBasicMaterial({ color: 0x666666 }))] as [THREE.Mesh, THREE.Mesh];
    pm[0].position.set(-0.22, 0.85, 0); pm[1].position.set(0.22, 0.85, 0); pm.forEach((p) => { owned.push(p.material as THREE.Material); p.visible = false; m.add(p); });
    pips[n.id] = pm; group.add(m); meshes[n.id] = m; pickables.push(m);
  }
  // the edges of the chain (a straight line each; the feedback to the subject crosses the whole chain)
  const pts: number[] = [];
  for (const [a, b] of EDGES) { const pa = meshes[a].position, pb = meshes[b].position; pts.push(pa.x, pa.y, pa.z, pb.x, pb.y, pb.z); }
  const eg = new THREE.BufferGeometry(); eg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  const em = new THREE.LineBasicMaterial({ color: 0x8a94a0, transparent: true, opacity: 0.55 }); owned.push(eg, em);
  const edgeLines = new THREE.LineSegments(eg, em); group.add(edgeLines);
  // the four paths: one segment per step that is a transition on an edge, drawn beside the edge (offset by path) for the baseline and a little lower for the branch
  const pathSegments: PathSegment[] = [], ppts: number[] = [], pBranch: number[] = [];
  PATHS.forEach((p, pi) => p.steps.forEach((st) => {
    if (!st.edge) return;
    pathSegments.push({ path: p.id, step: st.id, edge: st.edge });
    const a = meshes[st.edge[0]].position, b = meshes[st.edge[1]].position, z = (pi - 1.5) * 0.16;
    ppts.push(a.x, a.y, a.z + z, b.x, b.y, b.z + z); pBranch.push(a.x, a.y - 0.2, a.z + z, b.x, b.y - 0.2, b.z + z);
  }));
  const mkLines = (pts: number[]): THREE.LineSegments => {
    const g = new THREE.BufferGeometry(), m = new THREE.LineBasicMaterial({ vertexColors: true });
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(new Array(pts.length).fill(0.15), 3)); owned.push(g, m);
    const l = new THREE.LineSegments(g, m); group.add(l); return l;
  };
  const pathLines = mkLines(ppts), pathLinesBranch = mkLines(pBranch);
  pathLinesBranch.visible = false;
  // the selected relation: its edges drawn in front of the chain, green where the engine's record satisfies the model's own transition rule at this period, red where it does not, white where there is no identity to check
  const rg = new THREE.BufferGeometry(), rm = new THREE.LineBasicMaterial({ color: RELATION_COLORS.open, depthTest: false }); owned.push(rg, rm);
  rg.setAttribute('position', new THREE.Float32BufferAttribute(new Array(2 * 2 * 3).fill(0), 3));
  const relationLines = new THREE.LineSegments(rg, rm); relationLines.renderOrder = 10; relationLines.visible = false; relationLines.name = 'truth-relation'; group.add(relationLines);
  // the pose frames, beside the subject: the reference (solid) and the measured (translucent)
  const poseRef = poseFrame(0xe8e8ee, 1, owned), poseMeasured = poseFrame(0xe0a030, 0.6, owned);
  poseRef.position.set(meshes.subject.position.x - 1.9, meshes.subject.position.y + 0.2, 0); poseMeasured.position.copy(poseRef.position); poseMeasured.scale.setScalar(1.12);
  group.add(poseRef, poseMeasured);
  // CHANGED TARGET and LABEL SHIFT, from the record of the selected subject: a bar the height of |z - z counterfactual| and a marker for a shifted label
  const barGeo = new THREE.BoxGeometry(0.18, 1, 0.18); barGeo.translate(0, 0.5, 0);
  const barMat = new THREE.MeshBasicMaterial({ color: 0xb0b8c4 }), mkGeo = new THREE.OctahedronGeometry(0.2), mkMat = new THREE.MeshBasicMaterial({ color: 0xf0a030 }); owned.push(barGeo, barMat, mkGeo, mkMat);
  const targetBar = new THREE.Mesh(barGeo, barMat), labelShiftMarker = new THREE.Mesh(mkGeo, mkMat);
  targetBar.name = 'truth-target-bar'; labelShiftMarker.name = 'truth-label-shift';
  targetBar.position.set(meshes.subject.position.x, meshes.subject.position.y - 1.9, 0); labelShiftMarker.position.set(meshes.subject.position.x, meshes.subject.position.y + 1.35, 0);
  targetBar.visible = false; labelShiftMarker.visible = false; group.add(targetBar, labelShiftMarker);
  parent.add(group);

  const colorOf = (v: number | null): THREE.Color => (v === null ? new THREE.Color(0x444444) : new THREE.Color().setHSL(0.58, 0.18, 0.12 + 0.6 * v));
  const set = (f: TruthFrame): void => {
    const rec = f.run.records[f.k][Math.max(0, Math.min(f.t, f.run.records[f.k].length - 1))];
    const bRec = f.branch ? f.branch.records[f.k][Math.max(0, Math.min(f.t, f.branch.records[f.k].length - 1))] : null;
    for (const n of NODES) {
      const m = meshes[n.id], mat = m.material as THREE.MeshStandardMaterial, v = nodeValue(n.id, rec);
      mat.color.copy(colorOf(v)); mat.emissive.copy(colorOf(v)); mat.emissiveIntensity = f.selected === n.id ? 0.9 : 0.25;
      m.scale.setScalar(f.selected === n.id ? 1.3 : 1);
      const [pb, pr] = pips[n.id];
      pb.visible = pr.visible = !!bRec;
      if (bRec) { (pb.material as THREE.MeshBasicMaterial).color.copy(colorOf(v)); (pr.material as THREE.MeshBasicMaterial).color.copy(colorOf(nodeValue(n.id, bRec))); }
    }
    // a binding constraint is shown as the gate turned a quarter (a display mark, not a physical rotation)
    meshes.gate_a.rotation.y = rec.locked ? Math.PI / 4 : 0;
    const e = (g: THREE.Group, p: number[] | Array<number | null>): void => {
      if (p.some((x) => x === null)) { g.visible = false; return; }
      g.visible = true; g.rotation.set(rad(p[1] as number), rad(p[0] as number), rad(p[2] as number), 'YXZ');  // yaw about Y, pitch about X, roll about Z
    };
    e(poseRef, rec.pose_reference); e(poseMeasured, rec.pose_measured);
    const paint = (lines: THREE.LineSegments, run: TERun | null): void => {
      lines.visible = !!run; if (!run) return;
      const col = lines.geometry.getAttribute('color') as THREE.BufferAttribute;
      pathSegments.forEach((sg, i) => {
        const step = PATHS.find((p) => p.id === sg.path)!.steps.find((x) => x.id === sg.step)!, c = stepReached(run, f.k, step, f.t) ? new THREE.Color(PATH_COLORS[sg.path]) : DARK;
        col.setXYZ(i * 2, c.r, c.g, c.b); col.setXYZ(i * 2 + 1, c.r, c.g, c.b);
      });
      col.needsUpdate = true;
    };
    paint(pathLines, f.run); paint(pathLinesBranch, f.branch);
    const tc = rec.z_counterfactual === undefined ? null : Math.abs(rec.reference_z - rec.z_counterfactual);
    targetBar.visible = tc !== null; targetBar.scale.y = (tc === null ? 0 : Math.min(3, tc)) * TARGET_BAR_UNIT + 0.001;
    labelShiftMarker.visible = rec.label_counterfactual !== undefined && rec.verification_label !== rec.label_counterfactual;
    const rel = f.relation ? RELATIONS.find((r) => r.id === f.relation) : undefined;
    relationLines.visible = !!rel;
    if (rel) {
      const pos = rg.getAttribute('position') as THREE.BufferAttribute;
      rel.edges.forEach(([a, b], j) => { const pa = meshes[a].position, pb = meshes[b].position; pos.setXYZ(j * 2, pa.x, pa.y, pa.z + 0.35); pos.setXYZ(j * 2 + 1, pb.x, pb.y, pb.z + 0.35); });
      pos.needsUpdate = true; rg.setDrawRange(0, rel.edges.length * 2);
      const holds = relationAt(f.run, f.k, f.t, rel.id).check.holds;
      rm.color.setHex(holds === true ? RELATION_COLORS.holds : holds === false ? RELATION_COLORS.fails : RELATION_COLORS.open);
    }
  };
  const dispose = (): void => { group.removeFromParent(); for (const o of owned) o.dispose(); for (const m of Object.values(meshes)) for (const c of m.children) ((c as THREE.Mesh).material as THREE.Material | undefined)?.dispose(); };
  return { group, pickables, meshOf: (id) => meshes[id], poseRef, poseMeasured, edgeLines, set, dispose, pathLines, pathLinesBranch, pathSegments, relationLines, targetBar, labelShiftMarker };
}

export const teNodeOf = (o: THREE.Object3D | undefined): NodeId | null => {
  const id = (o?.userData as { teNode?: NodeId } | undefined)?.teNode;
  return id && NODES.some((n) => n.id === id) ? id : null;
};
