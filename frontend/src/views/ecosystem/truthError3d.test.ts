// TRUTH-ERROR DYNAMICS in the 3D scene — the mapping from the engine's record to the objects (brightness, pose rotation, markers, the mark of a binding constraint), picking, and the release of resources. Real engine
// runs (truth-error-runs.json); three.js runs in node. SYNTHETIC only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { EDGES, NODES, PATHS, RELATIONS, nodeValue, relationAt, stepReached, type NodeId, type TERun } from './truthError';
import { PATH_COLORS, RELATION_COLORS, TARGET_BAR_UNIT, buildTruthLayer, teNodeOf } from './truthError3d';

const runs = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'truth-error-runs.json'), 'utf8')) as Record<'base' | 'invalid' | 'biased' | 'noscore', TERun>;
const { base, invalid, biased } = runs;
const runs2 = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'truth-error-runs2.json'), 'utf8')) as Record<'base' | 'process' | 'no_release' | 'appeal' | 'appeal_gated' | 'guarded' | 'feedback' | 'on_request' | 'base5' | 'feedback5', TERun>;
const light = (m: THREE.Mesh) => { const c = (m.material as THREE.MeshStandardMaterial).color, h = { h: 0, s: 0, l: 0 }; c.getHSL(h); return h.l; };

describe('the objects of the chain', () => {
  const parent = new THREE.Group(), layer = buildTruthLayer(parent, new THREE.Vector3(0, 12, 0), 18);
  it('are one pickable mesh per node, each naming its node, and one line segment per edge', () => {
    expect(layer.pickables).toHaveLength(NODES.length);
    for (const n of NODES) { expect(teNodeOf(layer.meshOf(n.id))).toBe(n.id); expect(layer.meshOf(n.id).userData).toEqual({ teNode: n.id }); }
    expect(teNodeOf(undefined)).toBeNull(); expect(teNodeOf(new THREE.Object3D())).toBeNull();
    expect((layer.edgeLines.geometry.getAttribute('position') as THREE.BufferAttribute).count).toBe(EDGES.length * 2);
  });
  it('take their brightness from the engine\'s record: a granted access is brighter than a denied one, a high score brighter than a low one', () => {
    const rs = base.records[1];
    const granted = rs.find((r) => r.access)!, denied = rs.find((r) => !r.access)!;
    layer.set({ run: base, branch: null, k: 1, t: granted.t, selected: null });
    const a = light(layer.meshOf('gate_a'));
    layer.set({ run: base, branch: null, k: 1, t: denied.t, selected: null });
    expect(light(layer.meshOf('gate_a'))).toBeLessThan(a);
    const hi = rs.reduce((p, r) => (r.score > p.score ? r : p)), lo = rs.reduce((p, r) => (r.score < p.score ? r : p));
    layer.set({ run: base, branch: null, k: 1, t: hi.t, selected: null }); const lh = light(layer.meshOf('score'));
    layer.set({ run: base, branch: null, k: 1, t: lo.t, selected: null });
    expect(light(layer.meshOf('score'))).toBeLessThan(lh);
  });
  it('rotate the pose frames as the record\'s angles say (yaw about Y, pitch about X, roll about Z), reference and measured apart', () => {
    const r = biased.records[0].find((x) => x.pose_missing === 0 && x.pose_measured.every((v) => v !== null))!;
    layer.set({ run: biased, branch: null, k: 0, t: r.t, selected: null });
    const want = (p: Array<number | null>) => new THREE.Quaternion().setFromEuler(new THREE.Euler(((p[1] as number) * Math.PI) / 180, ((p[0] as number) * Math.PI) / 180, ((p[2] as number) * Math.PI) / 180, 'YXZ'));
    expect(layer.poseRef.quaternion.angleTo(want(r.pose_reference))).toBeLessThan(1e-6);
    expect(layer.poseMeasured.quaternion.angleTo(want(r.pose_measured))).toBeLessThan(1e-6);
    expect(layer.poseRef.quaternion.angleTo(layer.poseMeasured.quaternion)).toBeGreaterThan(0.01);  // the sensor's error is a visible difference between the two frames
  });
  it('hide the measured frame when the sensor obtained nothing, and keep the reference frame', () => {
    const lost = biased.records[0].find((x) => x.pose_missing > 0)!;
    layer.set({ run: biased, branch: null, k: 0, t: lost.t, selected: null });
    expect(layer.poseMeasured.visible).toBe(false); expect(layer.poseRef.visible).toBe(true);
  });
  it('show the baseline and branch markers together, each coloured from its own run, and none without a branch', () => {
    const pips = (id: NodeId) => layer.meshOf(id).children.filter((c) => (c as THREE.Mesh).isMesh) as THREE.Mesh[];
    layer.set({ run: base, branch: null, k: 2, t: 20, selected: null });
    expect(pips('classifier').every((p) => !p.visible)).toBe(true);
    // a period where the two runs classify differently
    const t = base.records[2].findIndex((r, i) => r.classification !== invalid.records[2][i].classification && i > 8);
    expect(t).toBeGreaterThan(0);
    layer.set({ run: base, branch: invalid, k: 2, t, selected: null });
    const [pb, pr] = pips('classifier');
    expect(pb.visible && pr.visible).toBe(true);
    expect((pb.material as THREE.MeshBasicMaterial).color.getHex()).not.toBe((pr.material as THREE.MeshBasicMaterial).color.getHex());
    const c = (v: number | null) => new THREE.Color().setHSL(0.58, 0.18, 0.12 + 0.6 * (v as number)).getHex();
    expect((pb.material as THREE.MeshBasicMaterial).color.getHex()).toBe(c(nodeValue('classifier', base.records[2][t])));
    expect((pr.material as THREE.MeshBasicMaterial).color.getHex()).toBe(c(nodeValue('classifier', invalid.records[2][t])));
  });
  it('mark a binding constraint on the gate, and highlight the selected node', () => {
    const lockedT = base.records.flatMap((rs) => rs.filter((r) => r.locked)).at(0)!;
    const k = base.records.findIndex((rs) => rs.some((r) => r.locked));
    layer.set({ run: base, branch: null, k, t: lockedT.t, selected: 'score' });
    expect(layer.meshOf('gate_a').rotation.y).toBeCloseTo(Math.PI / 4, 6);
    expect(layer.meshOf('score').scale.x).toBeGreaterThan(layer.meshOf('classifier').scale.x);
    const free = base.records[k].find((r) => !r.locked)!;
    layer.set({ run: base, branch: null, k, t: free.t, selected: null });
    expect(layer.meshOf('gate_a').rotation.y).toBe(0);
  });
  it('are picked by a ray aimed at them', () => {
    parent.updateMatrixWorld(true);
    const rc = new THREE.Raycaster();
    for (const id of ['subject', 'score', 'resources'] as NodeId[]) {
      const w = layer.meshOf(id).getWorldPosition(new THREE.Vector3());
      rc.set(new THREE.Vector3(w.x, w.y, w.z + 20), new THREE.Vector3(0, 0, -1));
      const hit = rc.intersectObjects(layer.pickables, false)[0];
      expect(teNodeOf(hit?.object), id).toBe(id);
    }
  });
  it('clamp the period into the run', () => {
    expect(() => layer.set({ run: base, branch: invalid, k: 0, t: 99999, selected: null })).not.toThrow();
    expect(() => layer.set({ run: base, branch: null, k: 0, t: -3, selected: null })).not.toThrow();
  });
});

