import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { api } from '../../api/client';
import { useExperiment } from '../research/common';
import { frameAt, PHYS_Y0, validate, type Frame, type LabRecord } from './labScene';

// XENO–ZIRAN 3D laboratory (Level 1 component): replays a recorded runtime execution.
//   runtime-derived (drawn from xzr/lab/apparatus.py values): containment shutters (gates entering a chamber), state lamp
//     (glow = ignitions, size = memory), conduits (live connections between chambers)
//   physical (drawn from recorded MuJoCo state, physical runs only): chamber walls, material samples, gantries, ports
//   static scenery (no runtime meaning): floor, grid, overhead frames
// Highlights mark recorded events only. Nothing drawn here feeds back into the run.

const FLOOR_Y = 0.3;  // chamber floor top in the view
const RECORDS = ['lab-m3-physical-9100', 'lab-m2-run-9100'];

type ChamberObj = { group: THREE.Group; lamp: THREE.Mesh; shutters: THREE.Mesh[]; ring: THREE.Mesh; h: number };
type GantryObj = { carriage: THREE.Mesh; rod: THREE.Mesh; lamp: THREE.Mesh };

const metal = (c: number, m = 0.7, r = 0.35) => new THREE.MeshStandardMaterial({ color: c, metalness: m, roughness: r });

function buildChamber(pos: [number, number, number], half: number, physical: boolean, wallH: number): ChamberObj {
  const g = new THREE.Group();
  const H = physical ? wallH + 0.9 : 2 * half;  // containment height (runtime gate) above the floor
  g.position.set(pos[0], FLOOR_Y, pos[2]);
  const W = 2 * half;
  const glass = new THREE.Mesh(new THREE.BoxGeometry(W, H, W),
    new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.06, roughness: 0.05, depthWrite: false }));
  glass.position.y = H / 2;
  const frame = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(W, H, W)), new THREE.LineBasicMaterial({ color: 0xc8c8ce }));
  frame.position.y = H / 2;
  const plinth = new THREE.Mesh(new THREE.BoxGeometry(W * 1.08, 0.3, W * 1.08), metal(0x26262a));
  plinth.position.y = -0.15;
  g.add(glass, frame, plinth);
  if (physical) {  // the physical walls the gantry must lift samples over
    for (let k = 0; k < 4; k++) {
      const w = new THREE.Mesh(new THREE.BoxGeometry(W, wallH, 0.06), metal(0x55555b, 0.8, 0.4));
      w.rotation.y = (k * Math.PI) / 2;
      w.position.set(Math.sin((k * Math.PI) / 2) * half, wallH / 2, Math.cos((k * Math.PI) / 2) * half);
      g.add(w);
    }
  }
  const lamp = new THREE.Mesh(new THREE.IcosahedronGeometry(0.32, 1),
    new THREE.MeshStandardMaterial({ color: 0x1b1b1e, emissive: 0xffffff, emissiveIntensity: 0, metalness: 0.4, roughness: 0.6, flatShading: true }));
  lamp.position.y = physical ? H - 0.35 : H / 2;
  const shutters: THREE.Mesh[] = [];
  for (let k = 0; k < 4; k++) {
    const p = new THREE.Mesh(new THREE.BoxGeometry(W, 1, 0.04), metal(0x8a8a90, 0.85, 0.3));
    p.rotation.y = (k * Math.PI) / 2;
    p.position.set(Math.sin((k * Math.PI) / 2) * half * 1.02, 0, Math.cos((k * Math.PI) / 2) * half * 1.02);
    shutters.push(p);
    g.add(p);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(half * 1.55, 0.04, 8, 48), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 }));
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.02;
  g.add(lamp, ring);
  return { group: g, lamp, shutters, ring, h: H };
}

