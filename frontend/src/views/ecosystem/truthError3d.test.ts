// TRUTH-ERROR DYNAMICS in the 3D scene — the mapping from the engine's record to the objects (brightness, pose rotation, markers, the mark of a binding constraint), picking, and the release of resources. Real engine
// runs (truth-error-runs.json); three.js runs in node. SYNTHETIC only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { EDGES, NODES, nodeValue, type NodeId, type TERun } from './truthError';
import { buildTruthLayer, teNodeOf } from './truthError3d';

const runs = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'truth-error-runs.json'), 'utf8')) as Record<'base' | 'invalid' | 'biased' | 'noscore', TERun>;
const { base, invalid, biased } = runs;
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
