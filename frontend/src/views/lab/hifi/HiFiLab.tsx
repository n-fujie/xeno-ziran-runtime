import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import type { LabRecord } from '../labScene';
import { buildLab, type Lab, type Quality } from './assemblies';
import { chamberFloor, physToView, type V3 } from './coords';
import {
  CATEGORY_TEXT, allEvents, bayOf, ignitions, inspect, levels, mediation, provenance, specs, transfers, transitions,
  type Layer, type Selection,
} from './model';

// M8 high-fidelity laboratory view. It draws a recorded or streamed run and nothing else: every layer-A object is at
// its recorded MuJoCo position (coords.ts), every layer-B object reflects recorded runtime or system state (model.ts),
// layer C is architecture without scientific claim. The viewer never sends anything to a run except the existing live
// controls (pause / resume / stop) owned by the parent view.

type CamMode = 'overview' | 'domain' | 'apparatus' | 'operation' | 'transfer' | 'sensor' | 'free';
const CAM_MODES: [CamMode, string][] = [['overview', 'Overview'], ['domain', 'Domain'], ['apparatus', 'Apparatus'],
  ['operation', 'Operation'], ['transfer', 'Transfer'], ['sensor', 'Sensor'], ['free', 'Free']];
const QUALITY: Quality[] = ['performance', 'balanced', 'high'];
const HIGHLIGHT = 12;
const PANEL_MS = 250;  // live side-panel refresh period

export type Perf = { quality: Quality; fps: number; frameMs: { mean: number; p95: number; max: number }; drawCalls: number;
  triangles: number; geometries: number; heapMB: number | null; frames: number };

type Props = { rec: LabRecord; index: number; tick: number; playing: boolean; rate: number; live: boolean; controls: ReactNode;
  onSeek: (i: number) => void; status: ReactNode };

function readQuality(): Quality {
  const q = new URLSearchParams(location.search).get('quality');
  return (QUALITY as string[]).includes(q ?? '') ? (q as Quality) : 'balanced';
}

