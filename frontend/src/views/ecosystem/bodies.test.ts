// XENO ECOSYSTEM — the experimental bodies and the wet ground, without a renderer: what the record says about the bodies (a pure mapping), that the geometry builds with the
// detail it claims, that each state of the run produces the mechanical change it is documented to produce, and that the ground faces up.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { bodyState, buildBodies, FLASH_TICKS, perforated } from './bodies';
import { sssMechanics } from './mechanics';
import { nodeAwake, nodeProbeState, reservoirLevel, ringProbeState, REACTIVATE_AT, RECOVERY_TICKS, type BodyState } from './bodyState';
import { buildCables, routeCurve } from './cables';
import { Fasteners } from './hardware';
import { FULL_OBSERVATION, type MeosRecord } from './meosApi';
import { buildProbe, probeDimensions, type ProbeMats, type ProbeSpec } from './probes';
import { PUDDLES, buildTerrain, makeNoise } from './terrain';
import { weather } from './weathering';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const rec1 = JSON.parse(readFileSync(join(dir, 'meos-a2-removed.json'), 'utf8')) as MeosRecord;

const idle: BodyState = {
  sampling: false, coverage: 1, aim: [6.5, 6.5], interval: 1, a1FireAge: null, renewAge: null, interaction: 0, couplingCut: false, a2Present: true, status: 'ACTIVE', recovered: false,
  collapsed: false, recoveryAge: null, pulseAge: null, pulseAmount: 0, historyEnabled: true, address: { A1: null, A2: null }, arenaRadius: null, observability: 'OBSERVABLE', tick: 0,
  sss: { scale: 1, size: 1, speed: 1 }, sssRegion: 'ACTIVE', mech: sssMechanics({ scale: 1, size: 1, speed: 1 }), m2: { configured: false, sense: 'none', sensed: 0, state: null },
};

describe('bodyState', () => {
  it('reads the last A1 firing from the events, as an age in ticks', () => {
    const fires = rec.events.filter((e) => e.kind === 'fire' && e.actor === 'A1').map((e) => e.tick);
    const t = fires[10] + 2;
    expect(bodyState(rec, t, null).a1FireAge).toBe(t - Math.max(...fires.filter((f) => f <= t)));
  });
  it('marks the coupling as cut while the interaction channel is cut, and not before or after', () => {
    expect(bodyState(rec, 90, null).couplingCut).toBe(false);
    expect(bodyState(rec, 120, null).couplingCut).toBe(true);
    expect(bodyState(rec, 160, null).couplingCut).toBe(false);
  });
  it('follows the observation: a sampled tick, its coverage and its interval', () => {
    expect(bodyState(rec, 8, { ...FULL_OBSERVATION, sampling_interval: 4 }).sampling).toBe(true);
    expect(bodyState(rec, 9, { ...FULL_OBSERVATION, sampling_interval: 4 }).sampling).toBe(false);
    expect(bodyState(rec, 9, { ...FULL_OBSERVATION, spatial_stride: 2 }).coverage).toBeCloseTo(0.25, 6);
    expect(bodyState(rec, 9, { ...FULL_OBSERVATION, sampling_interval: 4 }).interval).toBe(4);
  });
  it('reads collapse, recovery, the resource pulse and the Address Domain fault from the record', () => {
    expect(bodyState(rec, 100, null).collapsed).toBe(false);
    expect(bodyState(rec, 150, null).collapsed).toBe(true);
    expect(bodyState(rec, 100, null).recoveryAge).toBeNull();
    expect(bodyState(rec, 170, null).recoveryAge).toBe(170 - 161);
    expect(bodyState(rec, 155, null).pulseAge).toBe(4);
    expect(bodyState(rec, 170, null).pulseAge).toBeNull();
    expect(bodyState(rec, 210, null).address.A2).toBe('fragment');
    expect(bodyState(rec, 230, null).address.A2).toBeNull();
  });
  it('passes the observability of the run, and reads a record without traces', () => {
    expect(bodyState(rec, 10, null, 'INSUFFICIENT_TEMPORAL_RESOLUTION').observability).toBe('INSUFFICIENT_TEMPORAL_RESOLUTION');
    expect(() => bodyState(rec1, 100, null)).not.toThrow();
    expect(bodyState(rec1, 100, null).interaction).toBe(0);
  });
  it('is pure', () => { expect(bodyState(rec, 130, null)).toEqual(bodyState(rec, 130, null)); });
});

