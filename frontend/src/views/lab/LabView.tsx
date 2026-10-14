import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useExperiment } from '../research/common';
import { frameAt, validate, type Frame, type LabRecord } from './labScene';

// XENO–ZIRAN 3D laboratory (Level 1 component): replays a recorded runtime execution. Chambers, containment shutters,
// material cores and conduits are drawn from runtime-derived apparatus values (labScene.ts); highlights mark recorded
// apparatus events only. The static gantry and floor carry no runtime meaning. Nothing drawn here feeds back into the run.

const RECORD = 'lab-m2-run-9100';
const BOX = 2.6;

type ChamberObj = { group: THREE.Group; core: THREE.Mesh; shutters: THREE.Mesh[]; ring: THREE.Mesh; frame: THREE.LineSegments };

function metal(c: number, m = 0.7, r = 0.35) {
  return new THREE.MeshStandardMaterial({ color: c, metalness: m, roughness: r });
}

function buildChamber(pos: [number, number, number]): ChamberObj {
  const g = new THREE.Group();
  g.position.set(pos[0], pos[1], pos[2]);
  const glass = new THREE.Mesh(new THREE.BoxGeometry(BOX, BOX, BOX),
    new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.07, roughness: 0.05, metalness: 0, depthWrite: false }));
  const frame = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(BOX, BOX, BOX)),
    new THREE.LineBasicMaterial({ color: 0xc8c8ce }));
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(BOX * 0.62, BOX * 0.68, 0.32, 24), metal(0x2a2a2e));
  plinth.position.y = -BOX / 2 - 0.16;
  const head = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.28, 0.9, 12), metal(0x9a9aa0));
  head.position.y = BOX / 2 + 0.45;
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.55, 1),
    new THREE.MeshStandardMaterial({ color: 0x1b1b1e, emissive: 0xffffff, emissiveIntensity: 0, metalness: 0.4, roughness: 0.6, flatShading: true }));
  const shutters: THREE.Mesh[] = [];
  for (let k = 0; k < 4; k++) {
    const p = new THREE.Mesh(new THREE.BoxGeometry(BOX, 1, 0.05), metal(0x6e6e74, 0.85, 0.3));
    p.rotation.y = (k * Math.PI) / 2;
    p.position.set(Math.sin((k * Math.PI) / 2) * BOX / 2, 0, Math.cos((k * Math.PI) / 2) * BOX / 2);
    shutters.push(p);
    g.add(p);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(BOX * 0.78, 0.04, 8, 48),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0 }));
  ring.rotation.x = Math.PI / 2;
  ring.position.y = -BOX / 2;
  g.add(glass, frame, plinth, head, core, ring);
  return { group: g, core, shutters, ring, frame };
}

function applyFrame(f: Frame, objs: Map<string, ChamberObj>, conduitGroup: THREE.Group, pos: Map<string, THREE.Vector3>) {
  for (const c of f.chambers) {
    const o = objs.get(c.cid);
    if (!o) continue;
    const h = Math.max(0.001, c.shutterClosure * BOX);
    for (const p of o.shutters) {  // panels descend from the top by the recorded closure
      p.scale.y = h;
      p.position.y = BOX / 2 - h / 2;
      p.visible = c.shutterClosure > 0.005;
    }
    (o.core.material as THREE.MeshStandardMaterial).emissiveIntensity = 2.2 * c.coreGlow;
    o.core.scale.setScalar(c.coreScale);
    const age = c.highlight ? f.t - c.highlight.t : -1;
    (o.ring.material as THREE.MeshBasicMaterial).opacity = c.highlight ? 0.9 * (1 - age / 12) : 0;
  }
  conduitGroup.clear();
  for (const k of f.conduits) {
    const a = pos.get(k.a), b = pos.get(k.b);
    if (!a || !b) continue;
    const mid = a.clone().add(b).multiplyScalar(0.5);
    mid.y = Math.max(a.y, b.y) + BOX * 0.9 + a.distanceTo(b) * 0.08;
    const curve = new THREE.QuadraticBezierCurve3(a.clone().setY(a.y + BOX / 2 + 0.9), mid, b.clone().setY(b.y + BOX / 2 + 0.9));
    const hl = k.highlight ? 1 - (f.t - k.highlight.t) / 12 : 0;
    const severed = k.count === 0;
    // live conduits stay faint (their number is the topology, drawn as opacity); recorded events light them up
    const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, depthWrite: false,
      opacity: severed ? 0.7 * hl : Math.min(0.9, 0.035 + 0.03 * Math.log2(1 + k.count) + 0.75 * hl) });
    conduitGroup.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 20, hl > 0 ? 0.06 : 0.012 + 0.004 * Math.min(6, k.count), 5, false), mat));
  }
}

