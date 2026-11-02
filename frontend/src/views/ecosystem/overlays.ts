// XENO ECOSYSTEM — the scientific overlay layers drawn over the habitat arena. Each layer is a function of a MEOS record at a tick (layers.ts), drawn in
// the arena's local cell coordinates; the layers are rebuilt when the tick, the selection or the toggles change, never per render frame.
import * as THREE from 'three';
import type { AdStatic, Dependency, MeosRecord, MfsOut } from './meosApi';
import { ENTITY_NAMES, firingView, frameAt, historyPaths, meosView, relations, sssView, xenobodyHulls, type EntityName, type LayerId } from './layers';
import { WORLD, type Arena } from './megastructure';

export interface OverlayInput {
  rec: MeosRecord; t: number; arena: Arena; layers: Set<LayerId>; ad: { A1: AdStatic; A2: AdStatic } | null; mfs: MfsOut | null;
  partitions: Record<string, { label: string; components: string[] }>; selected: EntityName | null;
}

const labelCache = new Map<string, THREE.SpriteMaterial>();
/** A monochrome text label (cached per text); the cache is released with ``disposeLabels``. */
export function label(text: string, scale = 0.5, screen = false): THREE.Sprite {
  const key = screen ? `screen:${text}` : text;
  let mat = labelCache.get(key);
  if (!mat) {
    const cv = document.createElement('canvas');
    const g = cv.getContext('2d')!;
    g.font = '28px "IBM Plex Mono", Menlo, monospace';
    const w = Math.ceil(g.measureText(text).width) + 20;
    cv.width = w; cv.height = 44;
    g.font = '28px "IBM Plex Mono", Menlo, monospace';
    g.fillStyle = 'rgba(0,0,0,0.62)'; g.fillRect(0, 0, w, 44);
    g.strokeStyle = 'rgba(255,255,255,0.55)'; g.strokeRect(0.5, 0.5, w - 1, 43);
    g.fillStyle = '#f2f2f4'; g.textBaseline = 'middle'; g.fillText(text, 10, 23);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false, sizeAttenuation: !screen });  // screen: constant size on screen
    mat.userData = { w, h: 44 };
    labelCache.set(key, mat);
  }
  const s = new THREE.Sprite(mat);
  const { w, h } = mat.userData as { w: number; h: number };
  s.scale.set((w / h) * scale, scale, 1);
  s.renderOrder = 10;
  return s;
}
export function disposeLabels() { labelCache.forEach((m) => { m.map?.dispose(); m.dispose(); }); labelCache.clear(); }

const solid = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, depthTest: false });
const soft = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.45, depthTest: false });
const dashed = (size: number, gap: number, op = 0.9) => new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: size, gapSize: gap, transparent: true, opacity: op, depthTest: false });

/** A line drawn three times with a small offset: a heavier stroke than the one-pixel hardware line. */
function fat(pts: THREE.Vector3[], mat: THREE.Material, closed = false): THREE.Group {
  const g = new THREE.Group();
  for (const [dx, dz] of [[0, 0], [0.05, 0], [0, 0.05]]) g.add(line(pts.map((p) => p.clone().add(new THREE.Vector3(dx, 0, dz))), mat, closed));
  return g;
}

function line(pts: THREE.Vector3[], mat: THREE.Material, closed = false): THREE.Line {
  const l = closed ? new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), mat) : new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
  if ((mat as THREE.LineDashedMaterial).isLineDashedMaterial) l.computeLineDistances();
  l.renderOrder = 9;
  return l;
}
const arc = (a: THREE.Vector3, b: THREE.Vector3, lift: number, n = 16) => Array.from({ length: n + 1 }, (_, i) => {
  const f = i / n;
  return new THREE.Vector3(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f + Math.sin(f * Math.PI) * lift, a.z + (b.z - a.z) * f);
});
const rect = (a: THREE.Vector3, b: THREE.Vector3, y: number) => [new THREE.Vector3(a.x, y, a.z), new THREE.Vector3(b.x, y, a.z), new THREE.Vector3(b.x, y, b.z), new THREE.Vector3(a.x, y, b.z)];