describe('the documented mapping of state to probe, node and reservoir', () => {
  it('retracts every probe when the run collapses and leaves every node asleep', () => {
    const c = { ...idle, collapsed: true, status: 'COLLAPSED' };
    for (const n of ['A', 'B', 'C'] as const) { expect(nodeProbeState(c, n)).toBe('retracted'); expect(nodeAwake(c, n)).toBe(false); }
    expect(ringProbeState(c, 0, 6)).toBe('retracted');
  });
  it('reactivates the nodes one after another after a recovery', () => {
    const at = (age: number): BodyState => ({ ...idle, recovered: true, recoveryAge: age });
    expect([nodeAwake(at(0), 'A'), nodeAwake(at(0), 'B'), nodeAwake(at(0), 'C')]).toEqual([true, false, false]);
    expect([nodeAwake(at(REACTIVATE_AT.B), 'A'), nodeAwake(at(REACTIVATE_AT.B), 'B'), nodeAwake(at(REACTIVATE_AT.B), 'C')]).toEqual([true, true, false]);
    expect(nodeAwake(at(REACTIVATE_AT.C), 'C')).toBe(true);
    expect(nodeAwake(at(RECOVERY_TICKS + 5), 'C')).toBe(true);
    expect(nodeProbeState(at(1), 'C')).toBe('inactive');
  });
  it('reads the state of the probes of A, B and C from the observation, the A1 firing and the A2 renewal', () => {
    expect(nodeProbeState({ ...idle, sampling: true }, 'A')).toBe('sampling');
    expect(nodeProbeState({ ...idle, sampling: true, observability: 'INSUFFICIENT_TEMPORAL_RESOLUTION' }, 'A')).toBe('overloaded');
    expect(nodeProbeState({ ...idle, a1FireAge: 1 }, 'B')).toBe('sampling');
    expect(nodeProbeState({ ...idle, a1FireAge: FLASH_TICKS + 4 }, 'B')).toBe('extended');
    expect(nodeProbeState({ ...idle, renewAge: 0 }, 'C')).toBe('sampling');
    expect(nodeProbeState({ ...idle, a2Present: false }, 'C')).toBe('inactive');
    expect(nodeProbeState({ ...idle, address: { A1: 'loss', A2: null } }, 'B')).toBe('inactive');
    expect(nodeProbeState({ ...idle, address: { A1: null, A2: 'partial' } }, 'C')).toBe('overloaded');
  });
  it('withdraws the observer probes beyond the coverage of the observation', () => {
    const half = { ...idle, coverage: 0.5 };
    expect([0, 1, 2, 3, 4, 5].map((i) => ringProbeState(half, i, 6))).toEqual(['extended', 'extended', 'extended', 'retracted', 'retracted', 'retracted']);
    expect(ringProbeState({ ...half, sampling: true }, 0, 6)).toBe('sampling');
    expect(ringProbeState({ ...half, observability: 'OBSERVATION_WINDOW_MISMATCH' }, 0, 6)).toBe('overloaded');
    expect(ringProbeState({ ...idle, coverage: 0.01 }, 0, 6)).not.toBe('retracted');  // at least one probe stays out
  });
  it('raises the reservoir with a resource pulse and lets it settle over the pulse window', () => {
    const base = reservoirLevel(idle), hit = reservoirLevel({ ...idle, pulseAge: 0, pulseAmount: 2 }), later = reservoirLevel({ ...idle, pulseAge: 10, pulseAmount: 2 });
    expect(hit).toBeGreaterThan(base); expect(later).toBeLessThan(hit); expect(later).toBeGreaterThanOrEqual(base);
    expect(reservoirLevel({ ...idle, collapsed: true })).toBeLessThan(base);
  });
});

