// XENO ECOSYSTEM — the experimental bodies of the habitat's surface, modelled after the supplied concept renders:
//
//   NON-CENTRAL EXPERIMENTAL BODY   three nodes (observation / processing / resource exchange) on rock, joined by a cable network through a ring junction
//   ADAPTIVE OBSERVATION NODE       an asymmetric multi-legged carrier with a telescoping boom, a side optical unit, an articulated ring and a ring of retractable micro-probes
//
// The geometry is static architecture and says nothing about the model. What moves or lights is driven only by a ``BodyState`` (bodyState.ts), a pure function of a MEOS record at
// a tick and of the observation configuration. The mapping is a design choice of this view and is written at the head of bodyState.ts; it does not claim that A1, A2 or the
// observation are these machines. ``parts`` lists the components with identifiers and the parameters they were built from, which the technical view reads.
import * as THREE from 'three';
import { cylAt, Parts, sphere, tube, v3 } from './geom';
import { Fasteners, hingePin, turnbuckle } from './hardware';
import { buildCables, junctionBlock, type CableRoute, type CableSet } from './cables';
import { buildNode, seeded, type BodyMats, type NodeBuild, type PartInfo, PLATE_DEPTH } from './ncb';
import { buildObserver, type ObserverBuild } from './observer';
import { FLASH_TICKS, flashOf, nodeAwake, nodeProbeState, reservoirLevel, type BodyState } from './bodyState';
import { weather, WEATHER_DEFAULT } from './weathering';

// ---------------------------------------------------------------------------------------------------- reflections
/** A dark studio for reflections: a black room with a few long bright strips and panels, so that polished metal and wet rock show crisp white streaks as in the concept renders. */
export function studioEnvironment(renderer: THREE.WebGLRenderer): THREE.Texture {
  const sc = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(80, 40, 80), new THREE.MeshBasicMaterial({ color: 0x030304, side: THREE.BackSide })); sc.add(room);
  const panel = (w: number, h: number, pos: [number, number, number], rot: [number, number, number], k: number) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(k, k, k * 1.05), side: THREE.DoubleSide }));
    m.position.set(...pos); m.rotation.set(...rot); sc.add(m);
  };
  panel(60, 2.2, [0, 19.5, -8], [Math.PI / 2, 0, 0.35], 9); panel(40, 1.6, [-37, 8, 0], [0, Math.PI / 2, 0.1], 6); panel(1.8, 26, [30, 4, -37], [0, 0, 0], 7);
  panel(10, 10, [0, 6, 38], [0, Math.PI, 0], 2.5); panel(22, 1.2, [10, -3, 38], [0, Math.PI, 0.3], 5); panel(16, 16, [0, 19.8, 14], [Math.PI / 2, 0, 0], 1.2);
  const pm = new THREE.PMREMGenerator(renderer), t = pm.fromScene(sc, 0.02).texture;
  pm.dispose();
  sc.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.geometry.dispose(); (m.material as THREE.Material).dispose(); } });
  return t;
}

// ---------------------------------------------------------------------------------------------------- materials
function materials(env: THREE.Texture | null, owned: Array<{ dispose(): void }>, quality: string): BodyMats {
  const w = quality === 'performance' ? { ...WEATHER_DEFAULT, range: 0 } : { ...WEATHER_DEFAULT, range: quality === 'high' ? 90 : 62 };
  const std = (o: THREE.MeshStandardMaterialParameters, wear = true) => { const m = new THREE.MeshStandardMaterial({ envMap: env, ...o }); owned.push(m); return wear && w.range > 0 ? weather(m, w) : m; };
  const lamp = () => std({ color: 0x0c0c0e, emissive: 0xffffff, emissiveIntensity: 0, roughness: 0.3, metalness: 0.1 }, false);
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x020203, roughness: 0.04, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.03, envMap: env, envMapIntensity: 2.4 });
  const spark = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  const pulse = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
  owned.push(glass, spark, pulse);
  return {
    chrome: std({ color: 0xcfd3da, metalness: 1, roughness: 0.16, envMapIntensity: 1.6 }),
    gun: std({ color: 0x1b1d21, metalness: 0.95, roughness: 0.27, envMapIntensity: 1.7 }),
    dark: std({ color: 0x0a0b0d, metalness: 0.7, roughness: 0.42, envMapIntensity: 1.1 }),
    rubber: std({ color: 0x08080a, metalness: 0.2, roughness: 0.62, envMapIntensity: 0.8 }),
    polished: std({ color: 0xe6e8ee, metalness: 1, roughness: 0.07, envMapIntensity: 1.9 }, false),
    sleeve: std({ color: 0x111215, metalness: 0.85, roughness: 0.3, envMapIntensity: 1.4 }),
    glass, lamp: lamp(), lampA: lamp(), lampB: lamp(), lampC: lamp(), lens: lamp(), spark, pulse,
  };
}