export default function LabView() {
  const { data, error } = useExperiment<LabRecord>(RECORD);
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
    if (!rec || !mount.current) return;
    const el = mount.current;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060607);
    scene.fog = new THREE.Fog(0x060607, 30, 70);
    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.1, 200);
    camera.position.set(26, 22, 30);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 3, 0);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x101012, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(10, 30, 12);
    scene.add(key);
    // static environment (no runtime meaning): floor, grid, gantry rails over each bay
    const floor = new THREE.Mesh(new THREE.CircleGeometry(40, 64), metal(0x0e0e10, 0.8, 0.28));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.4;
    const grid = new THREE.GridHelper(80, 80, 0x2a2a30, 0x17171b);
    grid.position.y = -0.39;
    scene.add(floor, grid);
    const objs = new Map<string, ChamberObj>();
    const pos = new Map<string, THREE.Vector3>();
    for (const c of rec.chambers) {
      const o = buildChamber(c.position);
      o.group.userData.cid = c.cid;
      objs.set(c.cid, o);
      pos.set(c.cid, new THREE.Vector3(...c.position));
      scene.add(o.group);
    }
    const bays = new Map<string, THREE.Vector3[]>();
    for (const c of rec.chambers) bays.set(c.cid.split('.')[0], [...(bays.get(c.cid.split('.')[0]) ?? []), new THREE.Vector3(...c.position)]);
    for (const ps of bays.values()) {
      const cen = ps.reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / ps.length);
      const rail = new THREE.Mesh(new THREE.BoxGeometry(9, 0.25, 0.25), metal(0x3a3a40));
      rail.position.set(cen.x, 9.6, cen.z);
      rail.lookAt(0, 9.6, 0);
      rail.rotateY(Math.PI / 2);
      for (const sx of [-4.2, 4.2]) {
        const post = new THREE.Mesh(new THREE.BoxGeometry(0.22, 10, 0.22), metal(0x2c2c31));
        post.position.set(sx, -4.9, 0);
        rail.add(post);
      }
      scene.add(rail);
    }
    const conduitGroup = new THREE.Group();
    scene.add(conduitGroup);
    state.current = { apply: (f) => applyFrame(f, objs, conduitGroup, pos) };
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

  if (!rec || !frame) return <div className="panel-view dim">{error ? `No laboratory record (${error}).` : 'loading…'}</div>;
  const s = rec.steps[frame.index];
  const k = sel ? rec.chambers.findIndex((c) => c.cid === sel) : -1;
  return (
    <div className="lab">
      <div className="lab-stage" ref={mount} />
      <aside className="lab-side small">
        <div className="lab-status"><b>Recorded runtime execution, replayed.</b> Level 1 component. Simulation-internal:
          no physical apparatus; not evidence of autonomous science.</div>
        <div className="lab-controls">
          <button onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Run'}</button>
          <button onClick={() => setIndex(Math.max(0, frame.index - 1))}>−1</button>
          <button onClick={() => setIndex(Math.min(rec.steps.length - 1, frame.index + 1))}>+1</button>
          <button onClick={() => { setPlaying(false); setIndex(0); }}>Reset</button>
          <select value={rate} onChange={(e) => setRate(Number(e.target.value))}>
            {[2, 8, 24].map((r) => <option key={r} value={r}>{r} steps/s</option>)}</select>
        </div>
        <input type="range" min={0} max={rec.steps.length - 1} value={frame.index} onChange={(e) => setIndex(Number(e.target.value))} />
        <div className="mono dim">step {frame.t} / {rec.steps.length} · {fps} fps · runtime {s.fingerprint.slice(0, 12)}</div>
        <div className="mono dim">config gen {String(rec.config.gen_seed)} · seed {String(rec.config.seed)} · n {String(rec.config.n)}</div>
        {k >= 0 && (
          <div className="lab-inspect">
            <h4>Chamber {sel}</h4>
            <div className="mono">configurations {rec.chambers[k].size} · shutter {s.shutter[k]} · activity {s.activity[k]} · memory {s.memory[k]}</div>
            <div className="mono dim">conduits: {Object.entries(s.conduits).filter(([p]) => p.split('|').includes(sel as string)).map(([p, n]) => `${p.replace(sel as string, '').replace('|', '')}×${n}`).join(' ') || 'none'}</div>
          </div>
        )}
        <h4>Recorded apparatus events (≤ step {frame.t})</h4>
        <ul className="lab-events mono">
          {[...frame.events].reverse().slice(0, 40).map((e, i) => (
            <li key={i} className={frame.t - e.t < 12 ? 'on' : ''} onClick={() => { setPlaying(false); setIndex(rec.steps.findIndex((x) => x.t === e.t)); }}>
              t{e.t} {e.type.replace('_', ' ')} {e.chamber ?? e.pair} {e.before}→{e.after}<br /><span className="dim">cause: {e.cause.join(', ')}</span></li>
          ))}
        </ul>
        <p className="dim">Drawn from runtime state: shutters = 1 − mean gate of connections entering the chamber; core glow =
          share of its configurations that ignited this step; core size = its retained memory; conduits = live connections
          between chambers. Rings and bright conduits mark recorded events only. Gantry and floor are static scenery.</p>
      </aside>
    </div>
  );
}