const mats = (): ProbeMats => {
  const m = () => new THREE.MeshStandardMaterial();
  return { chrome: m(), gun: m(), rubber: m(), polished: m(), lamp: m() };
};
describe('probes', () => {
  const spec: ProbeSpec = { id: 'T', length: 2.0, radius: 0.08, tip: 'hollow', insulated: 0.3, retractor: true, strain: true };
  it('is built from its spec and its dimensions are read back from the geometry', () => {
    const p = buildProbe(spec, mats(), 1), d = probeDimensions(p);
    expect(d.length).toBe(2);
    expect(d.measuredLength).toBeGreaterThan(1.95); expect(d.measuredLength).toBeLessThan(2.2);
    expect(d.diameter).toBeCloseTo(0.08 * 2 * 0.72, 2);
    expect(d.housing).toBeCloseTo(2.0 * 0.55, 3);
    expect(d.tip).toBe('hollow');
  });
  it('gives different probes different lengths and diameters', () => {
    const a = probeDimensions(buildProbe({ ...spec, length: 1.0, radius: 0.04 }, mats(), 1)), b = probeDimensions(buildProbe({ ...spec, length: 2.6, radius: 0.1, tip: 'hook' }, mats(), 1));
    expect(b.measuredLength).toBeGreaterThan(a.measuredLength * 2); expect(b.diameter).toBeGreaterThan(a.diameter * 2);
  });
  it('poses the five states: retracted is in, extended out, sampling further out and lit, overloaded trembles', () => {
    const p = buildProbe(spec, mats(), 1), lamp = () => (p.bead.material as THREE.MeshStandardMaterial).emissiveIntensity;
    p.setState('extended', 0); const ext = p.rod.position.y, lampExt = lamp();
    p.setState('retracted', 0); const ret = p.rod.position.y;
    p.setState('sampling', 0); const smp = p.rod.position.y, lampSmp = lamp();
    p.setState('inactive', 0); const ina = p.rod.position.y, lampIna = lamp();
    expect(ret).toBeGreaterThan(ina); expect(ina).toBeGreaterThan(ext); expect(ext).toBeGreaterThan(smp);  // y grows as the rod is withdrawn upward into the housing
    expect(lampSmp).toBeGreaterThan(lampExt * 5); expect(lampIna).toBe(0);
    p.setState('overloaded', 0); const x0 = p.rod.position.x, l0 = lamp();
    p.setState('overloaded', 1); expect(p.rod.position.x).toBe(-x0); expect(lamp()).not.toBe(l0);
  });
  it('has a different tip for each kind', () => {
    const v = (tip: ProbeSpec['tip']) => { const p = buildProbe({ ...spec, tip }, mats(), 1); let n = 0; p.group.traverse((o) => { const g = (o as THREE.Mesh).geometry; if (g) n += g.getAttribute('position').count; }); return n; };
    expect(new Set([v('needle'), v('hollow'), v('hook'), v('bead')]).size).toBe(4);
  });
});