export default function HiFiLab({ rec, index, tick, playing, rate, live, controls, onSeek, status }: Props) {
  const mount = useRef<HTMLDivElement>(null);
  const [quality, setQuality] = useState<Quality>(readQuality);
  const url = useMemo(() => new URLSearchParams(location.search), []);
  const [layers, setLayers] = useState<Record<Layer, boolean>>(() => {
    const l = url.get('layers');
    return l ? { A: l.includes('A'), B: l.includes('B'), C: l.includes('C') } : { A: true, B: true, C: true };
  });
  const [overlay, setOverlay] = useState({ coverage: true, conduits: true });
  const [cam, setCam] = useState<CamMode>(() => (CAM_MODES.map((m) => m[0]) as string[]).includes(url.get('cam') ?? '') ? url.get('cam') as CamMode : 'overview');
  const [domain, setDomain] = useState(() => url.get('domain') ?? '0');
  const [sel, setSel] = useState<Selection | null>(() => {
    const v = url.get('sel');
    if (!v) return null;
    const [kind, ...id] = v.split(':');
    return { kind: kind as Selection['kind'], id: id.join(':') };
  });
  const [sysSel, setSysSel] = useState<string | null>(() => url.get('sys'));
  const [evSel, setEvSel] = useState<string | null>(() => url.get('ev'));
  const [perf, setPerf] = useState<Perf | null>(null);
  const engine = useRef<{ lab: Lab; renderer: THREE.WebGLRenderer; camera: THREE.PerspectiveCamera; controls: OrbitControls;
    goal: { pos: THREE.Vector3; target: THREE.Vector3 } | null } | null>(null);
  const live_ = useRef({ index, playing, rate, changedAt: performance.now(), layers, overlay, cam, sel, sysSel, domain, events: new Set<string>() });

  const step = rec.steps[Math.min(index, rec.steps.length - 1)];
  const t = step?.t ?? 0;
  // recorded events of the last HIGHLIGHT steps mark their chambers / connections
  const recent = useMemo(() => {
    const out = new Set<string>();
    for (const e of rec.events) if (e.t <= t && e.t > t - HIGHLIGHT) out.add(e.chamber ?? e.pair ?? '');
    for (const e of rec.science_events ?? []) if (e.t <= t && e.t > t - HIGHLIGHT) for (const k of ['chamber', 'dst']) if (typeof e[k] === 'string') out.add(e[k] as string);
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec, t, tick]);

  useEffect(() => {
    live_.current = { ...live_.current, playing, rate, layers, overlay, cam, sel, sysSel, domain, events: recent };
    if (live_.current.index !== index) { live_.current.index = index; live_.current.changedAt = performance.now(); }
  }, [index, playing, rate, layers, overlay, cam, sel, sysSel, domain, recent]);

  // ---------------------------------------------------------------------------------------------- scene lifecycle
  useEffect(() => {
    const el = mount.current;
    if (!el || !rec.steps.length) return;
    const q = quality;
    const renderer = new THREE.WebGLRenderer({ antialias: q !== 'performance', powerPreference: 'high-performance' });
    renderer.setPixelRatio(q === 'high' ? Math.min(2, window.devicePixelRatio) : q === 'balanced' ? Math.min(1.5, window.devicePixelRatio) : 1);
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;
    renderer.shadowMap.enabled = q !== 'performance';
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050506);
    scene.fog = new THREE.FogExp2(0x050506, 0.012);  // atmospheric depth: ~4 % at 15 m, ~30 % at 50 m (no scientific claim)
    let pmrem: THREE.PMREMGenerator | null = null;
    if (q !== 'performance') {  // soft studio reflections so brushed metal shows its form (computed once)
      pmrem = new THREE.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environmentIntensity = q === 'high' ? 0.4 : 0.3;
    }
    scene.add(new THREE.HemisphereLight(0xdcdce0, 0x141416, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 1.7);
    key.position.set(18, 34, 10);
    key.castShadow = q !== 'performance';
    key.shadow.mapSize.setScalar(q === 'high' ? 2048 : 1024);
    Object.assign(key.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, near: 5, far: 80 });
    key.shadow.bias = -0.0004;
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xbfc2c8, 0.45);
    fill.position.set(-20, 12, -16);
    const counter = new THREE.DirectionalLight(0xe6e6ea, 0.35);  // low counter-light from the opposite side, no shadows
    counter.position.set(-6, 5, 24);
    scene.add(fill, counter);
    for (const [, [x, y]] of Object.entries(rec.layout?.bays ?? {})) {  // localized instrument lighting over each domain
      const l = new THREE.PointLight(0xf2f2f0, q === 'performance' ? 9 : 14, 11, 2);
      l.position.set(x, 6.2, y);
      scene.add(l);
    }
    const camera = new THREE.PerspectiveCamera(42, el.clientWidth / Math.max(1, el.clientHeight), 0.1, 300);
    camera.position.set(30, 26, 34);
    const urlPos = (k: string) => { const v = new URLSearchParams(location.search).get(k)?.split(',').map(Number); return v?.length === 3 && v.every(Number.isFinite) ? v as [number, number, number] : null; };
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.5, 0);
    const cp = urlPos('campos'), ct = urlPos('target');
    if (cp) camera.position.set(...cp);
    if (ct) controls.target.set(...ct);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI * 0.495;
    controls.minDistance = 1.2;
    controls.maxDistance = 120;
    const lab = buildLab(rec, q);
    scene.add(lab.root);
    engine.current = { lab, renderer, camera, controls, goal: null };
    (window as unknown as { __labHiFi?: unknown }).__labHiFi = { lab, rec, renderer, scene, camera,
      /** Browser-level check of the rendered scene graph against the record at the displayed step. */
      prof: { panelMs: [] as number[], applyMs: [] as number[], renderMs: [] as number[], frameMs: [] as number[] },
      state: () => ({ cam: live_.current.cam, sel: live_.current.sel, sys: live_.current.sysSel, domain: live_.current.domain,
        layers: live_.current.layers, quality: q, step: rec.steps[Math.min(live_.current.index, rec.steps.length - 1)]?.t,
        index: live_.current.index, camera: camera.position.toArray().map((v) => +v.toFixed(3)),
        target: controls.target.toArray().map((v) => +v.toFixed(3)), pixelRatio: renderer.getPixelRatio(),
        canvas: [renderer.domElement.width, renderer.domElement.height] }),
      selfTest: () => {
        const i = Math.min(live_.current.index, rec.steps.length - 1);
        lab.apply(i, 0, { coverage: true, conduits: true, events: new Set() });
        renderer.render(scene, camera);
        scene.updateMatrixWorld(true);
        const ph = rec.steps[i].physics;
        let checked = 0, worst = 0;
        const wp = new THREE.Vector3();
        scene.traverse((o) => {
          const sel = o.userData.sel as Selection | undefined;
          if (!ph || !sel || o.userData.kind === undefined) return;
          void sel;
          if (sel.kind === 'gantry' && o.userData.kind === 'carriage and tool (recorded tool tip)' && o.type === 'Group' && ph.gantries[sel.id]) {
            o.getWorldPosition(wp);
            worst = Math.max(worst, wp.distanceTo(new THREE.Vector3(...physToView(ph.gantries[sel.id].tip as V3))));
            checked++;
          }
        });
        scene.traverse((o) => {  // instanced samples: every instance matrix against the recorded sample position
          const ids = o.userData.ids as string[] | undefined;
          const im = o as THREE.InstancedMesh;
          if (!ph || !ids || !im.isInstancedMesh) return;
          const m = new THREE.Matrix4();
          ids.forEach((sid, k) => {
            if (!ph.samples[sid]) return;
            im.getMatrixAt(k, m);
            wp.setFromMatrixPosition(m).applyMatrix4(im.matrixWorld);
            worst = Math.max(worst, wp.distanceTo(new THREE.Vector3(...physToView(ph.samples[sid] as V3))));
            checked++;
          });
        });
        const count = (L: Layer) => lab.layers[L].length;
        return { step: rec.steps[i].t, positionsChecked: checked, worstPositionError: worst, layers: { A: count('A'), B: count('B'), C: count('C') },
          drawCalls: renderer.info.render.calls, triangles: renderer.info.render.triangles, quality: q };
      } };

    const ray = new THREE.Raycaster();
    const down = { x: 0, y: 0 };
    const onDown = (ev: PointerEvent) => { down.x = ev.clientX; down.y = ev.clientY; };
    const onUp = (ev: PointerEvent) => {
      if (Math.hypot(ev.clientX - down.x, ev.clientY - down.y) > 4) return;  // a drag, not a click
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = ray.intersectObjects(lab.pickables, true).find((h) => h.object.visible && (h.object.userData.sel || h.object.userData.ids));
      const ids = hit?.object.userData.ids as string[] | undefined;  // instanced samples: instance id -> sample id
      const s = (ids && hit?.instanceId !== undefined ? { kind: 'sample', id: ids[hit.instanceId] } : hit?.object.userData.sel) as Selection | undefined;
      setSel(s ?? null);
      if (s && (s.kind === 'sensor' || s.kind === 'store')) setSysSel(s.id.split(':')[0]);
    };
    renderer.domElement.addEventListener('pointerdown', onDown);
    renderer.domElement.addEventListener('pointerup', onUp);
    const onResize = () => {
      camera.aspect = el.clientWidth / Math.max(1, el.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(el);

    let raf = 0;
    const frameMs: number[] = [];
    let last = performance.now(), lastReport = last;
    const loop = () => {
      const now = performance.now();
      const dt = now - last;
      frameMs.push(dt);
      last = now;
      const L = live_.current;
      const n = rec.steps.length;
      const i = Math.min(L.index, n - 1);
      // rendering-only interpolation toward the next recorded step while a replay plays
      const frac = L.playing && !live && i + 1 < n ? Math.min(1, ((now - L.changedAt) / 1000) * L.rate) : 0;
      const tA = performance.now();
      lab.apply(i, frac, { coverage: L.overlay.coverage && L.layers.B, conduits: L.overlay.conduits && L.layers.B, events: L.events });
      const prof = (window as unknown as { __labHiFi?: { prof?: Record<string, number[]> } }).__labHiFi?.prof;
      prof?.applyMs.push(performance.now() - tA);
      for (const k of ['A', 'B', 'C'] as Layer[]) for (const o of lab.layers[k]) o.visible = L.layers[k];
      for (const o of lab.layers.C) if (o.userData.cutawayAbove !== undefined && camera.position.y > o.userData.cutawayAbove) o.visible = false;
      cameraGoal(lab, rec, i, L.cam, L.sel, L.sysSel, L.domain, engine.current!);
      const g = engine.current!.goal;
      if (g) {
        const k = 0.085;
        camera.position.lerp(g.pos, k);
        controls.target.lerp(g.target, k);
        if (camera.position.distanceTo(g.pos) < 0.05 && L.cam !== 'operation' && L.cam !== 'transfer') engine.current!.goal = null;
      }
      controls.update();
      const tR = performance.now();
      renderer.render(scene, camera);
      prof?.renderMs.push(performance.now() - tR);
      prof?.frameMs.push(dt);
      if (prof && prof.renderMs.length > 4000) for (const k of Object.keys(prof)) prof[k].splice(0, 2000);
      (window as unknown as { __labHiFiFrames?: number }).__labHiFiFrames = ((window as unknown as { __labHiFiFrames?: number }).__labHiFiFrames ?? 0) + 1;
      if (now - lastReport > 1000) {
        const ms = frameMs.splice(0).slice(1).sort((a, b) => a - b);
        const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory;
        const p: Perf = { quality: q, fps: Math.round(1000 / (ms.reduce((a, b) => a + b, 0) / Math.max(1, ms.length))),
          frameMs: { mean: +(ms.reduce((a, b) => a + b, 0) / Math.max(1, ms.length)).toFixed(2), p95: +(ms[Math.floor(ms.length * 0.95)] ?? 0).toFixed(2),
            max: +(ms[ms.length - 1] ?? 0).toFixed(2) },
          drawCalls: renderer.info.render.calls, triangles: renderer.info.render.triangles, geometries: renderer.info.memory.geometries,
          heapMB: mem ? +(mem.usedJSHeapSize / 1048576).toFixed(1) : null, frames: ms.length };
        setPerf(p);
        (window as unknown as { __labPerf?: Perf[] }).__labPerf = [...((window as unknown as { __labPerf?: Perf[] }).__labPerf ?? []), p].slice(-120);
        lastReport = now;
      }
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onDown);
      renderer.domElement.removeEventListener('pointerup', onUp);
      controls.dispose();
      lab.dispose();
      pmrem?.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
      engine.current = null;
    };
    // the scene is rebuilt when the record identity or the quality changes; state updates go through live_
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec.config, rec.chambers, quality]);

  useEffect(() => { if (engine.current) engine.current.goal = null; if (cam !== 'free') primeGoal(); }, [cam, sel, sysSel, domain]);  // eslint-disable-line react-hooks/exhaustive-deps
  function primeGoal() { const e = engine.current; if (e) cameraGoal(e.lab, rec, index, cam, sel, sysSel, domain, e, true); }

  // ---------------------------------------------------------------------------------------------- panels
  // The side panel is decoupled from the 3D frames: in a live run it recomputes at most every PANEL_MS and only when
  // the step changed (the scene still follows every streamed step). Replays update it immediately.
  const [panelIndex, setPanelIndex] = useState(index);
  const lastPanel = useRef(0);
  useEffect(() => {
    if (!live) { setPanelIndex(index); return; }
    const wait = Math.max(0, PANEL_MS - (performance.now() - lastPanel.current));
    const id = setTimeout(() => { lastPanel.current = performance.now(); setPanelIndex(index); }, wait);
    return () => clearTimeout(id);
  }, [index, live]);
  const pIndex = Math.min(panelIndex, rec.steps.length - 1);
  const pT = rec.steps[pIndex]?.t ?? 0;
  const panel = useMemo(() => {
    const tPanel = performance.now();
    const sysList = specs(rec);
    const activeSys = sysSel ?? sysList[0]?.sid ?? null;
    const compare = sysList.map((s) => ({ sid: s.sid, kind: s.kind, lv: levels(rec, pIndex, s.sid) }));  // once per system
    const lv = compare.find((c) => c.sid === activeSys)?.lv ?? null;
    const ign = activeSys && pT % 4 === 0 ? ignitions(rec, pIndex, activeSys) : [];
    const allTrs = transfers(rec, pT);  // once; shared with the mediation table
    const out = {
      sysList, activeSys, compare, lv, ign, insp: sel ? inspect(rec, pIndex, sel) : null, med: mediation(rec, pIndex, allTrs),
      trs: allTrs.slice(-8).reverse(), trans: transitions(rec, pT).slice(-14).reverse(),
      evs: allEvents(rec).filter((e) => e.t <= pT && e.type !== 'leg_complete' && e.type !== 'variable_candidate').slice(-40).reverse(),
      prov: evSel ? provenance(rec, evSel) : null,
    };
    (window as unknown as { __labHiFi?: { prof?: Record<string, number[]> } }).__labHiFi?.prof?.panelMs.push(performance.now() - tPanel);
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec, pIndex, pT, sysSel, sel, evSel, live ? panelIndex : tick]);
  const { sysList, activeSys, compare, lv, ign, insp, med, trs, trans, evs, prov } = panel;
  const domains = Object.keys(rec.layout?.bays ?? {});

  return (
    <div className="lab hifi">
      <div className="lab-stage" ref={mount} data-testid="hifi-stage" />
      <aside className="lab-side small hifi-side">
        {controls}
        <div className="lab-status">{status}</div>
        <div className="hifi-row">
          <span className="dim">quality</span>
          {QUALITY.map((q) => <button key={q} className={q === quality ? 'on' : ''} onClick={() => setQuality(q)}>{q}</button>)}
        </div>
        <div className="hifi-row">
          <span className="dim">layers</span>
          {(['A', 'B', 'C'] as Layer[]).map((k) => (
            <label key={k} title={k === 'A' ? CATEGORY_TEXT[1] : k === 'B' ? CATEGORY_TEXT[2] : CATEGORY_TEXT[4]}>
              <input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} />
              {k === 'A' ? 'A physical' : k === 'B' ? 'B scientific' : 'C architecture'}</label>))}
        </div>
        <div className="hifi-row">
          <span className="dim">overlays</span>
          <label><input type="checkbox" checked={overlay.coverage} onChange={(e) => setOverlay({ ...overlay, coverage: e.target.checked })} />observation</label>
          <label><input type="checkbox" checked={overlay.conduits} onChange={(e) => setOverlay({ ...overlay, conduits: e.target.checked })} />connections</label>
        </div>
        <div className="hifi-row">
          <span className="dim">camera</span>
          {CAM_MODES.map(([m, l]) => <button key={m} className={m === cam ? 'on' : ''} onClick={() => setCam(m)}>{l}</button>)}
          {cam === 'domain' && <select value={domain} onChange={(e) => setDomain(e.target.value)}>{domains.map((d) => <option key={d} value={d}>domain {d}</option>)}</select>}
        </div>
        {perf && <div className="mono dim" data-testid="hifi-perf">{perf.fps} fps · frame {perf.frameMs.mean} ms (p95 {perf.frameMs.p95}) · {perf.drawCalls} draw calls · {Math.round(perf.triangles / 1000)}k tris{perf.heapMB !== null ? ` · heap ${perf.heapMB} MB` : ''}</div>}

        {sysList.length > 0 && <>
          <h4>System · what exists, is observed, accessible, selected, executed</h4>
          <div className="hifi-row">{sysList.map((s) => <button key={s.sid} className={s.sid === activeSys ? 'on' : ''} onClick={() => setSysSel(s.sid)}>{s.sid} {s.kind}</button>)}</div>
          {lv && <table className="hifi-levels mono"><tbody>
            <tr><td>exists (executable in the laboratory)</td><td>{step.physics ? lv.exists.length : 'unmeasured'}</td></tr>
            <tr><td>observed (recorded coverage)</td><td>{lv.observed.length} chambers</td></tr>
            <tr><td>accessible (selectable now)</td><td>{lv.accessible.length}</td></tr>
            <tr><td>selected (so far)</td><td>{lv.selected.length}{lv.pending ? ` · pending ${lv.pending.join('→')}` : ''}</td></tr>
            <tr><td>executed: delivered (so far)</td><td>{lv.executed.length}</td></tr>
          </tbody></table>}
          {ign.length > 0 && <div className="mono dim">ignition (derived): {ign.join(', ')} became accessible at t{t}</div>}
          {compare.length > 1 && <table className="hifi-levels mono" data-testid="hifi-compare"><tbody>
            <tr><td>system</td><td>observes</td><td>accessible</td><td>selected</td><td>delivered</td></tr>
            {compare.map((c) => <tr key={c.sid}><td>{c.sid} {c.kind}</td><td>{c.lv?.observed.length ?? '—'}</td><td>{c.lv?.accessible.length ?? '—'}</td>
              <td>{c.lv?.selected.length ?? '—'}</td><td>{c.lv?.executed.length ?? '—'}</td></tr>)}
          </tbody></table>}
          <div className="dim">The three systems share one decision rule; they differ in observation, reach, memory, isolation and
            resources (configuration-dependent heterogeneity, M4).</div>
        </>}

        {insp && <div className="lab-inspect" data-testid="hifi-inspect">
          <h4>{insp.title}</h4>
          <div className="dim">layer {insp.layer} · {CATEGORY_TEXT[insp.category]}</div>
          <table className="mono hifi-fields"><tbody>{insp.fields.map((f, k) => (
            <tr key={k}><td>{f.label}</td><td>{f.status === 'recorded' ? f.value : <span className={`avail ${f.status.replace(/ /g, '-')}`}>{f.status === 'derived' ? `${f.value} (derived)` : f.status}</span>}
              {f.note ? <span className="dim"> — {f.note}</span> : null}</td></tr>))}</tbody></table>
        </div>}

        {med.length > 0 && <>
          <h4>Physical resources (mediation)</h4>
          <table className="mono hifi-med"><thead><tr><th>gantry</th><th>health</th><th>queue</th><th>legs by system</th><th>shared</th></tr></thead>
            <tbody>{med.map((m) => (
              <tr key={m.key} className={m.failed ? 'failed' : ''} onClick={() => setSel({ kind: 'gantry', id: m.key })}>
                <td>{m.key}</td><td>{m.failed ? 'FAILED' : m.health.toFixed(2)}</td><td>{m.queue}</td>
                <td>{m.group ? 'n/a (per-carriage legs not recorded)' : Object.entries(m.legsBySystem).map(([k, n]) => `${k === 'unattributed' ? 'in transit (attributed at completion)' : k} ${n}`).join(' · ') || '—'}</td>
                <td>{m.group ? `private (${m.group})` : m.shared ? 'yes' : 'no'}</td></tr>))}</tbody></table>
          <div className="mono">{trs.map((x) => (
            <div key={x.tid} className={`tr ${x.state.replace(/ /g, '-')}`}>transfer {x.tid}{x.system ? ` (${x.system})` : ''} {x.src}→{x.dst}: <b>{x.state}</b></div>))}</div>
          <div className="dim">“Delivered” only when the runtime accepted the material (recorded material_delivered). A transfer whose
            sample reached the chamber but whose delivery was refused is “delivery blocked” — physical transport completion is not delivery.</div>
        </>}

        <h4>Scientific transitions</h4>
        <ul className="lab-events mono">{trans.map((x, k) => (
          <li key={k} onClick={() => { if (x.eventId) setEvSel(x.eventId); }}>t{x.t} <b>{x.kind}</b>{x.system ? ` · ${x.system}` : ''} {x.where.join('→')}
            <br /><span className="dim">{x.derived ? 'derived: ' : ''}{x.rule}{x.eventId ? ` · ${x.eventId}` : ''}</span></li>))}</ul>

        <h4>Recorded events · provenance</h4>
        {prov && <div className="lab-inspect" data-testid="hifi-provenance">
          <div className="mono"><b>{prov.event.id}</b> t{prov.event.t} {prov.event.type}</div>
          <div className="mono">attribution: {prov.attribution}</div>
          {prov.preceding.length > 0 && <div className="mono dim">before: {prov.preceding.map((f) => `${f.label} = ${f.value}`).join(' · ')}</div>}
          <div className="mono">initiated by: {prov.initiating.map((e) => `${e.id} ${e.type} (t${e.t})`).join(', ') || '— (none recorded)'}</div>
          <div className="mono">consequences: {prov.consequences.map((e) => `${e.id} ${e.type} (t${e.t})`).join(', ') || '— (none recorded)'}</div>
          <button onClick={() => onSeek(rec.steps.findIndex((s) => s.t === prov.event.t))}>go to t{prov.event.t}</button>
        </div>}
        <ul className="lab-events mono" data-testid="hifi-events">{evs.map((e) => (
          <li key={e.id} className={evSel === e.id ? 'on' : ''} onClick={() => setEvSel(e.id)}>{e.id} t{e.t} {e.type.replace(/_/g, ' ')}
            {' '}{String(e.raw.system ?? e.raw.bay ?? '')} {String(e.raw.chamber ?? e.raw.pair ?? (e.raw.src ? `${String(e.raw.src)}→${String(e.raw.dst)}` : ''))}</li>))}</ul>
        <p className="dim">Layer A (physical, MuJoCo): chamber floors and walls, ports, samples, carriages and tools at recorded positions;
          rails, bridges and masts represent the slide joints. The roof is cut away while the camera is above it. Layer B (scientific, runtime): containment louvres (1 − mean gate of
          entering connections), activity bars, memory columns, sensors, stores, connections, pending experiments, observed
          chambers. Layer C (architecture): platforms, columns, roof, walls and walkway carry no scientific claim.</p>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------- camera modes