function applyFrame(f: Frame, objs: Map<string, ChamberObj>, conduitGroup: THREE.Group, pos: Map<string, THREE.Vector3>,
  gantries: Map<string, GantryObj>, samples: Map<string, THREE.Mesh>) {
  for (const c of f.chambers) {
    const o = objs.get(c.cid);
    if (!o) continue;
    const h = Math.max(0.001, c.shutterClosure * o.h);
    for (const p of o.shutters) {  // panels descend from the top of the containment by the recorded closure
      p.scale.y = h;
      p.position.y = o.h - h / 2;
      p.visible = c.shutterClosure > 0.005;
    }
    (o.lamp.material as THREE.MeshStandardMaterial).emissiveIntensity = 2.2 * c.coreGlow;
    o.lamp.scale.setScalar(c.coreScale);
    (o.ring.material as THREE.MeshBasicMaterial).opacity = c.highlight ? 0.9 * (1 - (f.t - c.highlight.t) / 12) : 0;
  }
  conduitGroup.clear();
  for (const k of f.conduits) {
    const a = pos.get(k.a), b = pos.get(k.b);
    const oa = objs.get(k.a), ob = objs.get(k.b);
    if (!a || !b || !oa || !ob) continue;
    const ya = FLOOR_Y + oa.h, yb = FLOOR_Y + ob.h;
    const mid = a.clone().add(b).multiplyScalar(0.5);
    mid.y = Math.max(ya, yb) + 1.2 + a.distanceTo(b) * 0.08;
    const curve = new THREE.QuadraticBezierCurve3(a.clone().setY(ya), mid, b.clone().setY(yb));
    const hl = k.highlight ? 1 - (f.t - k.highlight.t) / 12 : 0;
    const severed = k.count === 0;
    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, depthWrite: false,
      opacity: severed ? 0.7 * hl : Math.min(0.9, 0.035 + 0.03 * Math.log2(1 + k.count) + 0.75 * hl) });
    conduitGroup.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 20, hl > 0 ? 0.06 : 0.012 + 0.004 * Math.min(6, k.count), 5, false), mat));
  }
  for (const g of f.gantries) {  // recorded tool-tip position; the rod hangs from the overhead frame
    const o = gantries.get(g.bay);
    if (!o) continue;
    const [x, y, z] = g.tip;
    o.carriage.position.set(x, y + 0.18, z);
    const top = 6.2;
    o.rod.scale.y = Math.max(0.01, top - (y + 0.3));
    o.rod.position.set(x, (top + y + 0.3) / 2, z);
    (o.carriage.material as THREE.MeshStandardMaterial).color.setHex(g.failed ? 0x2a2a2e : 0xd8d8de);
    (o.lamp.material as THREE.MeshBasicMaterial).opacity = g.failed ? 0.05 : 0.25 + 0.75 * g.health;
    o.lamp.position.set(x, y + 0.42, z);
  }
  for (const s of f.samples) {
    const m = samples.get(s.sid);
    if (!m) continue;
    m.position.set(...s.position);
    (m.material as THREE.MeshStandardMaterial).emissiveIntensity = s.carried ? 0.35 : 0;
  }
}