describe('cables', () => {
  const cm = { rubber: new THREE.MeshStandardMaterial(), sleeve: new THREE.MeshStandardMaterial(), chrome: new THREE.MeshStandardMaterial(), gun: new THREE.MeshStandardMaterial(), dark: new THREE.MeshStandardMaterial() };
  const routes = [
    { id: 'a', kind: 'power' as const, points: [new THREE.Vector3(0, 3, 0), new THREE.Vector3(4, 2, 1), new THREE.Vector3(8, 3, 0)], radius: 0.09, sleeve: [0.2, 0.7] as [number, number], ends: ['anchor', 'connector'] as ['anchor', 'connector'], clamps: [0.2, 0.5, 0.8] },
    { id: 'b', kind: 'data' as const, points: [new THREE.Vector3(0, 1, 2), new THREE.Vector3(6, 1, 3)], radius: 0.04, sag: 0.2, ends: ['strain', 'strain'] as ['strain', 'strain'], clamps: [0.5] },
  ];
  it('hangs with slack: the lowest point of a route is below the line between its ends', () => {
    const c = routeCurve(routes[1]), pts = c.getPoints(40);
    expect(Math.min(...pts.map((p) => p.y))).toBeLessThan(1 - 0.1);
  });
  it('rests on the ground when asked to', () => {
    const c = routeCurve({ ...routes[1], points: [new THREE.Vector3(0, 1, 0), new THREE.Vector3(5, 1, 0), new THREE.Vector3(10, 1, 0)], rest: 0.05 });
    expect(Math.min(...c.getPoints(60).map((p) => p.y))).toBeLessThan(0.3);
  });
  it('builds routes of unequal thickness with clamps, connectors and a braided sleeve, and counts them', () => {
    const s = buildCables(routes, cm, 1, () => 0.5);
    expect(s.stats).toMatchObject({ routes: 2, clamps: 4, connectors: 1, sleeved: 1 });
    expect(s.stats.lengthTotal).toBeGreaterThan(14);
    expect(new Set(s.routes.map((r) => r.radius)).size).toBe(2);
    expect(s.group.children.length).toBeGreaterThan(3);
  });
});