/** A close-up camera position for a target: tries viewing directions starting radially outward from the installation
 *  centre and keeps the first that is not inside any chamber housing (so the view is never blocked by a wall). */
export function closeView(rec: LabRecord, target: THREE.Vector3, dist: number, height: number, prefer?: number,
  blocked: (p: THREE.Vector3) => boolean = () => false): THREE.Vector3 {
  const out = new THREE.Vector3(target.x, 0, target.z);
  const r = out.length();
  // instruments stand outside the gantry envelopes (M8.2), on the bays' outer sides: look at them from the hall side
  const radial = r > 1e-3 ? Math.atan2(out.z, out.x) : 0;
  const base = prefer ?? (r > 16.5 ? radial + Math.PI : radial);
  const inside = (p: THREE.Vector3) => {
    const pr = Math.hypot(p.x, p.z);
    if (pr > 22 || (Math.abs(pr - 20.3) < 0.7 && p.y < 2.6)) return true;  // beyond the walkway / in the service housing ring
    return rec.chambers.some((c) => Math.abs(p.x - c.position[0]) < 1.75 && Math.abs(p.z - c.position[2]) < 1.75) && p.y < 1.4;
  };
  for (const da of [0.55, -0.55, 0, 1.1, -1.1, 1.7, -1.7, Math.PI]) {
    for (const k of [1, 1.35, 1.7]) {
      const a = base + da;
      const p = new THREE.Vector3(target.x + Math.cos(a) * dist * k, target.y + height * k, target.z + Math.sin(a) * dist * k);
      if (!inside(p) && !blocked(p)) return p;
    }
  }
  // every candidate occluded: fall back to the first one that is not inside a solid
  for (const da of [0.55, -0.55, 0, 1.1, -1.1, 1.7, -1.7, Math.PI]) {
    const a = base + da;
    const p = new THREE.Vector3(target.x + Math.cos(a) * dist, target.y + height, target.z + Math.sin(a) * dist);
    if (!inside(p)) return p;
  }
  return target.clone().add(new THREE.Vector3(0, dist + height, 0));
}