export function disposeGroup(g: THREE.Object3D) {
  g.traverse((o) => {
    const m = o as THREE.Mesh;
    if (m.geometry) m.geometry.dispose();
    if ((o as THREE.Line).isLine) (m.material as THREE.Material).dispose();
  });
  g.clear();
}

export function buildOverlays(inp: OverlayInput): THREE.Group {
  const { rec, t, arena, layers, ad, mfs, partitions, selected } = inp;
  const g = new THREE.Group();
  g.name = 'overlays';
  const fr = frameAt(rec, t);
  const L = (x: number, y: number, h = 0.12) => arena.local(x, y).setY(h);
  const pos = { A1: L(fr.A1.x, fr.A1.y), A2: L(fr.A2.x, fr.A2.y) };
  const half = (arena.n * 1.0) / 2;
  const rectOf = (c: [number, number], r: number, y: number) => rect(arena.local(c[0] - r, c[1] - r).sub(new THREE.Vector3(0.5, 0, 0.5)), arena.local(c[0] + r, c[1] + r).add(new THREE.Vector3(0.5, 0, 0.5)), y);
  const shown = (n: EntityName) => !selected || selected === n;

  if (layers.has('operational')) {
    const rels = relations(rec, t, 14);
    for (const r of rels) {
      const age = t - r.tick, op = Math.max(0.2, 1 - age / 16);
      const m = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: op, depthTest: false });
      const cell = r.cell ?? [fr.A1.x, fr.A1.y];
      const at = L(cell[0], cell[1], 0.15);
      if (r.kind === 'alters') g.add(line([at, at.clone().setY(1.9)], m));
      else if (r.kind === 'detects') g.add(line(arc(L(cell[0], cell[1], 1.9), pos.A2.clone().setY(1.0), 1.2), m));
      else if (r.kind === 'reconfigures') g.add(line(arc(at.clone().setY(0.9), pos.A1.clone().setY(0.9), 1.6), m));
      else if (r.kind === 'fires-on') g.add(line(arc(pos.A2.clone().setY(1.2), pos.A1.clone().setY(1.2), 1.0), m));
    }
    const s = label(`${rels.length} recorded relations in the last 14 ticks`, 0.42); s.position.set(0, 4.3, -half - 0.8); g.add(s);
  }

  if (layers.has('meos')) {
    const mv = meosView(rec, t);
    const a = pos.A1.clone().setY(1.0), b = pos.A2.clone().setY(1.0);
    const loop = [a, arc(a, b, 1.1)[8], b, arc(b, a, -0.2)[8]].map((p) => p.clone());
    const style = mv.label === 'ACTIVE' ? solid : mv.label === 'DEGRADED' ? dashed(0.3, 0.2) : dashed(0.1, 0.4, 0.5);
    for (const off of mv.label === 'ACTIVE' ? [0, 0.05, -0.05] : [0]) g.add(line(loop.map((p) => p.clone().add(new THREE.Vector3(0, off, 0))), style, true));
    const s = label(`MEOS ${mv.label}${mv.dependency ? ' - ' + brief(mv.dependency) : ''}`, 0.5); s.position.set(0, 5.1, -half - 0.8); g.add(s);
    if (mv.dependency?.entity && (mv.label === 'COLLAPSED' || mv.label === 'DEGRADED')) {
      const p = (mv.dependency.entity === 'A1' ? pos.A1 : pos.A2).clone().setY(2.6);
      const x = line([p.clone().add(new THREE.Vector3(-0.4, 0.4, 0)), p.clone().add(new THREE.Vector3(0.4, -0.4, 0))], solid), y = line([p.clone().add(new THREE.Vector3(-0.4, -0.4, 0)), p.clone().add(new THREE.Vector3(0.4, 0.4, 0))], solid);
      g.add(x, y);
    }
  }

  if (layers.has('address') && ad) {
    for (const n of ENTITY_NAMES) {
      if (!shown(n)) continue;
      const e = fr[n], a = ad[n];
      g.add(fat(rectOf([e.x, e.y], a.operational_boundary.sensor_radius, 0.14), solid, true));
      if (a.operational_boundary.footprint > 0) g.add(line(rectOf([e.x, e.y], a.operational_boundary.footprint, 0.16), dashed(0.18, 0.12), true));
      const s = label(`${n} (${e.x},${e.y}) r=${a.operational_boundary.sensor_radius} win=${a.temporal_window.window} persist=${a.temporal_window.persist} v=${a.speed}`, 0.4);
      s.position.copy(pos[n]).add(new THREE.Vector3(0, n === 'A1' ? 2.8 : 3.4, 0)); g.add(s);
    }
    if (ad.A1.operational_boundary.arena_radius != null) g.add(line(rectOf([(arena.n - 1) / 2, (arena.n - 1) / 2], ad.A1.operational_boundary.arena_radius, 0.2), dashed(0.4, 0.2), true));
  }

  if (layers.has('sss') && ad) {
    for (const n of ENTITY_NAMES) {
      if (!shown(n)) continue;
      const v = sssView(ad, n)!;
      const p = pos[n].clone().setY(0.2);
      const reach = new THREE.Vector3(v.sensorCells, 0, 0);
      g.add(line([p.clone().add(new THREE.Vector3(0, 0, -1.2)), p.clone().add(reach).add(new THREE.Vector3(0, 0, -1.2))], solid));
      g.add(line([p.clone().add(new THREE.Vector3(0, 0, -1.4)), p.clone().add(new THREE.Vector3(0, 0, -1.0))], solid));
      g.add(line([p.clone().add(reach).add(new THREE.Vector3(0, 0, -1.4)), p.clone().add(reach).add(new THREE.Vector3(0, 0, -1.0))], solid));
      const arrow = p.clone().add(new THREE.Vector3(0, 0.6, 1.2));
      g.add(line([arrow, arrow.clone().add(new THREE.Vector3(v.stepsPerTick, 0, 0))], solid));
      const s = label(`${n} scale ${v.scale} size ${v.size} speed ${v.speed}: reach ${v.sensorCells} cells, ${v.stepsPerTick} cells/tick`, 0.36);
      s.position.copy(p).add(new THREE.Vector3(0, 2.2, 1.4)); g.add(s);
    }
  }

  if (layers.has('history')) {
    const paths = historyPaths(rec, t, 60);
    const fires = rec.events.filter((e) => e.kind === 'fire' && e.tick <= t && e.tick > t - 60);
    for (const h of paths) {
      const cur = fires.find((e) => e.tick === h.tick && e.actor === h.entity), prev = fires.filter((e) => e.actor === h.entity && e.tick < h.tick).pop();
      if (!cur || !prev) continue;
      const c = cur.cell as [number, number], p = prev.cell as [number, number];
      const m = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: Math.min(1, 0.25 + h.reentry * 6), depthTest: false });
      g.add(line(arc(L(p[0], p[1], 2.2), L(c[0], c[1], 2.2), 0.9), m));
    }
    for (const n of ENTITY_NAMES) {
      const e = fr[n];
      const s = label(`${n} history trace ${e.h.toFixed(2)}  threshold -${e.reentry.toFixed(3)}`, 0.38); s.position.copy(pos[n]).add(new THREE.Vector3(0, n === 'A1' ? 3.4 : 4.0, 0)); g.add(s);
    }
  }

  if (layers.has('firing')) {
    for (const n of ENTITY_NAMES) {
      if (!shown(n)) continue;
      const f = firingView(rec, n, t);
      const ringR = Math.max(0.15, Math.min(1.6, f.ratio) * 0.9);
      const pts = Array.from({ length: 40 }, (_, i) => new THREE.Vector3(Math.cos((i / 40) * 6.283) * ringR, 0, Math.sin((i / 40) * 6.283) * ringR));
      g.add(line(pts.map((q) => q.add(pos[n]).setY(0.22)), f.state === 'firing' ? solid : soft, true));
      const th = Array.from({ length: 40 }, (_, i) => new THREE.Vector3(Math.cos((i / 40) * 6.283) * 0.9, 0, Math.sin((i / 40) * 6.283) * 0.9).add(pos[n]).setY(0.22));
      g.add(line(th, dashed(0.12, 0.1, 0.7), true));
      const why = f.state === 'blocked' ? `blocked: ${f.failed[0]}` : f.state === 'refractory' ? `refractory ${f.refireIn}` : f.state === 'firing' ? `firing, expires in ${f.expiresIn}` : f.state;
      const s = label(`${n} ${why}  d/theta ${f.ratio.toFixed(2)}`, 0.38); s.position.copy(pos[n]).add(new THREE.Vector3(0, n === 'A1' ? 2.2 : 2.6, 0)); g.add(s);
    }
  }

  if (layers.has('mfs')) {
    const comps = ['A2', 'sensor_resource', 'sensor_alteration', 'interaction_channel', 'feedback', 'resource_renewal', 'environmental_persistence', 'history', 'resource_gradient'];
    const base = new THREE.Vector3(half + 1.4, 0.3, -half + 0.6);
    comps.forEach((c, i) => {
      const retained = mfs?.retained.includes(c);
      const known = mfs !== null;
      const s = label(`${known ? (retained ? '[x]' : '[ ]') : '[?]'} ${c}${known ? (retained ? ' retained' : ' removable') : ''}`, 0.36);
      s.position.copy(base).add(new THREE.Vector3(2.4, 0.4 + i * 0.5, 0)); g.add(s);
    });
    const link = line([pos.A1.clone().setY(0.8), pos.A2.clone().setY(0.8)], mfs?.retained.includes('interaction_channel') ? solid : dashed(0.2, 0.25, 0.6));
    g.add(link);
    for (const n of ENTITY_NAMES) g.add(line(rectOf([fr[n].x, fr[n].y], ad?.[n].operational_boundary.sensor_radius ?? 2, 0.13), (n === 'A1' ? mfs?.retained.includes('sensor_resource') : mfs?.retained.includes('sensor_alteration')) ? solid : dashed(0.2, 0.2, 0.5), true));
    if (!mfs) { const s = label('MFS: not computed (run: find the minimal configuration)', 0.4); s.position.set(0, 5.8, -half - 0.8); g.add(s); }
  }

  if (layers.has('xenobody')) {
    const hulls = xenobodyHulls(rec, t, ad, partitions);
    hulls.forEach((h, i) => {
      const pad = 0.5 + i * 0.45;
      const xs: number[] = [], zs: number[] = [];
      for (const r of h.rects) { xs.push(r[0], r[2]); zs.push(r[1], r[3]); }
      for (const p of h.points) { xs.push(p[0]); zs.push(p[1]); }
      if (!xs.length) return;
      const a = arena.local(Math.min(...xs), Math.min(...zs)).sub(new THREE.Vector3(pad + 0.5, 0, pad + 0.5)), b = arena.local(Math.max(...xs), Math.max(...zs)).add(new THREE.Vector3(pad + 0.5, 0, pad + 0.5));
      const mat = i === 0 ? solid : i === 1 ? dashed(0.45, 0.25) : dashed(0.08, 0.2);
      g.add(fat(rect(a, b, 0.3 + i * 0.02), mat, true));
      const s = label(`${h.id}  ${h.label}`, 0.36); s.position.set((a.x + b.x) / 2, 3.2 + i * 0.7, a.z - 0.6); g.add(s);
      if (h.includesDepot) {
        const d = WORLD.depot.clone().sub(WORLD.habitat).setY(0); const to = d.clone().normalize().multiplyScalar(half * 1.5);
        g.add(line([new THREE.Vector3(b.x, 0.3, a.z), to.setY(0.3)], dashed(0.1, 0.2)));
      }
    });
  }
  return g;
}

function brief(d: NonNullable<Dependency>): string {
  return d.detail.length > 70 ? d.detail.slice(0, 67) + '...' : d.detail;
}