describe('mounting and unmounting', () => {
  it('leaves the parent as it found it and disposes what it created', () => {
    const parent = new THREE.Group(), before = parent.children.length, disposed: string[] = [];
    for (let i = 0; i < 15; i++) {
      const l = buildTruthLayer(parent, new THREE.Vector3(), 18);
      expect(parent.children.length).toBe(before + 1);
      (l.meshOf('score').geometry as THREE.BufferGeometry).addEventListener('dispose', () => disposed.push('g'));
      l.set({ run: base, branch: invalid, k: 0, t: 10, selected: 'gate_a' });
      l.dispose();
      expect(parent.children.length).toBe(before);
    }
    expect(disposed).toHaveLength(15);
  });
});

describe('the four paths in the scene', () => {
  const parent = new THREE.Group(), layer = buildTruthLayer(parent, new THREE.Vector3(0, 12, 0), 18);
  const colourOf = (lines: THREE.LineSegments, i: number): number => { const a = lines.geometry.getAttribute('color') as THREE.BufferAttribute; return new THREE.Color(a.getX(i * 2), a.getY(i * 2), a.getZ(i * 2)).getHex(); };
  const steps = PATHS.flatMap((p) => p.steps.map((st) => ({ p: p.id, st }))).filter((x) => x.st.edge);
  it('has one segment for each step of a path that is a transition on an edge, and none for a step with no transition', () => {
    expect(layer.pathSegments).toHaveLength(steps.length);
    expect((layer.pathLines.geometry.getAttribute('position') as THREE.BufferAttribute).count).toBe(steps.length * 2);
    expect(layer.pathSegments.map((s) => `${s.path}/${s.step}`)).toEqual(steps.map((x) => `${x.p}/${x.st.id}`));
    for (const sg of layer.pathSegments) expect(EDGES.some(([a, b]) => a === sg.edge[0] && b === sg.edge[1])).toBe(true);   // never a line the chain has no edge for
  });
  it('lights a segment in its path\'s colour exactly when the step holds for that subject at that period, and leaves it dark otherwise', () => {
    for (const t of [0, 14, 30]) for (const k of [1, 6]) {
      layer.set({ run: runs2.process, branch: null, k, t, selected: null });
      layer.pathSegments.forEach((sg, i) => {
        const st = PATHS.find((p) => p.id === sg.path)!.steps.find((x) => x.id === sg.step)!;
        const lit = stepReached(runs2.process, k, st, t);
        expect(colourOf(layer.pathLines, i), `${sg.path}/${sg.step} k${k} t${t}`).toBe(lit ? PATH_COLORS[sg.path] : 0x23282e);
      });
    }
  });
  it('shows the branch\'s own lines below the baseline\'s only when there is a branch, lit by the branch\'s record', () => {
    layer.set({ run: runs2.process, branch: null, k: 1, t: 30, selected: null });
    expect(layer.pathLinesBranch.visible).toBe(false);
    layer.set({ run: runs2.process, branch: runs2.no_release, k: 1, t: 30, selected: null });
    expect(layer.pathLinesBranch.visible).toBe(true);
    const i = layer.pathSegments.findIndex((s) => s.step === 'released');
    expect(colourOf(layer.pathLines, i)).toBe(PATH_COLORS.correction);       // released in the baseline run
    expect(colourOf(layer.pathLinesBranch, i)).toBe(0x23282e);               // never released in the branch
    const pa = layer.pathLines.geometry.getAttribute('position') as THREE.BufferAttribute, pb = layer.pathLinesBranch.geometry.getAttribute('position') as THREE.BufferAttribute;
    expect(pb.getY(i * 2)).toBeLessThan(pa.getY(i * 2));
  });
  it('draws the two lines of a path along the endpoints of the node objects', () => {
    const sg = layer.pathSegments[0], a = layer.meshOf(sg.edge[0]).position, pos = layer.pathLines.geometry.getAttribute('position') as THREE.BufferAttribute;
    expect([pos.getX(0), pos.getY(0)]).toEqual([expect.closeTo(a.x, 5), expect.closeTo(a.y, 5)]);
  });
});