describe('hardware and geometry', () => {
  it('lays fasteners out unevenly, of several kinds, with gaps', () => {
    const f = new Fasteners(), pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(3, 0, 0), new THREE.Vector3(3, 3, 0), new THREE.Vector3(0, 3, 0)];
    let s = 1; const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
    f.edge(pts, new THREE.Vector3(0, 0, 1), rnd, { pitch: 0.3, inset: 0.1, lift: 0.04, kinds: ['hex', 'socket', 'exposed', 'captive'] });
    expect(f.count).toBeGreaterThan(30);
    const g = new THREE.Group(); f.build(g, { chrome: new THREE.MeshBasicMaterial(), gun: new THREE.MeshBasicMaterial(), dark: new THREE.MeshBasicMaterial() }, [], 1);
    expect(g.children.length).toBeGreaterThanOrEqual(4);  // one instanced mesh per kind, and the recesses of the socket screws
    const gaps = new Set<number>();
    const inst = g.children[0] as THREE.InstancedMesh, m = new THREE.Matrix4(), p = new THREE.Vector3();
    const xs: number[] = []; for (let i = 0; i < inst.count; i++) { inst.getMatrixAt(i, m); p.setFromMatrixPosition(m); xs.push(+p.x.toFixed(2)); }
    xs.sort((a, b) => a - b); for (let i = 1; i < xs.length; i++) gaps.add(+(xs[i] - xs[i - 1]).toFixed(1));
    expect(gaps.size).toBeGreaterThan(1);
  });
  it('makes a perforated plate with real holes and with slots', () => {
    const tri: Array<[number, number]> = [[0, 0], [3, 0], [1.5, 2.6]];
    const plain = perforated(tri, { hole: 0.01, pitch: 100, margin: 5, depth: 0.1 });
    const dense = perforated(tri, { hole: 0.06, pitch: 0.25, margin: 0.2, depth: 0.1 });
    const sparse = perforated(tri, { hole: 0.06, pitch: 0.5, margin: 0.2, depth: 0.1 });
    const slotted = perforated(tri, { hole: 0.01, pitch: 100, margin: 5, depth: 0.1, slots: [[1.5, 0.8, 0.8, 0.08], [1.5, 1.1, 0.8, 0.08]] });
    expect(dense.getAttribute('position').count).toBeGreaterThan(sparse.getAttribute('position').count);
    expect(sparse.getAttribute('position').count).toBeGreaterThan(plain.getAttribute('position').count);
    expect(slotted.getAttribute('position').count).toBeGreaterThan(plain.getAttribute('position').count);
  });
  it('builds the bodies at every tier with more detail at a higher tier, many fasteners, probes of several kinds and a cable network', () => {
    const sets = (['performance', 'balanced', 'high'] as const).map((q) => buildBodies(q, null, () => 0));
    const v = sets.map((b) => b.stats.vertices), fa = sets.map((b) => b.stats.fasteners);
    expect(v[0]).toBeGreaterThan(20000); expect(v[1]).toBeGreaterThan(v[0]); expect(v[2]).toBeGreaterThan(v[1]);
    expect(fa[2]).toBeGreaterThan(400); expect(fa[2]).toBeGreaterThanOrEqual(fa[1]);
    const b = sets[1];
    expect(b.stats.probes).toBe(1 + 2 + 2 + 6);
    expect(b.stats.cableRoutes).toBeGreaterThanOrEqual(10); expect(b.stats.clamps).toBeGreaterThan(15); expect(b.stats.connectors).toBeGreaterThanOrEqual(6); expect(b.stats.sleeved).toBeGreaterThanOrEqual(4);
    const tips = new Set(b.parts.filter((p) => p.kind === 'probe').map((p) => p.params?.tip));
    expect(tips.size).toBe(4);
    const lens = b.parts.filter((p) => p.kind === 'probe').map((p) => Number(p.params?.length));
    expect(new Set(lens).size).toBeGreaterThan(8);  // probes of many different lengths
    sets.forEach((s) => s.dispose());
  }, 120000);
  it('lists its components with identifiers and the parameters they were built from', () => {
    const b = buildBodies('performance', null, () => 0), ids = b.parts.map((p) => p.id);
    for (const id of ['A', 'B', 'C', 'J', 'B.archive', 'C.reservoir', 'OBS', 'RING', 'CLUSTER', 'OPT', 'HEAD', 'O1', 'O6', 'cable.BCb', 'cable.BCc']) expect(ids).toContain(id);
    expect(new Set(ids).size).toBeGreaterThan(40);
    expect(b.parts.find((p) => p.id === 'A')!.params!.plateThickness).toBe(b.stats.plateDepth);
    b.dispose();
  });
  it('weathers a material in world space within a range, and only on request', () => {
    const m = weather(new THREE.MeshStandardMaterial(), { brushing: 1, scratches: 1, edgeWear: 1, grime: 1, streaks: 1, stains: 1, smudge: 1, range: 50 });
    expect(typeof m.onBeforeCompile).toBe('function');
    const shader = { uniforms: {} as Record<string, unknown>, vertexShader: '#include <common>\n#include <begin_vertex>', fragmentShader: '#include <common>\n#include <roughnessmap_fragment>' };
    m.onBeforeCompile(shader as never, null as never);
    expect(shader.fragmentShader).toContain('wRange'); expect(shader.vertexShader).toContain('aWear'); expect(shader.uniforms).toHaveProperty('wRange');
  });
});

describe('the ground', () => {
  const terrain = buildTerrain('performance', 34, [], null);
  it('faces up: every sampled triangle of the ground has an upward normal', () => {
    const ground = terrain.group.children.find((c) => (c as THREE.Mesh).isMesh) as THREE.Mesh;
    const pos = ground.geometry.getAttribute('position'), idx = ground.geometry.index!;
    let up = 0, n = 0;
    for (let i = 0; i < idx.count; i += 3 * 97) {
      const a = new THREE.Vector3().fromBufferAttribute(pos, idx.getX(i)), b = new THREE.Vector3().fromBufferAttribute(pos, idx.getX(i + 1)), c = new THREE.Vector3().fromBufferAttribute(pos, idx.getX(i + 2));
      n++;
      if (b.sub(a).cross(c.sub(a)).y > 0) up++;
    }
    expect(n).toBeGreaterThan(20);
    expect(up).toBe(n);
  });
  it('is deterministic and level where the work areas stand', () => {
    expect(makeNoise(3).fbm(1.3, 2.1)).toBe(makeNoise(3).fbm(1.3, 2.1));
    expect(Math.abs(terrain.heightAt(-104, 4))).toBeLessThan(0.5);
    expect(Math.abs(terrain.heightAt(-66, 16))).toBeLessThan(0.5);
    expect(PUDDLES.length).toBeGreaterThan(3);
  });
});