export default function LabView() {
  const [name, setName] = useState(RECORDS[0]);
  const [available, setAvailable] = useState<string[]>(RECORDS);
  const { data, error } = useExperiment<LabRecord>(name);
  const rec = useMemo(() => (data ? validate(data) : null), [data]);
  const mount = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(8);
  const [fps, setFps] = useState(0);
  const [sel, setSel] = useState<string | null>(null);
  const state = useRef<{ apply: (f: Frame) => void } | null>(null);
  const frame = useMemo(() => (rec ? frameAt(rec, index) : null), [rec, index]);

  useEffect(() => {
    void api.experiments().then((l) => {
      const labs = l.map((e) => e.name).filter((n) => n.startsWith('lab-'));
      if (labs.length) setAvailable([...RECORDS.filter((r) => labs.includes(r)), ...labs.filter((r) => !RECORDS.includes(r))]);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!rec || !mount.current) return;
    const el = mount.current;
    const physical = !!rec.layout;
    const half = rec.layout?.chamber_half ?? 1.3;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060607);
    scene.fog = new THREE.Fog(0x060607, 32, 75);
    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.1, 200);
    camera.position.set(24, 20, 28);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.5, 0);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x101012, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(10, 30, 12);
    scene.add(key);
    const floor = new THREE.Mesh(new THREE.CircleGeometry(40, 64), metal(0x0e0e10, 0.8, 0.28));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.3;
    const grid = new THREE.GridHelper(80, 80, 0x2a2a30, 0x17171b);
    grid.position.y = -0.29;
    scene.add(floor, grid);
    const objs = new Map<string, ChamberObj>();
    const pos = new Map<string, THREE.Vector3>();
    for (const c of rec.chambers) {
      const o = buildChamber(c.position, half, physical, rec.layout?.wall_height ?? 0.7);
      o.group.userData.cid = c.cid;
      objs.set(c.cid, o);
      pos.set(c.cid, new THREE.Vector3(c.position[0], FLOOR_Y, c.position[2]));
      scene.add(o.group);
    }
    const gantries = new Map<string, GantryObj>();
    const samples = new Map<string, THREE.Mesh>();
    if (rec.layout) {
      const L = rec.layout;
      for (const [, [x, y]] of Object.entries(L.ports)) {  // physical handoff ports
        const port = new THREE.Mesh(new THREE.BoxGeometry(2 * L.port_half, 0.1, 2 * L.port_half), metal(0x6a6a70, 0.8, 0.3));
        port.position.set(x, PHYS_Y0, y);
        const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 0.55, 8), metal(0x2c2c31));
        leg.position.set(x, PHYS_Y0 - 0.3, y);
        scene.add(port, leg);
      }
      for (const [bay, [x, y]] of Object.entries(L.bays)) {  // overhead frame (static) + gantry (recorded)
        const frame = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(11, 0.2, 11)), new THREE.LineBasicMaterial({ color: 0x3a3a40 }));
        frame.position.set(x, 6.3, y);
        scene.add(frame);
        for (const [dx, dz] of [[-5.5, -5.5], [5.5, -5.5], [-5.5, 5.5], [5.5, 5.5]]) {
          const post = new THREE.Mesh(new THREE.BoxGeometry(0.16, 6.6, 0.16), metal(0x24242a));
          post.position.set(x + dx, 3.0, y + dz);
          scene.add(post);
        }
        const carriage = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.36, 0.34), metal(0xd8d8de, 0.85, 0.25));
        const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1, 8), metal(0x9a9aa0));
        const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.08, 10, 10), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 1 }));
        gantries.set(bay, { carriage, rod, lamp });
        scene.add(carriage, rod, lamp);
      }
      for (const c of rec.chambers) {
        const s = new THREE.Mesh(new THREE.BoxGeometry(2 * L.sample_half, 2 * L.sample_half, 2 * L.sample_half),
          new THREE.MeshStandardMaterial({ color: 0x3c3c40, emissive: 0xffffff, emissiveIntensity: 0, metalness: 0.2, roughness: 0.85 }));
        samples.set(c.cid, s);
        scene.add(s);
      }
    }
    const conduitGroup = new THREE.Group();
    scene.add(conduitGroup);
    state.current = { apply: (f) => applyFrame(f, objs, conduitGroup, pos, gantries, samples) };
    const ray = new THREE.Raycaster();
    const onClick = (ev: MouseEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = ray.intersectObjects([...objs.values()].map((o) => o.group), true)[0];
      let g: THREE.Object3D | null = hit?.object ?? null;
      while (g && !g.userData.cid) g = g.parent;
      setSel(g ? (g.userData.cid as string) : null);
    };
    renderer.domElement.addEventListener('click', onClick);
    const onResize = () => {
      camera.aspect = el.clientWidth / Math.max(1, el.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener('resize', onResize);
    let raf = 0, frames = 0, last = performance.now();
    const loop = () => {
      controls.update();
      renderer.render(scene, camera);
      frames++;
      const now = performance.now();
      if (now - last > 1000) { setFps(Math.round((frames * 1000) / (now - last))); frames = 0; last = now; }
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      renderer.domElement.removeEventListener('click', onClick);
      controls.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
      state.current = null;
    };
  }, [rec]);

  useEffect(() => { if (frame) state.current?.apply(frame); }, [frame]);

  useEffect(() => {
    if (!playing || !rec) return;
    const id = setInterval(() => setIndex((i) => (i + 1 >= rec.steps.length ? (setPlaying(false), i) : i + 1)), 1000 / rate);
    return () => clearInterval(id);
  }, [playing, rate, rec]);

  const picker = (
    <select value={name} onChange={(e) => { setPlaying(false); setIndex(0); setName(e.target.value); }}>
      {available.map((n) => <option key={n} value={n}>{n.replace(/^lab-/, '')}</option>)}</select>
  );
  if (!rec || !frame) return <div className="panel-view dim">{picker} {error ? `No laboratory record (${error}).` : 'loading…'}</div>;
  const s = rec.steps[frame.index];
  const k = sel ? rec.chambers.findIndex((c) => c.cid === sel) : -1;
  const phys = s.physics;
  const str = (v: unknown) => (v === undefined || v === null ? '' : String(v));
  const timeline = [
    ...frame.events.map((e) => ({ t: e.t, kind: 'apparatus', text: `${e.type.replace('_', ' ')} ${e.chamber ?? e.pair} ${e.before}→${e.after}`, cause: e.cause.join(', ') })),
    ...frame.physicalEvents.filter((e) => e.type !== 'leg_complete' && e.type !== 'sample_grasped').map((e) => ({
      t: e.t, kind: 'physical', text: `${e.type.replace(/_/g, ' ')} ${str(e.src ?? e.bay)}${e.dst ? '→' + str(e.dst) : ''}`,
      cause: [e.operation ? `operation:${str(e.operation)}` : '', e.causal_event !== undefined ? `causal_event:${str(e.causal_event)}` : '',
        str(e.reason), Array.isArray(e.via) && e.via.length ? `via ${(e.via as string[]).join(', ')}` : ''].filter(Boolean).join(', '),
    })),
  ].sort((a, b) => b.t - a.t).slice(0, 50);
  return (
    <div className="lab">
      <div className="lab-stage" ref={mount} />
      <aside className="lab-side small">
        <div className="lab-status"><b>Recorded runtime execution, replayed.</b> Level 1 component. Simulation-internal
          {rec.layout ? ' (rigid-body physics within declared approximations)' : ''}: not a physical laboratory; not evidence of
          autonomous science.</div>
        <div className="lab-controls">
          {picker}
          <button onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Run'}</button>
          <button onClick={() => setIndex(Math.max(0, frame.index - 1))}>−1</button>
          <button onClick={() => setIndex(Math.min(rec.steps.length - 1, frame.index + 1))}>+1</button>
          <button onClick={() => { setPlaying(false); setIndex(0); }}>Reset</button>
          <select value={rate} onChange={(e) => setRate(Number(e.target.value))}>
            {[2, 8, 24].map((r) => <option key={r} value={r}>{r} steps/s</option>)}</select>
        </div>
        <input type="range" min={0} max={rec.steps.length - 1} value={frame.index} onChange={(e) => setIndex(Number(e.target.value))} />
        <div className="mono dim">step {frame.t} / {rec.steps.length} · {fps} fps · runtime {s.fingerprint.slice(0, 12)}{phys ? ` · physics ${phys.fingerprint}` : ''}</div>
        <div className="mono dim">config gen {str(rec.config.gen_seed)} · seed {str(rec.config.seed)} · n {str(rec.config.n)} · physics {String(!!rec.layout)}</div>
        {phys && <div className="mono dim">gantries: {Object.entries(phys.gantries).map(([b, g]) => `${b}:${g.failed ? 'FAILED' : g.health.toFixed(2)}`).join(' ')}</div>}
        {k >= 0 && (
          <div className="lab-inspect">
            <h4>Chamber {sel}</h4>
            <div className="mono">configurations {rec.chambers[k].size} · shutter {s.shutter[k]} · activity {s.activity[k]} · memory {s.memory[k]}</div>
            {phys && <div className="mono">material: {(phys.contents[sel as string] ?? []).join(', ') || 'none'}</div>}
            <div className="mono dim">conduits: {Object.entries(s.conduits).filter(([p]) => p.split('|').includes(sel as string)).map(([p, n]) => `${p.replace(sel as string, '').replace('|', '')}×${n}`).join(' ') || 'none'}</div>
          </div>
        )}
        <h4>Recorded events (≤ step {frame.t})</h4>
        <ul className="lab-events mono">
          {timeline.map((e, i) => (
            <li key={i} className={frame.t - e.t < 12 ? 'on' : ''} onClick={() => { setPlaying(false); setIndex(rec.steps.findIndex((x) => x.t === e.t)); }}>
              t{e.t} [{e.kind}] {e.text}<br /><span className="dim">cause: {e.cause || '—'}</span></li>
          ))}
        </ul>
        <p className="dim">Runtime-derived: shutters = 1 − mean gate of connections entering the chamber; lamp glow = share of its
          configurations that ignited; lamp size = retained memory; conduits = live connections between chambers.
          {rec.layout ? ' Physical (recorded MuJoCo state): walls, samples, gantries (lamp = health), ports.' : ''} Rings and bright
          conduits mark recorded events only. Floor, grid and overhead frames are static scenery.</p>
      </aside>
    </div>
  );
}