// ---------------------------------------------------------------------------------------------------- the set of bodies
export interface BodySet {
  group: THREE.Group; ncbCentre: THREE.Vector3; observerCentre: THREE.Vector3; set(s: BodyState, aimWorld: THREE.Vector3): void;
  parts: PartInfo[]; nodes: NodeBuild[]; observer: ObserverBuild; cables: CableSet[]; ncb: THREE.Group; obs: THREE.Group;
  /** world points where cables lie on the ground: stones are placed against them so that a stretch of cable runs partly hidden */ restPoints: THREE.Vector3[];
  stats: { vertices: number; fasteners: number; probes: number; cableRoutes: number; clamps: number; connectors: number; sleeved: number; plateDepth: number };
  dispose(): void;
}
export const NCB_AT = v3(-104, 0, 4), OBSERVER_AT = v3(-86, 0, 36);

export function buildBodies(quality: 'performance' | 'balanced' | 'high', env: THREE.Texture | null, groundAt: (x: number, z: number) => number): BodySet {
  const detail = quality === 'performance' ? 0.4 : quality === 'balanced' ? 0.75 : 1;
  const owned: Array<{ dispose(): void }> = [];
  const M = materials(env, owned, quality), R = seeded(3);
  const group = new THREE.Group(); group.name = 'experimental-bodies';
  const info: PartInfo[] = [];
  const mk = { chrome: M.chrome, gun: M.gun, dark: M.dark, rubber: M.rubber, polished: M.polished, sleeve: M.sleeve, glass: M.glass };

  // ---- non-central body: three nodes
  const ncb = new THREE.Group(); ncb.position.set(NCB_AT.x, groundAt(NCB_AT.x, NCB_AT.z), NCB_AT.z); ncb.rotation.y = 0.35; group.add(ncb);
  const spots = { A: v3(0, 5.6, -8.5), B: v3(-10, 1.0, 5.5), C: v3(10, 1.0, 5.5) };
  const nodeA = buildNode({ id: 'A', r0: 2.4, r1: 1.2, h: 3.8, window: true, legs: false, seed: 1, probes: [{ id: 'A1', length: 1.9, radius: 0.09, tip: 'hollow', insulated: 0.25, retractor: true, strain: true }] }, M, detail);
  const nodeB = buildNode({ id: 'B', r0: 2.2, r1: 1.2, h: 3.4, window: true, legs: true, seed: 2, archive: true, probes: [{ id: 'B1', length: 1.5, radius: 0.07, tip: 'needle', insulated: 0.3, retractor: true, strain: true }, { id: 'B2', length: 0.9, radius: 0.045, tip: 'bead', insulated: 0.2, retractor: false, strain: false }] }, M, detail);
  const nodeC = buildNode({ id: 'C', r0: 2.2, r1: 1.1, h: 3.4, window: false, legs: true, seed: 3, reservoir: true, probes: [{ id: 'C1', length: 2.3, radius: 0.11, tip: 'hook', insulated: 0.35, retractor: true, strain: true }, { id: 'C2', length: 1.1, radius: 0.05, tip: 'needle', insulated: 0.0, retractor: true, strain: false }] }, M, detail);
  nodeA.group.position.copy(spots.A); nodeB.group.position.copy(spots.B); nodeC.group.position.copy(spots.C);
  nodeB.group.rotation.y = 2.3; nodeC.group.rotation.y = -0.9; nodeA.group.rotation.y = 0.2;
  ncb.add(nodeA.group, nodeB.group, nodeC.group);
  [nodeA, nodeB, nodeC].forEach((n) => { n.group.updateMatrix(); info.push(...n.parts); });
  const world = (n: NodeBuild, p: THREE.Vector3) => p.clone().applyMatrix4(n.group.matrix);

  // node A stands on three splayed struts with knees, hinge pins, tension brackets and gripping feet
  const sp = new Parts(), sf = new Fasteners();
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2 + 0.9, foot = spots.A.clone().add(v3(Math.cos(a) * 4.4, -spots.A.y, Math.sin(a) * 4.4)), top = spots.A.clone().add(v3(Math.cos(a) * 1.3, -0.1, Math.sin(a) * 1.3));
    const knee = top.clone().lerp(foot, 0.5).add(v3(Math.cos(a) * 0.7, 0.2, Math.sin(a) * 0.7));
    sp.add('gun', tube(top, knee, 0.15), 0.5); sp.add('gun', tube(knee, foot, 0.13), 0.5); sp.add('chrome', sphere(knee, 0.27), 0.95); sp.add('chrome', sphere(top, 0.22), 0.95);
    hingePin(sp, knee, v3(-Math.sin(a), 0, Math.cos(a)), 0.7, 0.07); turnbuckle(sp, top.clone().lerp(knee, 0.5).add(v3(0.1, 0, 0)), foot.clone().lerp(knee, 0.5).add(v3(-Math.sin(a) * 1.4, 0, Math.cos(a) * 1.4)), 0.05);
    sp.add('gun', cylAt(foot.clone().add(v3(0, 0.1, 0)), v3(0, 1, 0), 0.62, 0.2, 18, 0.5), 0.9);
    for (let k = 0; k < 3; k++) { const b = (k / 3) * 6.28; sp.add('chrome', cylAt(foot.clone().add(v3(Math.cos(b) * 0.4, -0.08, Math.sin(b) * 0.4)), v3(0, 1, 0), 0.07, 0.14, 6, 0.02), 0.9); }
    for (let k = 0; k < 10; k++) { const b = (k / 10) * 6.28; sf.add(k % 3 ? 'hex' : 'socket', foot.clone().add(v3(Math.cos(b) * 0.5, 0.21, Math.sin(b) * 0.5)), v3(0, 1, 0), 0.9); }
  }
  // the ring junction on a post
  const junctionAt = v3(0, 3.1, 0.5);
  sp.add('gun', cylAt(v3(junctionAt.x, junctionAt.y / 2, junctionAt.z), v3(0, 1, 0), 0.28, junctionAt.y, 14, 0.4), 0.7);
  sp.add('chrome', cylAt(v3(0, 0.3, 0.5), v3(0, 1, 0), 0.55, 0.22, 16, 0.4), 0.9);
  for (let k = 0; k < 8; k++) { const b = (k / 8) * 6.28; sf.add('hex', v3(Math.cos(b) * 0.48, 0.42, 0.5 + Math.sin(b) * 0.48), v3(0, 1, 0), 0.9); }
  sp.flush(ncb, mk, owned, 'ncb');
  sf.build(ncb, { chrome: M.chrome, gun: M.gun, dark: M.dark }, owned, detail);
  const jr: THREE.Mesh[] = [];
  for (const [R0, r0, z, mat] of [[0.95, 0.12, 0, M.chrome], [0.7, 0.08, 0.14, M.gun], [0.7, 0.08, -0.14, M.gun]] as const) {
    const t = new THREE.Mesh(new THREE.TorusGeometry(R0, r0, 12, 40), mat); t.position.copy(junctionAt).add(v3(0, 0, z)); ncb.add(t); owned.push(t.geometry); jr.push(t);
  }
  const hubDisc = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.3, 28).rotateX(Math.PI / 2), M.dark); hubDisc.position.copy(junctionAt); ncb.add(hubDisc); owned.push(hubDisc.geometry);
  info.push({ id: 'J', name: 'Ring junction', kind: 'joint', body: 'ncb', object: hubDisc, params: { radius: 0.95 } });

  // ---- the cable network: routes anchored at hubs and ports of the nodes; clamps stand on anchor plates; the coupling is two halves that meet at a connector pair
  const cm = { rubber: M.rubber, sleeve: M.sleeve, chrome: M.chrome, gun: M.gun, dark: M.dark };
  const mid = v3(0, 0.55, 5.4), J = junctionAt;
  const aBase = (i: number) => world(nodeA, nodeA.anchors[`hubBase${i}`]), bTop = (i: number) => world(nodeB, nodeB.anchors[`hubTop${i}`]), bBase = (i: number) => world(nodeB, nodeB.anchors[`hubBase${i}`]);
  const cTop = (i: number) => world(nodeC, nodeC.anchors[`hubTop${i}`]), cBase = (i: number) => world(nodeC, nodeC.anchors[`hubBase${i}`]);
  const resTop = world(nodeC, nodeC.anchors.reservoirTop);
  const main: CableRoute[] = [
    { id: 'AJ', kind: 'power', points: [aBase(1).add(v3(0, 0.3, 0)), aBase(1).lerp(J, 0.5).add(v3(0.3, 0.2, 0)), J.clone().add(v3(0.05, 0.12, -0.4))], radius: 0.09, sag: 0.1, sleeve: [0.2, 0.75], ends: ['anchor', 'connector'], clamps: [0.18, 0.55, 0.85] },
    { id: 'JB', kind: 'data', points: [J.clone().add(v3(-0.8, 0.1, 0.2)), J.clone().add(v3(-3.2, -0.9, 0.9)), bTop(0)], radius: 0.055, sag: 0.14, ends: ['connector', 'strain'], clamps: [0.3, 0.75] },
    { id: 'JC', kind: 'resource', points: [J.clone().add(v3(0.8, 0.1, 0.2)), J.clone().add(v3(2.4, -0.6, 0.6)), cTop(1)], radius: 0.105, sag: 0.12, ends: ['connector', 'strain'], clamps: [0.3, 0.6, 0.85] },
    { id: 'AB', kind: 'power', points: [aBase(2).add(v3(0, 0.1, 0)), aBase(2).lerp(bTop(2), 0.5).add(v3(0.6, -0.8, 0.2)), bTop(2)], radius: 0.052, sag: 0.16, sleeve: [0.1, 0.5], ends: ['anchor', 'strain'], clamps: [0.35, 0.8] },
    { id: 'AC', kind: 'resource', points: [aBase(0), aBase(0).lerp(cTop(2), 0.5).add(v3(-0.5, -1.0, 0.4)), cTop(2)], radius: 0.075, sag: 0.18, ends: ['strain', 'connector'], clamps: [0.25, 0.7] },
    { id: 'CRES', kind: 'resource', points: [resTop, resTop.clone().add(v3(0.4, 0.5, 0.3)), cTop(0).add(v3(0, 0.2, 0))], radius: 0.065, sag: 0.2, ends: ['connector', 'strain'], clamps: [0.5] },
    { id: 'BG', kind: 'data', points: [bBase(1).add(v3(0, 0.1, 0)), bBase(1).add(v3(-2.2, -0.4, 1.8)), bBase(1).add(v3(-5.8, -0.5, 4.2)), v3(-9.5, 0.0, 6.5)], radius: 0.05, sag: 0.05, rest: 0.02, ends: ['strain', 'anchor'], clamps: [0.4, 0.85] },
    { id: 'BCa', kind: 'data', points: [bBase(0).add(v3(0, 0.05, 0.3)), v3(-3.5, 0.18, 6.4), v3(3.5, 0.18, 6.4), cBase(1).add(v3(0, 0.05, 0.3))], radius: 0.042, sag: 0.05, rest: 0.05, ends: ['strain', 'strain'], clamps: [0.3, 0.7] },
  ];
  const mainSet = buildCables(main, cm, detail, R);
  ncb.add(mainSet.group);
  // the coupling: a B-side half that stays, and a C-side half that swings down about node C when the coupling is cut
  const bcB: CableRoute = { id: 'BCb', kind: 'resource', points: [bBase(2).add(v3(0, 0.1, 0.2)), v3(-5.5, 0.9, 5.8), mid], radius: 0.115, sag: 0.1, sleeve: [0.3, 0.8], ends: ['anchor', 'connector'], clamps: [0.3, 0.6] };
  const cAnchor = cBase(0).add(v3(0, 0.1, 0.2));
  const bcC: CableRoute = { id: 'BCc', kind: 'resource', points: [mid.clone().add(v3(0.02, 0, 0)), v3(5.5, 0.9, 5.8), cAnchor], radius: 0.115, sag: 0.1, sleeve: [0.2, 0.7], ends: ['connector', 'anchor'], clamps: [0.4, 0.7] };
  const couplingB = buildCables([bcB], cm, detail, R), couplingC = buildCables([bcC], cm, detail, R);
  ncb.add(couplingB.group);
  const pivot = new THREE.Group(); pivot.position.copy(cAnchor); couplingC.group.position.copy(cAnchor.clone().negate()); pivot.add(couplingC.group); ncb.add(pivot);
  const chord = mid.clone().sub(cAnchor).normalize(), swingAxis = chord.clone().cross(v3(0, 1, 0)).normalize();
  const swing = chord.clone().applyAxisAngle(swingAxis, 0.3).y > chord.y ? -1 : 1;  // the sign of the rotation that lowers the free end
  // junction blocks where cables branch
  const jp = new Parts();
  junctionBlock(jp, J.clone().add(v3(0, -0.15, -0.55)), v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), 0.5);
  junctionBlock(jp, bTop(0).add(v3(0.3, -0.4, 0.2)), v3(1, 0, 0), v3(0, 1, 0), v3(0, 0, 1), 0.34);
  jp.flush(ncb, mk, owned, 'junction');
  [mainSet, couplingB, couplingC].forEach((cs) => cs.routes.forEach((r) => info.push({ id: `cable.${r.id}`, name: `Cable ${r.id} (${r.kind})`, kind: 'cable', body: 'ncb', object: cs.group, params: { radius: r.radius, kind: r.kind, length: +cs.curves[r.id].getLength().toFixed(2) } })));
  // travelling lights
  const spk = new THREE.SphereGeometry(0.2, 10, 8); owned.push(spk);
  const mkPulse = () => { const m = new THREE.Mesh(spk, M.pulse.clone()); m.visible = false; ncb.add(m); owned.push(m.material as THREE.Material); return m; };
  const pBC = mkPulse(), pCB = mkPulse(), pAJ = mkPulse(), pJB = mkPulse();
  const sparkC = new THREE.Mesh(new THREE.SphereGeometry(0.55, 12, 10), M.spark.clone()); sparkC.visible = false; nodeC.group.add(sparkC); owned.push(sparkC.geometry, sparkC.material as THREE.Material);
  sparkC.position.set(0, -2.0, 0);

  // ---- adaptive observation node
  const observer = buildObserver(M, detail, (x, z) => groundAt(OBSERVER_AT.x + x, OBSERVER_AT.z + z));
  const obs = observer.group; obs.position.set(OBSERVER_AT.x, groundAt(OBSERVER_AT.x, OBSERVER_AT.z), OBSERVER_AT.z); obs.rotation.y = -0.4; group.add(obs);
  info.push(...observer.parts);

  ncb.updateMatrixWorld(true);
  const restPoints: THREE.Vector3[] = [];
  for (const id of ['BG', 'BCa']) { const c = mainSet.curves[id]; for (let u = 0.1; u < 0.95; u += 0.13) { const p = c.getPoint(u); if (p.y < 0.4) restPoints.push(ncb.localToWorld(p.clone())); } }

  // ---- state-linked update
  const tmp = v3(0, 0, 0);
  const along = (u: number, out: THREE.Vector3) => (u < 0.5 ? couplingB.curves.BCb.getPoint(Math.max(0, u * 2), out) : couplingC.curves.BCc.getPoint(Math.min(1, (u - 0.5) * 2), out));
  const set = (s: BodyState, aimWorld: THREE.Vector3) => {
    const awakeA = nodeAwake(s, 'A'), awakeB = nodeAwake(s, 'B'), awakeC = nodeAwake(s, 'C') && s.a2Present;
    const fireF = awakeB ? flashOf(s.a1FireAge) : 0, renF = awakeC ? flashOf(s.renewAge) : 0;
    M.lampA.emissiveIntensity = awakeA && s.sampling ? 0.5 + 2.8 * s.coverage : 0.06;
    M.lampB.emissiveIntensity = awakeB ? 0.06 + 3.4 * fireF : 0;
    M.lampC.emissiveIntensity = awakeC ? 0.06 + 3.4 * renF + (s.recovered ? 0.3 : 0) : 0;
    M.lens.emissiveIntensity = awakeA && s.sampling ? 1.2 + 2.2 * s.coverage : 0.05;
    // probes: the first of each node follows the node's state; the second is out only while its node is working
    [nodeA, nodeB, nodeC].forEach((n) => {
      const st = nodeProbeState(s, n.spec.id);
      n.probes[0].setState(st, s.tick);
      if (n.probes[1]) n.probes[1].setState(st === 'sampling' ? 'sampling' : st === 'extended' ? 'retracted' : st, s.tick);
    });
    (sparkC.material as THREE.MeshBasicMaterial).opacity = renF * 0.8; sparkC.visible = renF > 0.05; sparkC.scale.setScalar(0.5 + renF);
    // reservoir level and the archive latch
    if (nodeC.reservoir) nodeC.reservoir.piston.position.y = nodeC.reservoir.bottom + reservoirLevel(s) * nodeC.reservoir.height;
    if (nodeB.latch) { nodeB.latch.lever.rotation.z = s.historyEnabled ? 0 : 1.25; (nodeB.latch.lamp.material as THREE.MeshStandardMaterial).emissiveIntensity = s.historyEnabled && awakeB ? 1.6 : 0; }
    // the coupling: the C-side half swings down and the junction ring opens when the coupling is cut
    pivot.rotation.set(0, 0, 0); pivot.rotateOnAxis(swingAxis, s.couplingCut ? swing * 0.6 : 0);
    jr.forEach((r, i) => { r.position.z = (i === 0 ? 0 : i === 1 ? 0.14 : -0.14) * (s.couplingCut ? 3.4 : 1) + 0.5; });
    // travelling lights
    const place = (m: THREE.Mesh, f: (out: THREE.Vector3) => void, opacity: number) => { m.visible = opacity > 0.02; if (m.visible) { f(tmp); m.position.copy(tmp); (m.material as THREE.MeshBasicMaterial).opacity = opacity; } };
    const uF = s.a1FireAge === null ? 0 : s.a1FireAge / (FLASH_TICKS + 1), uR = s.renewAge === null ? 1 : 1 - s.renewAge / (FLASH_TICKS + 1);
    place(pBC, (o) => along(uF, o), s.couplingCut ? 0 : fireF);
    place(pCB, (o) => along(uR, o), s.couplingCut || !awakeC ? 0 : renF);
    place(pAJ, (o) => mainSet.curves.AJ.getPoint(0.5, o), awakeA && s.sampling ? 0.5 * s.coverage : 0);
    place(pJB, (o) => mainSet.curves.JB.getPoint(Math.min(1, uF), o), fireF * 0.8);
    observer.set(s, aimWorld);
  };
  const stats = {
    vertices: nodeA.stats.vertices + nodeB.stats.vertices + nodeC.stats.vertices + observer.stats.vertices, fasteners: nodeA.stats.fasteners + nodeB.stats.fasteners + nodeC.stats.fasteners + observer.stats.fasteners,
    probes: [nodeA, nodeB, nodeC].reduce((a, n) => a + n.probes.length, 0) + observer.probes.length, cableRoutes: mainSet.stats.routes + 2, clamps: mainSet.stats.clamps + couplingB.stats.clamps + couplingC.stats.clamps,
    connectors: mainSet.stats.connectors + couplingB.stats.connectors + couplingC.stats.connectors, sleeved: mainSet.stats.sleeved + couplingB.stats.sleeved + couplingC.stats.sleeved, plateDepth: PLATE_DEPTH,
  };
  return {
    group, ncbCentre: NCB_AT.clone(), observerCentre: OBSERVER_AT.clone(), set, parts: info, nodes: [nodeA, nodeB, nodeC], observer, cables: [mainSet, couplingB, couplingC], ncb, obs, restPoints, stats,
    dispose: () => { owned.forEach((o) => o.dispose()); [nodeA, nodeB, nodeC].forEach((n) => n.dispose()); observer.dispose(); [mainSet, couplingB, couplingC].forEach((c) => c.dispose()); },
  };
}