describe('the bodies answer to the state, mechanically', () => {
  const b = buildBodies('performance', null, () => 0);
  const target = new THREE.Vector3(-66, 0, 16);
  const find = (id: string) => b.parts.find((p) => p.id === id)!.object;
  const nodeC = b.nodes[2], nodeB = b.nodes[1];
  it('swings the C-side half of the coupling down when the coupling is cut, and back when it is restored', () => {
    const pivot = b.ncb.children.find((c) => c.type === 'Group' && c.children.length === 1 && c.position.length() > 1 && (c.children[0] as THREE.Group).type === 'Group' && c !== nodeB.group && c !== nodeC.group)!;
    b.set({ ...idle, couplingCut: false }, target); const a0 = pivot.rotation.clone();
    b.set({ ...idle, couplingCut: true }, target); expect(pivot.quaternion.angleTo(new THREE.Quaternion())).toBeGreaterThan(0.5);
    b.set({ ...idle, couplingCut: false }, target); expect(pivot.quaternion.angleTo(new THREE.Quaternion().setFromEuler(a0))).toBeLessThan(1e-6);
  });
  it('slides the lens covers shut while a node sleeps, and opens them one node after another after a recovery', () => {
    const open = (n: typeof nodeB) => n.cover!.mesh.position.x, nodeA = b.nodes[0];
    b.set(idle, target); expect(open(nodeA)).toBeGreaterThan(0.5); expect(open(nodeB)).toBeGreaterThan(0.5);
    b.set({ ...idle, collapsed: true }, target); expect(open(nodeA)).toBe(0); expect(open(nodeB)).toBe(0);
    b.set({ ...idle, recovered: true, recoveryAge: 2 }, target); expect(open(nodeA)).toBeGreaterThan(0.5); expect(open(nodeB)).toBe(0);
    b.set({ ...idle, recovered: true, recoveryAge: REACTIVATE_AT.B }, target); expect(open(nodeB)).toBeGreaterThan(0.5);
  });
  it('opens the archive latch when history re-entry is disabled and darkens its lamp', () => {
    b.set(idle, target); const closed = nodeB.latch!.lever.rotation.z, lampOn = (nodeB.latch!.lamp.material as THREE.MeshStandardMaterial).emissiveIntensity;
    b.set({ ...idle, historyEnabled: false }, target);
    expect(nodeB.latch!.lever.rotation.z).toBeGreaterThan(closed + 1); expect((nodeB.latch!.lamp.material as THREE.MeshStandardMaterial).emissiveIntensity).toBeLessThan(lampOn);
  });
  it('raises the reservoir piston with a resource pulse', () => {
    b.set(idle, target); const y0 = nodeC.reservoir!.piston.position.y;
    b.set({ ...idle, pulseAge: 0, pulseAmount: 2 }, target); expect(nodeC.reservoir!.piston.position.y).toBeGreaterThan(y0);
  });
  it('turns the observation boom toward a different target and extends it on a sampled tick', () => {
    b.set(idle, new THREE.Vector3(-66, 0, 16)); const a = b.observer.yaw.rotation.y;
    b.set(idle, new THREE.Vector3(-120, 0, 60)); expect(b.observer.yaw.rotation.y).not.toBe(a);
    const sec2 = (): number => { let z = 0; b.observer.pitch.children.forEach((c) => { if (c.type === 'Group' && c.position.z > 1.5 && c.children.length) z = c.position.z; }); return z; };
    b.set(idle, target); const rest = sec2();
    b.set({ ...idle, sampling: true }, target); expect(sec2()).toBeGreaterThan(rest);
    b.set({ ...idle, collapsed: true }, target); expect(sec2()).toBeLessThan(rest);
    expect(b.observer.pitch.rotation.x).toBeGreaterThan(0.5);  // folded down
  });
  it('turns the articulated ring once per sampling interval', () => {
    const ring = find('RING');
    b.set({ ...idle, interval: 4, tick: 8 }, target); const a0 = ring.rotation.z;
    b.set({ ...idle, interval: 4, tick: 10 }, target); expect(ring.rotation.z).toBeCloseTo(a0 + Math.PI, 5);
    b.set({ ...idle, interval: 1, tick: 7 }, target); expect(ring.rotation.z).toBe(0);
  });
  it('withdraws the probes beyond the coverage and repositions the probe ring when the boundary changes', () => {
    const out = (): number => b.observer.probes.filter((p) => p.rod.position.y < 0.2).length;
    b.set({ ...idle, coverage: 1 }, target); const all = out();
    b.set({ ...idle, coverage: 0.34 }, target); expect(out()).toBeLessThan(all);
    const cluster = find('CLUSTER'); b.set({ ...idle, arenaRadius: null }, target); const r0 = cluster.rotation.z;
    b.set({ ...idle, arenaRadius: 2 }, target); expect(cluster.rotation.z).not.toBe(r0);
  });
  it('keeps node C dark and its probe withdrawn while A2 is absent, and lights a lamp for a few ticks after an event', () => {
    const lamps = () => b.group.children.length && [nodeB, nodeC].map((n) => (n.lamp.material as THREE.MeshStandardMaterial).emissiveIntensity);
    b.set(idle, target); const quiet = lamps() as number[];
    b.set({ ...idle, a1FireAge: 0, renewAge: 1 }, target); const fired = lamps() as number[];
    expect(fired[0]).toBeGreaterThan(quiet[0] * 5); expect(fired[1]).toBeGreaterThan(quiet[1] * 5);
    b.set({ ...idle, a1FireAge: FLASH_TICKS + 3, renewAge: FLASH_TICKS + 3 }, target); expect((lampsNow(nodeB))).toBeLessThanOrEqual(quiet[0] + 1e-9);
    b.set({ ...idle, renewAge: 0, a2Present: false }, target); expect(lampsNow(nodeC)).toBe(0);
    expect(nodeC.probes[0].rod.position.y).toBeGreaterThan(0.1);
  });
});