const viewCache = new WeakMap<Lab, Map<string, THREE.Vector3>>();
/** True when solid geometry (not lines, not the selected object itself) lies between a camera position and the target. */
function occluded(lab: Lab, target: THREE.Vector3): (p: THREE.Vector3) => boolean {
  const ray = new THREE.Raycaster();
  const shown = (o: THREE.Object3D | null): boolean => { for (let x = o; x; x = x.parent) if (!x.visible) return false; return true; };
  return (p) => {
    const d = target.clone().sub(p);
    const len = d.length();
    ray.set(p, d.normalize());
    ray.far = len - 0.45;  // hits within 0.45 m of the target are the selected object itself
    lab.root.updateMatrixWorld(true);
    return ray.intersectObject(lab.root, true).some((h) => (h.object as THREE.Mesh).isMesh && shown(h.object)
      && !((h.object as THREE.Mesh).material as THREE.Material).transparent);
  };
}

function cameraGoal(lab: Lab, rec: LabRecord, i: number, mode: CamMode, sel: Selection | null, sysSel: string | null, domain: string,
  e: { goal: { pos: THREE.Vector3; target: THREE.Vector3 } | null; camera: THREE.PerspectiveCamera }, prime = false): void {
  const set = (target: THREE.Vector3, offset: THREE.Vector3) => { e.goal = { pos: target.clone().add(offset), target }; };
  if (mode === 'free' || (!prime && e.goal === null && mode !== 'operation' && mode !== 'transfer')) return;
  if (mode === 'overview') return set(new THREE.Vector3(0, 1.5, 0), new THREE.Vector3(30, 26, 34));
  if (mode === 'domain') {
    const b = rec.layout?.bays[domain];
    if (!b) return;
    const out = new THREE.Vector3(b[0], 0, b[1]).normalize();
    return set(new THREE.Vector3(b[0], 1.2, b[1]), out.multiplyScalar(9).add(new THREE.Vector3(0, 7.5, 0)));
  }
  if (mode === 'apparatus') {
    const p = sel ? lab.focus(sel) : null;
    // a memory store is viewed along its slot face (world −x), from above the neighbouring walls; others radially
    if (!p || !sel) return;
    // the viewing offset is chosen once per selection (raycast occlusion test), then follows the object
    const cache = (viewCache.get(lab) ?? viewCache.set(lab, new Map()).get(lab))!;
    const key = `${sel.kind}:${sel.id}`;
    let off = cache.get(key);
    if (!off) {
      // a chamber is viewed from above its walls, so its contents (e.g. a refused sample) and its shutters are both visible
      const [d, h] = sel.kind === 'store' ? [2.6, 1.9] : sel.kind === 'chamber' ? [3.0, 2.9] : [3.2, 1.1];
      const pos = closeView(rec, p, d, h, undefined, occluded(lab, p));
      off = pos.sub(p);
      cache.set(key, off);
    }
    e.goal = { pos: p.clone().add(off), target: p };
    return;
  }
  const s = rec.steps[i];
  if (mode === 'sensor') {
    const sid = sysSel ?? specs(rec)[0]?.sid;
    const st = sid ? s.science?.[sid] : undefined;
    if (!st || !sid) return;
    const head = lab.focus({ kind: 'sensor', id: `${sid}:head` });
    const pts = st.coverage.map((c) => rec.chambers.find((x) => x.cid === c)).filter(Boolean).map((c) => new THREE.Vector3(...chamberFloor(c!.position as V3)));
    if (!head) return;
    // nothing observed (e.g. every observed chamber closed): look from the sensor across its own domain
    const own = rec.layout?.bays[bayOf(st.sensor)];
    const centre = pts.length ? pts.reduce((a, b) => a.add(b), new THREE.Vector3()).multiplyScalar(1 / pts.length)
      : own ? new THREE.Vector3(own[0], 0.8, own[1]) : head.clone();
    const back = head.clone().sub(centre).setY(0).normalize().multiplyScalar(2.2);
    e.goal = { pos: head.clone().add(back).add(new THREE.Vector3(0, 2.2, 0)), target: centre };
    return;
  }
  // operation / transfer tracking: follow the carried sample (recorded), else the pending experiment's target chamber
  const ph = s.physics;
  const sid = sysSel ?? specs(rec)[0]?.sid;
  const pend = sid ? s.science?.[sid]?.pending : null;
  let target: THREE.Vector3 | null = null;
  if (ph) {
    const carried = Object.values(ph.gantries).map((g) => g.carrying).filter(Boolean) as string[];
    const want = mode === 'transfer' && sel?.kind === 'sample' ? sel.id : pend ? carried.find((c) => c.split('#')[0] === pend[0]) ?? carried[0] : carried[0];
    if (want && ph.samples[want]) target = new THREE.Vector3(...physToView(ph.samples[want] as V3));
  }
  if (!target && pend) {
    const c = rec.chambers.find((x) => x.cid === pend[1]);
    if (c) target = new THREE.Vector3(...chamberFloor(c.position as V3));
  }
  if (target) e.goal = { pos: closeView(rec, target, 3.4, 1.2), target };
}