describe('the selected relation in the scene', () => {
  const parent = new THREE.Group(), layer = buildTruthLayer(parent, new THREE.Vector3(0, 12, 0), 18);
  const colour = () => (layer.relationLines.material as THREE.LineBasicMaterial).color.getHex();
  it('is drawn only when one is selected, on the real edge of that relation, in front of the chain', () => {
    layer.set({ run: runs2.process, branch: null, k: 1, t: 12, selected: null });
    expect(layer.relationLines.visible).toBe(false);
    for (const r of RELATIONS) {
      layer.set({ run: runs2.process, branch: null, k: 1, t: 12, selected: null, relation: r.id });
      expect(layer.relationLines.visible).toBe(true);
      const pos = layer.relationLines.geometry.getAttribute('position') as THREE.BufferAttribute, draw = layer.relationLines.geometry.drawRange;
      expect(draw.count).toBe(r.edges.length * 2);
      r.edges.forEach(([a, b], j) => {
        const pa = layer.meshOf(a).position, pb = layer.meshOf(b).position;
        expect([pos.getX(j * 2), pos.getY(j * 2), pos.getX(j * 2 + 1), pos.getY(j * 2 + 1)]).toEqual([expect.closeTo(pa.x, 4), expect.closeTo(pa.y, 4), expect.closeTo(pb.x, 4), expect.closeTo(pb.y, 4)]);
      });
    }
  });
  it('takes its colour from the engine check: green where the record satisfies the model\'s rule, red where it does not, white where there is no identity', () => {
    layer.set({ run: runs2.process, branch: null, k: 1, t: 12, selected: null, relation: 'score_judgement' });
    expect(relationAt(runs2.process, 1, 12, 'score_judgement').check.holds).toBe(true); expect(colour()).toBe(RELATION_COLORS.holds);
    const bad = structuredClone(runs2.process); bad.records[1][12].access = !bad.records[1][12].access;
    layer.set({ run: bad, branch: null, k: 1, t: 12, selected: null, relation: 'score_judgement' });
    expect(colour()).toBe(RELATION_COLORS.fails);
    layer.set({ run: runs2.process, branch: null, k: 1, t: 12, selected: null, relation: 'sensor_subject' });
    expect(colour()).toBe(RELATION_COLORS.open);
  });
  it('shows the guarantee node lit when a guarantee acted for that subject and period, dark otherwise', () => {
    const rs = runs2.guarded.records.find((r) => r.some((x) => x.guarantee_access || (x.support ?? 0) > 0))!, k = runs2.guarded.records.indexOf(rs);
    const on = rs.find((x) => x.guarantee_access || (x.support ?? 0) > 0)!, off = rs.find((x) => !x.guarantee_access && !(x.support ?? 0))!;
    const light = (m: THREE.Mesh) => { const h = { h: 0, s: 0, l: 0 }; (m.material as THREE.MeshStandardMaterial).color.getHSL(h); return h.l; };
    layer.set({ run: runs2.guarded, branch: null, k, t: on.t, selected: null }); const a = light(layer.meshOf('guarantee'));
    layer.set({ run: runs2.guarded, branch: null, k, t: off.t, selected: null });
    expect(light(layer.meshOf('guarantee'))).toBeLessThan(a);
  });
});