describe('fourth stage: SSS and M2 on the bodies, and the cables of the operational paths', () => {
  const b = buildBodies('performance', null, () => 0), target = new THREE.Vector3(-66, 0, 16), nodeB = b.nodes[1];
  const sec2z = (): number => { let z = 0; b.observer.pitch.children.forEach((c) => { if (c.type === 'Group' && c.position.z > 1.5 && c.children.length) z = c.position.z; }); return z; };
  const withSss = (sss: { scale: number; size: number; speed: number }, region: 'ACTIVE' | 'METASTABLE' | 'RECOVERY-CAPABLE' = 'ACTIVE'): BodyState => ({ ...idle, sss, sssRegion: region, mech: sssMechanics(sss, region) });
  it('lengthens the observer boom with the SSS scale, and only with it', () => {
    b.set(withSss({ scale: 1, size: 1, speed: 1 }), target); const z1 = sec2z();
    b.set(withSss({ scale: 2, size: 1, speed: 1 }), target); const z2 = sec2z();
    b.set(withSss({ scale: 1, size: 2, speed: 2 }), target); expect(sec2z()).toBe(z1);
    expect(z2).toBeGreaterThan(z1 + 0.1);
  });
  it('tilts the probe ring with the SSS size, and only with it', () => {
    const cluster = b.parts.find((p) => p.id === 'CLUSTER')!.object;
    b.set(withSss({ scale: 1, size: 1, speed: 1 }), target); expect(cluster.rotation.x).toBe(0);
    b.set(withSss({ scale: 1, size: 2, speed: 1 }), target); const big = cluster.rotation.x;
    b.set(withSss({ scale: 1, size: 0.5, speed: 1 }), target); const small = cluster.rotation.x;
    expect(big).toBeGreaterThan(0.05); expect(small).toBeLessThan(-0.05);
    b.set(withSss({ scale: 2, size: 1, speed: 2 }), target); expect(cluster.rotation.x).toBe(0);
  });
  it('leaves the archive latch ajar in a metastable or recovery-capable region while history is enabled', () => {
    b.set(withSss({ scale: 1, size: 1, speed: 1 }), target); const shut = nodeB.latch!.lever.rotation.z;
    b.set(withSss({ scale: 1.22, size: 1, speed: 1 }, 'METASTABLE'), target); const meta = nodeB.latch!.lever.rotation.z;
    b.set(withSss({ scale: 1, size: 1, speed: 1 }, 'RECOVERY-CAPABLE'), target); const rec = nodeB.latch!.lever.rotation.z;
    expect(meta).toBeGreaterThan(shut + 0.3); expect(rec).toBeGreaterThan(meta);
    b.set({ ...withSss({ scale: 1, size: 1, speed: 1 }), historyEnabled: false }, target); expect(nodeB.latch!.lever.rotation.z).toBeGreaterThan(rec);  // disabled history opens it fully
  });
  it('moves the reservoir level with the SSS speed (regulation)', () => {
    const y = () => b.nodes[2].reservoir!.piston.position.y;
    b.set(withSss({ scale: 1, size: 1, speed: 1 }), target); const y1 = y();
    b.set(withSss({ scale: 1, size: 1, speed: 2 }), target); expect(y()).toBeGreaterThan(y1);
  });
  it('drives node B\'s second probe as the M2 tap only when M2 sensing is configured', () => {
    const tap = b.nodes[1].probes[1], rod = () => tap.rod.position.y;
    b.set(idle, target); const off = rod();  // not configured: the probe follows the node as before
    b.set({ ...idle, m2: { configured: true, sense: 'direct', sensed: 0.4, state: 'sampling' } }, target); const lit = rod();
    b.set({ ...idle, m2: { configured: true, sense: 'direct', sensed: 0, state: 'extended' } }, target); const idleTap = rod();
    b.set({ ...idle, collapsed: true, m2: { configured: true, sense: 'direct', sensed: 0, state: 'retracted' } }, target); const folded = rod();
    expect(lit).not.toBe(off); expect(lit).not.toBe(idleTap); expect(folded).toBeGreaterThan(idleTap);  // a retracted probe's rod is drawn up into its housing (larger y)
  });
  it('carries the five operational paths on named cables: every cable of the body names its path, and each path has a cable', () => {
    const cables = b.parts.filter((p) => p.kind === 'cable' && p.body === 'ncb'), paths = new Set(cables.map((c) => c.params!.path).filter((x) => typeof x === 'string' && x !== ''));
    expect([...paths].sort()).toEqual(['coupling', 'history_access', 'observation', 'recovery', 'resource']);
    for (const id of ['ARCH', 'OBSV', 'REC']) expect(cables.some((c) => c.id === `cable.${id}`)).toBe(true);
    expect(cables.filter((c) => !c.params!.path).map((c) => c.id)).toEqual(['cable.BG']);  // the ground lead of node B is the one cable that carries no operational path
    expect(cables.find((c) => c.id === 'cable.BCb')!.params!.strands).toBeGreaterThan(0);
    expect(cables.find((c) => c.id === 'cable.BCb')!.params!.ties).toBeGreaterThan(0);
  });
});
const lampsNow = (n: { lamp: THREE.Mesh }) => (n.lamp.material as THREE.MeshStandardMaterial).emissiveIntensity;