describe('the changed target and the shifted label in the scene', () => {
  const parent = new THREE.Group(), layer = buildTruthLayer(parent, new THREE.Vector3(0, 12, 0), 18);
  it('draws a bar whose height is the record\'s |state - counterfactual state|, and none without the feedback', () => {
    for (const t of [3, 20, 39]) for (const k of [0, 1, 2]) {
      const x = runs2.feedback.records[k][t];
      layer.set({ run: runs2.feedback, branch: null, k, t, selected: null });
      expect(layer.targetBar.visible).toBe(true);
      expect(layer.targetBar.scale.y).toBeCloseTo(Math.min(3, Math.abs(x.reference_z - (x.z_counterfactual as number))) * TARGET_BAR_UNIT + 0.001, 6);
    }
    layer.set({ run: runs2.base, branch: null, k: 1, t: 25, selected: null });
    expect(layer.targetBar.scale.y).toBeLessThan(0.01);   // beta 0: the state is the counterfactual state
    const stripped = structuredClone(runs2.base) as TERun; delete stripped.records[1][25].z_counterfactual;
    layer.set({ run: stripped, branch: null, k: 1, t: 25, selected: null });
    expect(layer.targetBar.visible).toBe(false);   // a record without the counterfactual shows nothing rather than a guess
  });
  it('lights the label-shift marker exactly when the current label differs from the counterfactual label', () => {
    let lit = 0, dark = 0;
    for (let k = 0; k < runs2.feedback5.records.length; k++) for (let t = 0; t < 40; t += 3) {
      const x = runs2.feedback5.records[k][t], want = x.verification_label !== x.label_counterfactual;
      layer.set({ run: runs2.feedback5, branch: null, k, t, selected: null });
      expect(layer.labelShiftMarker.visible, `k${k} t${t}`).toBe(want); if (want) lit++; else dark++;
    }
    expect(lit).toBeGreaterThan(0); expect(dark).toBeGreaterThan(0);
  });
  it('draws the evaluator\'s label relation apart from the chain and colours it by the identity check', () => {
    layer.set({ run: runs2.feedback, branch: null, k: 1, t: 12, selected: null, relation: 'label_generation' });
    expect(layer.relationLines.visible).toBe(true);
    expect((layer.relationLines.material as THREE.LineBasicMaterial).color.getHex()).toBe(RELATION_COLORS.holds);
    const bad = structuredClone(runs2.feedback); bad.records[1][12].label_counterfactual = !bad.records[1][12].label_counterfactual;
    layer.set({ run: bad, branch: null, k: 1, t: 12, selected: null, relation: 'label_generation' });
    expect((layer.relationLines.material as THREE.LineBasicMaterial).color.getHex()).toBe(RELATION_COLORS.fails);
  });
});
