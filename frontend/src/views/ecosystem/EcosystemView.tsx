import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/examples/jsm/postprocessing/BokehPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import Chart from '../../components/Chart';
import {
  ablation, addressSweep, adAt, boundary, decodeFields, fieldAt, FULL_OBSERVATION, getSpec, historyCompare, mfs as mfsApi, replayMeos, runMeos, sssSweep, STATUS_VALUE,
  type AblationRow, type BoundaryOut, type HistoryOut, type Intervention, type Label, type MfsOut, type Observation, type RunOut, type Spec,
} from './meosApi';
import {
  ENTITY_NAMES, LAYERS, addressView, firingView, frameAt, interactionGraph, meosMembership, meosView, mfsMembership, statusSegments, trajectories,
  type EntityName, type LayerId,
} from './layers';
import { ANNOTATIONS, CAMERA_PRESETS, WORLD, buildMegastructure, type Megastructure, type Quality, type Trial } from './megastructure';
import { buildOverlays, disposeGroup, disposeLabels, label as makeLabel } from './overlays';
import { bodyState, studioEnvironment } from './bodies';
import { buildDeviceLayer, deviceState, observationCoverage, SPACES, type DeviceLayer } from './researchDevice';
import ExperimentsPane from './ExperimentsPane';
import TechnicalView from './TechnicalView';
import './ecosystem.css';

// XENO ECOSYSTEM — a real-time view of MEOS-0, a deterministic simulation (backend/xzr/meos). The page draws a record and nothing else: the simulation
// tick (the record's frames) and the render frame rate are separate clocks, the camera never reaches the simulation, and every value in the panels is
// read from the record. The surrounding megastructure is static architecture and is labelled as such.

type Tab = 'experiment' | 'inspect' | 'reductions' | 'studies' | 'technical' | 'data';
type Sel = { kind: 'entity'; name: EntityName } | { kind: 'trial'; i: number } | null;
const QUALITY: Quality[] = ['performance', 'balanced', 'high'];
const PRESETS: Record<string, Intervention[]> = {
  baseline: [], 'a2-removed': [{ tick: 60, op: 'REMOVE', target: 'A2' }], 'no-history': [{ tick: 0, op: 'DISABLE_HISTORY', mode: 'removed' }],
  'interaction-cut': [{ tick: 100, op: 'ISOLATE', target: 'interaction_channel' }],
  // the second-stage demonstration: a cut, its restoration with a resource pulse, a lowered renewal efficiency, an Address Domain fragmentation and its restoration
  'recovery-demo': [
    { tick: 100, op: 'ISOLATE', target: 'interaction_channel' }, { tick: 150, op: 'RECONNECT', target: 'interaction_channel' },
    { tick: 151, op: 'ALTER_RESOURCE', inject: { x: 3, y: 6, amount: 2 } }, { tick: 190, op: 'RECONFIGURE', path: 'environment.renew_efficiency', value: 0.85 },
    { tick: 200, op: 'ADDRESS', target: 'A2', mode: 'fragment', fraction: 0.5 }, { tick: 225, op: 'ADDRESS', target: 'both', mode: 'restore' },
  ],
};

export interface Perf { fps: number; frameMs: number; p95: number; drawCalls: number; triangles: number; instances: number; edgeSegments: number; simMs: number; heapMB: number | null; frames: number; quality: Quality }

export default function EcosystemView() {
  const url = useMemo(() => new URLSearchParams(location.search), []);
  const [quality, setQuality] = useState<Quality>(() => (QUALITY as string[]).includes(url.get('quality') ?? '') ? (url.get('quality') as Quality) : 'balanced');
  const mount = useRef<HTMLDivElement>(null);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [out, setOut] = useState<RunOut | null>(null);
  const [ivs, setIvs] = useState<Intervention[]>(() => PRESETS[url.get('preset') ?? 'baseline'] ?? []);
  const [seed, setSeed] = useState(1);
  const [horizon, setHorizon] = useState(() => ([240, 360, 480].includes(Number(url.get('horizon'))) ? Number(url.get('horizon')) : 240));
  const [obs, setObs] = useState<Observation>(FULL_OBSERVATION);
  const [conn, setConn] = useState<{ m2: string; m2w: number; phil: string; channel: string }>(() => ({ m2: ['direct', 'delayed', 'noisy'].includes(url.get('m2') ?? '') ? url.get('m2')! : 'none', m2w: 1, phil: ['expression', 'scorekeeping', 'revision'].includes(url.get('phil') ?? '') ? url.get('phil')! : 'none', channel: 'clean' }));
  const fullObs = JSON.stringify(obs) === JSON.stringify(FULL_OBSERVATION);
  const [tick, setTick] = useState(() => Math.max(0, Number(url.get('tick') ?? 0) || 0));
  const [playing, setPlaying] = useState(url.get('play') === '1');
  const [rate, setRate] = useState(12);
  const [layers, setLayers] = useState<Set<LayerId>>(() => new Set((url.get('layers') ?? 'physical,meos').split(',').filter((l) => LAYERS.some((x) => x.id === l)) as LayerId[]));
  const [cam, setCam] = useState(url.get('cam') ?? 'overview');
  const [follow, setFollow] = useState<EntityName | null>(null);
  const [sel, setSel] = useState<Sel>(null);
  const [tab, setTab] = useState<Tab>(() => (['ncb', 'observer'].includes(url.get('tech') ?? '') ? 'technical' : 'experiment'));
  const [techWhich, setTechWhich] = useState<'ncb' | 'observer'>(() => (url.get('tech') === 'observer' ? 'observer' : 'ncb'));
  const [techProbe, setTechProbe] = useState(() => url.get('probe') ?? (url.get('tech') === 'observer' ? 'O1' : 'A1'));
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [replay, setReplay] = useState<string | null>(null);
  const [abl, setAbl] = useState<AblationRow[] | null>(null);
  const [mfsRes, setMfsRes] = useState<MfsOut | null>(null);
  const [bnd, setBnd] = useState<BoundaryOut | null>(null);
  const [hist, setHist] = useState<HistoryOut | null>(null);
  const [sss, setSss] = useState<Array<{ axis: string; value: number; status: Label; cycles: number; first_collapse_tick: number | null }> | null>(null);
  const [addr, setAddr] = useState<Array<{ path: string; value: number; status: Label; cycles: number; first_collapse_tick: number | null }> | null>(null);
  const [perf, setPerf] = useState<Perf | null>(null);
  const [ready, setReady] = useState(false);
  const chrome = url.get('chrome') !== '0';  // chrome=0: the stage alone (panels and HUD hidden), used for the reference-composition captures

  const rec = out?.record ?? null;
  const fields = useMemo(() => (rec ? decodeFields(rec.fields, rec.frames.length) : null), [rec]);
  const live = useRef({ playing, rate, tick, playhead: tick, follow, goal: null as null | { pos: THREE.Vector3; target: THREE.Vector3 }, nFrames: 0 });
  const eng = useRef<{ device: DeviceLayer; composer: EffectComposer | null; mega: Megastructure; renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls; overlays: THREE.Group; simMs: number[] } | null>(null);
  const setTickRef = useRef(setTick), setPlayingRef = useRef(setPlaying);
  setTickRef.current = setTick; setPlayingRef.current = setPlaying;

  // ---------------------------------------------------------------------------------------------- run / interventions
  const runCfg = useMemo(() => {
    const c: Record<string, unknown> = { seed, horizon };
    if (conn.m2 !== 'none') c.m2 = { sense: conn.m2, weight: conn.m2w, ...(conn.m2 === 'delayed' ? { delay: 3 } : {}), ...(conn.m2 === 'noisy' ? { noise: 0.05 } : {}) };
    if (conn.phil !== 'none') c.phil = { mode: conn.phil, ...(conn.channel === 'noisy' ? { noise: 0.15 } : {}), ...(conn.channel === 'slow' ? { delay: 6 } : {}) };
    return c;
  }, [seed, horizon, conn]);
  const execute = useCallback(async (list: Intervention[], keepTick: number | null) => {
    setBusy('running the simulation'); setErr(null);
    try {
      const r = await runMeos(runCfg, list, fullObs ? undefined : { ...obs });
      setOut(r); setIvs(list); setReplay(null);
      const t = Math.min(keepTick ?? 0, r.record.frames.length - 1);
      live.current.playhead = t; setTick(t);
    } catch (e) { setErr(String(e)); } finally { setBusy(null); }
  }, [runCfg, fullObs, obs]);

  useEffect(() => { getSpec().then(setSpec).catch((e) => setErr(`the MEOS API is not available on this server (${e}). XENO ECOSYSTEM needs the local runtime.`)); }, []);
  useEffect(() => {
    void execute(ivs, tick);
    // re-run only when the run's own parameters change (not on every tick or intervention)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runCfg, obs]);

  const intervene = (iv: Omit<Intervention, 'tick'>) => {
    if (ivs.length >= 64) { setErr('at most 64 interventions per run'); return; }
    void execute([...ivs, { ...iv, tick: Math.min(tick, (rec?.frames.length ?? 1) - 1) } as Intervention], tick);
  };
  const doReplay = async () => {
    if (!rec) return;
    setBusy('replaying from the recorded seed, configuration and interventions');
    try {
      const r = await replayMeos(rec.config, rec.interventions, rec.result_digest);
      setReplay(r.identical ? `replay identical: ${r.got.slice(0, 16)}...` : `REPLAY DIFFERS: ${r.expected.slice(0, 12)} vs ${r.got.slice(0, 12)}`);
      live.current.playhead = 0; setTick(0); setPlaying(true);
    } catch (e) { setErr(String(e)); } finally { setBusy(null); }
  };

  // ---------------------------------------------------------------------------------------------- reductions and experiments
  const baseCfg = runCfg;
  const wrap = async (name: string, fn: () => Promise<void>) => { setBusy(name); setErr(null); try { await fn(); } catch (e) { setErr(String(e)); } finally { setBusy(null); } };
  const runAblation = () => wrap('ablation: removing each component in turn', async () => {
    if (!spec) return;
    const subsets = [...spec.components.map((c) => [c]), ['A2', 'history'], ['resource_gradient', 'history']];
    setAbl((await ablation(baseCfg, subsets, [seed])).rows);
  });
  const runMfs = (exhaustive: boolean) => wrap(exhaustive ? 'exhaustive search of all 512 retained sets' : 'minimal operational configuration (backward elimination)', async () => setMfsRes(await mfsApi(baseCfg, exhaustive, 160)));
  const runBoundary = () => wrap('XenoBody boundary specifications', async () => setBnd(await boundary(baseCfg)));
  const runHistory = () => wrap('H+ against H-', async () => setHist(await historyCompare(baseCfg)));
  const runSss = () => wrap('SSS perturbation', async () => setSss((await sssSweep(baseCfg)).rows));
  const runAddr = () => wrap('Address Domain perturbation', async () => setAddr((await addressSweep(baseCfg)).rows));

  useEffect(() => {
    if (url.get('reductions') === '1' && spec && !abl && !busy) void runAblation();
    // a one-time automatic run for deep links (?reductions=1), e.g. the subsurface-laboratory capture
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec]);
  const settled = !!rec && !busy && (url.get('reductions') !== '1' || !!abl);

  // ---------------------------------------------------------------------------------------------- scene lifecycle
  useEffect(() => {
    const el = mount.current;
    if (!el) return;
    const q = quality;
    const renderer = new THREE.WebGLRenderer({ antialias: q !== 'performance', powerPreference: 'high-performance', preserveDrawingBuffer: url.get('capture') === '1' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, q === 'performance' ? 1 : q === 'balanced' ? 1.5 : 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020202);
    scene.fog = new THREE.FogExp2(0x020202, 0.0034);
    let sceneEnv: THREE.Texture | null = null;
    if (q !== 'performance') {
      const pm = new THREE.PMREMGenerator(renderer);
      scene.environment = sceneEnv = pm.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environmentIntensity = 0.22;
    }
    scene.add(new THREE.HemisphereLight(0xffffff, 0x050505, 0.32));
    const key = new THREE.DirectionalLight(0xffffff, 1.7); key.position.set(120, 180, 80); scene.add(key);
    const rim = new THREE.DirectionalLight(0xffffff, 0.6); rim.position.set(-140, 70, -120); scene.add(rim);
    const shaftLights: THREE.PointLight[] = [];
    for (const y of [-6, -40, -74, -104]) { const l = new THREE.PointLight(0xffffff, 650, 90, 1.6); l.position.set(0, y, 0); scene.add(l); shaftLights.push(l); }
    const camera = new THREE.PerspectiveCamera(46, el.clientWidth / Math.max(1, el.clientHeight), 0.3, 2500);
    const p0 = CAMERA_PRESETS[cam] ?? CAMERA_PRESETS.overview;
    camera.position.set(...p0.pos);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(...p0.target);
    controls.enableDamping = true; controls.dampingFactor = 0.08; controls.maxDistance = 600; controls.minDistance = 1.5;
    // local key and rim lights on the experimental bodies (the low-key look of the concept renders): narrow cool spots over the dark ground
    const spots: THREE.SpotLight[] = [];
    const spot = (pos: [number, number, number], tgt: [number, number, number], intensity: number, angle: number) => {
      const l = new THREE.SpotLight(0xe6ecff, intensity, 110, angle, 0.9, 1.3); l.position.set(...pos); l.target.position.set(...tgt); scene.add(l, l.target); spots.push(l);
    };
    spot([-80, 26, 30], [-104, 2, 4], 330, 0.5); spot([-128, 16, -14], [-104, 3, 4], 260, 0.45); spot([-72, 24, 62], [-86, 4, 36], 200, 0.45);
    const studio = q === 'performance' ? null : studioEnvironment(renderer);
    const mega = buildMegastructure(q, 7, studio);
    scene.add(mega.root);
    if (url.get('labels') !== '0') for (const a of ANNOTATIONS) { const s = makeLabel(a.text, 0.032, true); s.position.copy(a.at); s.userData = { annotation: a.id }; scene.add(s); }
    const overlays = new THREE.Group(); mega.arena.group.add(overlays);
    const device = buildDeviceLayer(mega.arena.group, 14); mega.root.add(device.group);
    // post-processing (balanced and high): bloom on highlights and lamps, a vignette with fine grain, and at the high tier a depth-of-field pass focused on the orbit target
    // The post chain differs by tier because it is the largest fixed cost of a frame (measured: 9 ms of an empty scene at 1672 x 808 with multisampling, bloom, grade, output and FXAA).
    //   performance  none (the renderer draws to the screen with multisampling)
    //   balanced     render (half float, no multisampling) -> tone mapping and sRGB -> one final pass: a light edge anti-aliasing, a vignette and fine grain
    //   high         render (4x multisampling) -> bloom -> depth of field -> tone mapping -> vignette and grain
    let composer: EffectComposer | null = null, bokeh: BokehPass | null = null, final: ShaderPass | null = null;
    const finalShader = { uniforms: { tDiffuse: { value: null }, time: { value: 0 }, vignette: { value: 0.52 }, grain: { value: 0.035 }, aa: { value: 1 }, px: { value: new THREE.Vector2(1 / 1672, 1 / 808) } },
      vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
      fragmentShader: `uniform sampler2D tDiffuse; uniform float time; uniform float vignette; uniform float grain; uniform float aa; uniform vec2 px; varying vec2 vUv;
        float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233)) + time) * 43758.5453); }
        float luma(vec3 c){ return dot(c, vec3(0.299, 0.587, 0.114)); }
        void main(){
          vec3 c = texture2D(tDiffuse, vUv).rgb;
          if (aa > 0.5) {  // a light edge-only anti-aliasing: where the luminance contrast of the four neighbours is high, blend with their mean
            vec3 n = texture2D(tDiffuse, vUv + vec2(0.0, px.y)).rgb, s = texture2D(tDiffuse, vUv - vec2(0.0, px.y)).rgb, e = texture2D(tDiffuse, vUv + vec2(px.x, 0.0)).rgb, w = texture2D(tDiffuse, vUv - vec2(px.x, 0.0)).rgb;
            float lc = luma(c), ln = luma(n), ls = luma(s), le = luma(e), lw = luma(w), lmin = min(lc, min(min(ln, ls), min(le, lw))), lmax = max(lc, max(max(ln, ls), max(le, lw))), ct = lmax - lmin;
            float k = clamp((ct - max(0.05, lmax * 0.12)) * 4.0, 0.0, 0.7);
            c = mix(c, (n + s + e + w + c) * 0.2, k);
          }
          vec2 d = vUv - 0.5; c *= 1.0 - vignette * dot(d, d) * 2.2;
          c += (h(vUv * 1024.0) - 0.5) * grain * (1.0 - c);
          gl_FragColor = vec4(c, 1.0);
        }` };
    if (q !== 'performance') {
      const w0 = el.clientWidth, h0 = el.clientHeight, high = q === 'high';
      const target = new THREE.WebGLRenderTarget(w0, h0, { type: THREE.HalfFloatType, samples: Number(url.get('msaa') ?? (high ? 4 : 0)) });
      composer = new EffectComposer(renderer, target);
      composer.addPass(new RenderPass(scene, camera));
      // bloom (high; at balanced only with ?bloom=1) works at a quarter of the resolution of the frame: it blurs, so nothing is lost, and it is an expensive pass
      if (high || url.get('bloom') === '1') composer.addPass(new UnrealBloomPass(new THREE.Vector2(w0 * 0.5, h0 * 0.5), high ? 0.3 : 0.24, 0.5, 1.05));
      if (high) { bokeh = new BokehPass(scene, camera, { focus: 60, aperture: 0.00006, maxblur: 0.006 }); composer.addPass(bokeh); }
      composer.addPass(new OutputPass());
      final = new ShaderPass(finalShader);
      final.material.uniforms.aa.value = high ? 0 : 1;
      final.material.uniforms.px.value.set(1 / (w0 * renderer.getPixelRatio()), 1 / (h0 * renderer.getPixelRatio()));
      composer.addPass(final);
    }
    // Every light costs every lit pixel of the frame, so the lights that cannot be seen are switched off: the spot lights on the bodies when the camera is far from the bodies, the
    // shaft's point lights when the camera is away from the shaft and looks away from it. All four combinations are compiled once at the start, so a switch is not a hitch.
    const lightState = { spots: true, shaft: true };
    const bodiesAt = new THREE.Vector3(-98, 2, 14), fwd = new THREE.Vector3(), toShaft = new THREE.Vector3();
    const applyLights = (force = false) => {
      const dB = camera.position.distanceTo(bodiesAt);
      const spotsOn = lightState.spots ? dB < 105 : dB < 95;
      camera.getWorldDirection(fwd);
      const dS = camera.position.length(), toS = toShaft.set(-camera.position.x, -40 - camera.position.y, -camera.position.z).normalize(), facing = fwd.dot(toS);  // the shaft stands at the origin
      const awayFromShaft = lightState.shaft ? (dS > 85 && facing < 0.15) : (dS > 75 && facing < 0.45);
      if (!force && spotsOn === lightState.spots && !awayFromShaft === lightState.shaft) return;
      lightState.spots = spotsOn; lightState.shaft = !awayFromShaft;
      spots.forEach((l) => { l.visible = spotsOn; }); shaftLights.forEach((l) => { l.visible = !awayFromShaft; });
    };
    const features = { post: true, reflect: true, bodies: true, gravel: true, rocks: true, structure: true, bloom: true, everything: true, terrain: true, arena: true, lines: true, points: true, spots: true, env: true };
    const renderFrame = (now: number) => {
      if (composer && features.post) {
        finalShader.uniforms.time.value = (now / 1000) % 10;
        if (bokeh) (bokeh.uniforms as unknown as { focus: { value: number } }).focus.value = camera.position.distanceTo(controls.target);
        composer.render();
      } else renderer.render(scene, camera);
    };
    eng.current = { device, composer, mega, renderer, scene, camera, controls, overlays, simMs: [] };
    for (const [sp, sh] of [[true, true], [true, false], [false, true], [false, false]] as const) { spots.forEach((l) => { l.visible = sp; }); shaftLights.forEach((l) => { l.visible = sh; }); renderer.compile(scene, camera); }
    applyLights(true);
    setReady(true);

    const frames: number[] = [];
    let last = performance.now(), lastHud = last, raf = 0, frameCount = 0;
    const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      const raw = (now - last) / 1000, dt = Math.min(0.25, raw);  // dt drives the simulation clock (bounded); raw is the true frame time
      last = now;
      frames.push(raw * 1000); if (frames.length > 240) frames.shift();
      frameCount++;
      const L = live.current;
      if (L.playing && L.nFrames) {  // the simulation clock: independent of how many frames are drawn
        L.playhead += dt * L.rate;
        const t = Math.min(L.nFrames - 1, Math.floor(L.playhead));
        if (t !== L.tick) { L.tick = t; setTickRef.current(t); }
        if (L.playhead >= L.nFrames - 1) { L.playing = false; setPlayingRef.current(false); }
      }
      if (L.goal) {  // camera moves between presets; they change no experimental state
        camera.position.lerp(L.goal.pos, 0.09); controls.target.lerp(L.goal.target, 0.09);
        if (camera.position.distanceTo(L.goal.pos) < 0.05) L.goal = null;
      } else if (L.follow && eng.current) {
        mega.arena.entities[L.follow].getWorldPosition(tmp);
        tmp2.copy(tmp).sub(controls.target).multiplyScalar(0.12);
        controls.target.add(tmp2); camera.position.add(tmp2);
      }
      controls.update();
      mega.update(camera.position);
      applyLights();
      renderFrame(now);
      if (now - lastHud > 500) {
        lastHud = now;
        const s = [...frames].sort((a, b) => a - b), mean = frames.reduce((a, b) => a + b, 0) / Math.max(1, frames.length);
        const info = renderer.info.render, sim = eng.current?.simMs ?? [];
        setPerf({
          fps: 1000 / Math.max(0.01, mean), frameMs: mean, p95: s[Math.floor(s.length * 0.95)] ?? mean, drawCalls: info.calls, triangles: info.triangles,
          instances: mega.stats.instances, edgeSegments: mega.stats.edgeSegments, simMs: sim.length ? sim.reduce((a, b) => a + b, 0) / sim.length : 0,
          heapMB: (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory ? Math.round((performance as unknown as { memory: { usedJSHeapSize: number } }).memory.usedJSHeapSize / 1048576) : null,
          frames: frameCount, quality: q,
        });
      }
    };
    raf = requestAnimationFrame(loop);
    const ro = new ResizeObserver(() => { renderer.setSize(el.clientWidth, el.clientHeight); composer?.setSize(el.clientWidth, el.clientHeight); final?.material.uniforms.px.value.set(1 / (el.clientWidth * renderer.getPixelRatio()), 1 / (el.clientHeight * renderer.getPixelRatio())); camera.aspect = el.clientWidth / Math.max(1, el.clientHeight); camera.updateProjectionMatrix(); });
    ro.observe(el);
    // picking: a click (not a drag) on an operational configuration or a trial chamber
    let down: [number, number] | null = null;
    const rc = new THREE.Raycaster();
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) { down = null; return; }
      down = null;
      const r = renderer.domElement.getBoundingClientRect();
      rc.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = rc.intersectObjects([...mega.arena.pickables, ...mega.trials.pickables], false)[0];
      const ud = hit?.object.userData as { entity?: EntityName; trial?: number } | undefined;
      if (ud?.entity) { setSel({ kind: 'entity', name: ud.entity }); setTab('inspect'); } else if (ud?.trial !== undefined) { setSel({ kind: 'trial', i: ud.trial }); setTab('inspect'); } else setSel(null);
    };
    renderer.domElement.addEventListener('pointerdown', onDown); renderer.domElement.addEventListener('pointerup', onUp);
    (window as unknown as { __meos?: unknown }).__meos = {
      ready: () => !!eng.current, perf: () => perfSnapshot(frames, renderer, mega, eng.current?.simMs ?? [], q),
      camera: () => ({ pos: camera.position.toArray(), target: controls.target.toArray(), fov: camera.fov, near: camera.near, far: camera.far, exposure: renderer.toneMappingExposure, toneMapping: 'ACESFilmic', pixelRatio: renderer.getPixelRatio(), size: [renderer.domElement.width, renderer.domElement.height], quality: q }), stats: () => mega.stats,
      goto: (t: number) => { live.current.playhead = t; live.current.tick = t; setTickRef.current(t); }, play: (on: boolean) => { live.current.playing = on; setPlayingRef.current(on); },
      resetPerf: () => { frames.length = 0; if (eng.current) eng.current.simMs.length = 0; },
      // measurement hooks (they change nothing in the simulation): switch a graphics feature off to measure its cost, and render n frames back to back with a GPU sync after
      // each one, which gives the uncapped cost of a frame (the on-screen frame rate is limited by the display)
      setFeature: (k: keyof typeof features, on: boolean) => {
        features[k] = on;
        const by = (n: string) => mega.root.children.find((c) => c.name === n || c.children.some((g) => g.name === n));
        if (k === 'reflect' && mega.terrain.puddleMesh) { mega.terrain.puddleMesh.visible = on; mega.terrain.group.userData.noReflect = !on; }
        if (k === 'bodies') mega.bodies.group.visible = on;
        if (k === 'gravel') { const o = by('gravel'); if (o) o.visible = on; }
        if (k === 'rocks') { const o = by('rocks'); if (o) o.visible = on; }
        if (k === 'structure') mega.heavy.forEach((o) => { o.visible = on; });
        if (k === 'lines') mega.root.traverse((o) => { if ((o as THREE.LineSegments).isLineSegments) o.visible = on; });
        if (k === 'points') mega.root.traverse((o) => { if ((o as THREE.Points).isPoints) o.visible = on; });
        if (k === 'env') { scene.environment = on ? sceneEnv : null; scene.traverse((o) => { const m = (o as THREE.Mesh).material as THREE.Material | undefined; if (m) m.needsUpdate = true; }); }
        if (k === 'spots') scene.children.forEach((c) => { if ((c as THREE.SpotLight).isSpotLight) c.visible = on; });
        if (k === 'everything') mega.root.visible = on;
        if (k === 'terrain') mega.terrain.group.visible = on;
        if (k === 'arena') mega.arena.group.visible = on;
        if (k === 'bloom') composer?.passes.forEach((p) => { if (p instanceof UnrealBloomPass) p.enabled = on; });
      },
      benchmark: (n: number, orbit = false) => {
        const gl = renderer.getContext() as WebGL2RenderingContext, px = new Uint8Array(4), ms: number[] = [], js: number[] = [], gpu: number[] = [];
        const tq = gl.getExtension('EXT_disjoint_timer_query_webgl2') as { TIME_ELAPSED_EXT: number } | null;
        renderer.info.autoReset = false;  // the counters then cover every pass of one frame (the composer renders several)
        let calls = 0, triangles = 0;
        for (let i = 0; i < n; i++) {
          renderer.info.reset();
          const q = tq ? gl.createQuery() : null;
          if (q && tq) gl.beginQuery(tq.TIME_ELAPSED_EXT, q);
          const t0 = performance.now();
          if (orbit) { const o = camera.position.clone().sub(controls.target), a = 0.004, c = Math.cos(a), sn = Math.sin(a); camera.position.set(controls.target.x + o.x * c - o.z * sn, camera.position.y, controls.target.z + o.x * sn + o.z * c); camera.lookAt(controls.target); }
          controls.update(); mega.update(camera.position); applyLights(); renderFrame(t0);
          js.push(performance.now() - t0);  // the CPU side of the frame: scene traversal, state changes and the submission of the draw calls
          if (q && tq) gl.endQuery(tq.TIME_ELAPSED_EXT);
          gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);  // forces the GPU to finish the frame
          if (q) { if (gl.getQueryParameter(q, gl.QUERY_RESULT_AVAILABLE)) gpu.push(Number(gl.getQueryParameter(q, gl.QUERY_RESULT)) / 1e6); gl.deleteQuery(q); }
          ms.push(performance.now() - t0);
          calls = renderer.info.render.calls; triangles = renderer.info.render.triangles;
        }
        renderer.info.autoReset = true;
        return { ms, js, gpu, drawCalls: calls, triangles, geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures };
      },
      setCamera: (pos: [number, number, number], target: [number, number, number]) => { camera.position.set(...pos); controls.target.set(...target); controls.update(); },
      renderOnce: () => { controls.update(); renderFrame(performance.now()); },
    };
    return () => {
      cancelAnimationFrame(raf); ro.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onDown); renderer.domElement.removeEventListener('pointerup', onUp);
      disposeGroup(overlays); device.dispose(); composer?.dispose(); mega.dispose(); disposeLabels(); controls.dispose();
      scene.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh && m.geometry) m.geometry.dispose(); });
      renderer.dispose(); renderer.domElement.remove(); eng.current = null; setReady(false);
    };
    // the scene is rebuilt only when the quality changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quality]);

  useEffect(() => { live.current.playing = playing; live.current.rate = rate; live.current.follow = follow; }, [playing, rate, follow]);
  useEffect(() => { live.current.nFrames = rec?.frames.length ?? 0; live.current.tick = tick; if (Math.floor(live.current.playhead) !== tick) live.current.playhead = tick; }, [rec, tick]);

  // ---------------------------------------------------------------------------------------------- apply the record at the tick to the scene
  const trials: Array<Trial | null> = useMemo(() => {
    if (!abl) return [];
    return abl.map((r) => ({ label: r.removed.join(' + ') || 'baseline', status: r.outcomes[0].status, removed: r.removed, note: r.outcomes[0].failed_dependency?.detail }));
  }, [abl]);
  const ad = useMemo(() => (rec ? adAt(rec.frames, tick) : null), [rec, tick]);
  useEffect(() => {
    const E = eng.current;
    if (!E || !rec || !fields) return;
    const t0 = performance.now();
    const t = Math.min(tick, rec.frames.length - 1);
    const f = rec.frames[t];
    E.mega.arena.setFrame(f, fieldAt(fields, 'R', t), fieldAt(fields, 'M1', t), fieldAt(fields, 'M2', t));
    const cap = rec.config.power.capacity;
    E.mega.gauge.set(f.power / cap, rec.config.power.infinite);
    const r0 = rec.frames[0].R || 1;
    E.mega.stockpile.set(Math.min(1.4, f.R / r0));
    const renew = rec.events.filter((e) => e.kind === 'act' && e.actor === 'A2' && (e.renewed as number) > 0 && e.tick <= t && t - e.tick < 8);
    E.mega.carriers.set(renew.slice(-24).map((e) => ({ progress: (t - e.tick) / 8, amount: e.renewed as number })));
    const ds = deviceState(rec, t, obs);
    const aimAt = E.mega.arena.local(ds.array.aim[0], ds.array.aim[1]).clone().add(E.mega.arena.group.position);
    E.mega.array.aim(aimAt, ds.array.sampling, ds.array.activeDishes, f.status === 'ACTIVE' ? 1 : 0.4);
    E.mega.bodies.set(bodyState(rec, t, obs, out?.observed?.observability_status), aimAt);
    E.device.set(ds, { arenaCell: E.mega.arena.local, selectedTrial: sel?.kind === 'trial' ? sel.i : null, trialPos: E.mega.trials.positions, n: rec.config.grid });
    E.mega.arena.group.updateMatrixWorld(true);
    disposeGroup(E.overlays);
    E.overlays.add(...buildOverlays({ rec, t, arena: E.mega.arena, layers, ad, mfs: mfsRes, partitions: spec?.partitions ?? {}, selected: sel?.kind === 'entity' ? sel.name : null }).children.slice());
    E.simMs.push(performance.now() - t0); if (E.simMs.length > 120) E.simMs.shift();
  }, [rec, fields, tick, layers, ad, mfsRes, spec, sel, obs, ready, out]);
  useEffect(() => { eng.current?.mega.trials.set(trials); }, [trials, ready]);
  useEffect(() => {
    const E = eng.current;
    if (!E) return;
    E.mega.arena.group.children.forEach((c) => { if ((c as THREE.InstancedMesh).isInstancedMesh && (c.userData as { layer?: string }).layer) c.visible = layers.has('physical'); });
  }, [layers, ready]);

  // ---------------------------------------------------------------------------------------------- camera
  const goCam = (name: string) => {
    const E = eng.current, p = CAMERA_PRESETS[name];
    setCam(name); setFollow(null);
    if (!E || !p) return;
    live.current.goal = { pos: new THREE.Vector3(...p.pos), target: new THREE.Vector3(...p.target) };
    E.controls.target.set(...(p.target as [number, number, number]));
  };
  const focusSel = () => {
    const E = eng.current;
    if (!E || !sel) return;
    const t = new THREE.Vector3();
    if (sel.kind === 'entity') E.mega.arena.entities[sel.name].getWorldPosition(t); else t.copy(E.mega.trials.positions[sel.i]);
    live.current.goal = { pos: t.clone().add(new THREE.Vector3(5, 4, 7)), target: t };
    setFollow(null);
  };
  const toggleLayer = (id: LayerId) => setLayers((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  // ---------------------------------------------------------------------------------------------- derived panel data
  const mv = rec ? meosView(rec, tick) : null;
  const segs = useMemo(() => (rec ? statusSegments(rec) : []), [rec]);
  const traj = useMemo(() => (rec ? trajectories(rec) : null), [rec]);
  const n = rec?.frames.length ?? 0;

  return (
    <div className="eco" style={chrome ? undefined : { gridTemplateColumns: '1fr' }}>
      <div className="eco-stage" data-settled={settled ? '1' : '0'}>
        <div ref={mount} style={{ position: 'absolute', inset: 0 }} data-testid="eco-canvas" />
        {chrome && tab === 'technical' && rec && <TechnicalView rec={rec} tick={tick} obs={obs} observability={out?.observed?.observability_status ?? 'OBSERVABLE'} which={techWhich} setWhich={setTechWhich} probeId={techProbe} setProbeId={setTechProbe} />}
        <div className="eco-hud">
          {mv && <div className={`eco-badge ${mv.label}`}><span>MEOS {mv.label}</span><span className="dim">tick {tick}/{n - 1}</span></div>}
          {mv?.dependency && <div className="eco-dep">failed dependency{mv.dependency.entity ? ` (${mv.dependency.entity})` : ''}: {mv.dependency.detail}</div>}
          {busy && <div className="eco-dep">{busy}...</div>}
          {err && <div className="eco-dep eco-err">{err}</div>}
        </div>
        {chrome && <div className="eco-timeline">
          <div className="eco-strip" title="MEOS status trajectory">{segs.map((s, i) => <i key={i} className={s.label} style={{ flex: s.to - s.from + 1 }} />)}</div>
          <input type="range" min={0} max={Math.max(0, n - 1)} value={tick} onChange={(e) => { const t = Number(e.target.value); live.current.playhead = t; setTick(t); }} aria-label="simulation tick" />
        </div>}
        {chrome && perf && <div className="eco-perf" data-testid="eco-perf">{`${perf.fps.toFixed(0)} fps  ${perf.frameMs.toFixed(1)} ms (p95 ${perf.p95.toFixed(1)})\ndraw calls ${perf.drawCalls}  tris ${(perf.triangles / 1000).toFixed(0)}k\ninstances ${perf.instances}  edges ${perf.edgeSegments}\nsim update ${perf.simMs.toFixed(2)} ms  heap ${perf.heapMB ?? 'n/a'} MB\nquality ${perf.quality}`}</div>}
      </div>
      {chrome && <aside className="eco-side">
        <div className="eco-tabs" role="tablist">
          {(['experiment', 'inspect', 'reductions', 'studies', 'technical', 'data'] as Tab[]).map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t.toUpperCase()}</button>)}
        </div>
        <div className="eco-pane">
          {tab === 'experiment' && <ExperimentPane {...{ rec, spec, tick, n, playing, setPlaying, rate, setRate, seed, setSeed, horizon, setHorizon, obs, setObs, conn, setConn, fullObs, layers, toggleLayer, cam, goCam, follow, setFollow, sel, focusSel, ivs, execute, intervene, doReplay, replay, quality, setQuality, out, setTick, live }} />}
          {tab === 'inspect' && rec && <InspectPane rec={rec} tick={tick} sel={sel} setSel={setSel} ad={ad} mfs={mfsRes} trials={trials} />}
          {tab === 'reductions' && <ReductionsPane {...{ spec, abl, mfsRes, bnd, hist, sss, addr, runAblation, runMfs, runBoundary, runHistory, runSss, runAddr, busy }} />}
          {tab === 'technical' && <div className="eco-note">The technical inspection sheet is shown over the stage: orthographic drawings of the selected body's real geometry in the pose the run gives at the current tick, a probe detail, measured dimensions, component identifiers, cable routing and the state read from the run. Use the playhead to move through the run.</div>}
          {tab === 'studies' && <ExperimentsPane config={runCfg} busy={busy} wrap={wrap} />}
          {tab === 'data' && rec && traj && <DataPane rec={rec} tick={tick} traj={traj} setTick={(t) => { live.current.playhead = t; setTick(t); }} />}
        </div>
      </aside>}
    </div>
  );
}

function perfSnapshot(frames: number[], renderer: THREE.WebGLRenderer, mega: Megastructure, sim: number[], q: Quality) {
  const s = [...frames].sort((a, b) => a - b), mean = frames.reduce((a, b) => a + b, 0) / Math.max(1, frames.length);
  const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory;
  return { quality: q, frames: frames.length, fps: 1000 / Math.max(0.01, mean), frameMsMean: mean, frameMsP95: s[Math.floor(s.length * 0.95)] ?? mean, frameMsMax: s[s.length - 1] ?? 0,
    drawCalls: renderer.info.render.calls, triangles: renderer.info.render.triangles, geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures,
    instances: mega.stats.instances, edgeSegments: mega.stats.edgeSegments, simUpdateMsMean: sim.length ? sim.reduce((a, b) => a + b, 0) / sim.length : 0, heapMB: mem ? mem.usedJSHeapSize / 1048576 : null,
    entities: 2, trialChambers: mega.trials.slots };
}

// ------------------------------------------------------------------------------------------------------------------ panes
type ExpProps = {
  rec: RunOut['record'] | null; spec: Spec | null; tick: number; n: number; playing: boolean; setPlaying: (b: boolean) => void; rate: number; setRate: (n: number) => void;
  seed: number; setSeed: (n: number) => void; horizon: number; setHorizon: (n: number) => void; obs: Observation; setObs: (o: Observation) => void; conn: { m2: string; m2w: number; phil: string; channel: string }; setConn: (c: { m2: string; m2w: number; phil: string; channel: string }) => void; fullObs: boolean;
  layers: Set<LayerId>; toggleLayer: (l: LayerId) => void; cam: string; goCam: (n: string) => void; follow: EntityName | null; setFollow: (e: EntityName | null) => void;
  sel: Sel; focusSel: () => void; ivs: Intervention[]; execute: (l: Intervention[], t: number | null) => Promise<void>; intervene: (iv: Omit<Intervention, 'tick'>) => void;
  doReplay: () => void; replay: string | null; quality: Quality; setQuality: (q: Quality) => void; out: RunOut | null; setTick: (t: number) => void;
  live: React.MutableRefObject<{ playhead: number }>;
};

function ExperimentPane(p: ExpProps) {
  const [op, setOp] = useState('REMOVE');
  const [target, setTarget] = useState('A2');
  const [path, setPath] = useState('entities.A2.x');
  const [value, setValue] = useState(9);
  const [radius, setRadius] = useState(3);
  const [sssV, setSssV] = useState({ scale: 1, size: 1, speed: 1 });
  const [inj, setInj] = useState({ x: 3, y: 6, amount: 2 });
  const [resPath, setResPath] = useState('power.charge');
  const [resVal, setResVal] = useState(0.4);
  const [hMode, setHMode] = useState('removed');
  const [addr, setAddr] = useState({ mode: 'loss', target: 'A1', x: 9, y: 6, fraction: 0.5 });
  const apply = () => {
    if (op === 'REMOVE' || op === 'ISOLATE' || op === 'RECONNECT') p.intervene({ op, target });
    else if (op === 'RECONFIGURE') p.intervene({ op, path, value });
    else if (op === 'CHANGE_BOUNDARY') p.intervene({ op, arena_radius: radius });
    else if (op === 'DISABLE_HISTORY') p.intervene({ op, mode: hMode });
    else if (op === 'ADDRESS') p.intervene({ op, target: addr.target, mode: addr.mode, ...(addr.mode === 'reassign' ? { x: addr.x, y: addr.y } : {}), ...(addr.mode === 'fragment' || addr.mode === 'partial' ? { fraction: addr.fraction } : {}) });
    else if (op === 'ALTER_SSS') p.intervene({ op, ...sssV });
    else if (op === 'ALTER_RESOURCE') p.intervene(resPath === 'inject' ? { op, inject: inj } : { op, path: resPath, value: resVal } as never);
  };
  const settable = Object.keys(p.spec?.settable ?? {}).filter((k) => k.startsWith('entities.') || k.startsWith('environment.') || k.startsWith('history.'));
  const step = (d: number) => { p.setPlaying(false); const t = Math.max(0, Math.min(p.n - 1, p.tick + d)); p.live.current.playhead = t; p.setTick(t); };
  const mv = p.rec ? meosView(p.rec, p.tick) : null;
  return (
    <>
      <h3>XENO ECOSYSTEM · MEOS-0</h3>
      <div className="eco-note">A real-time simulation, not an animation: every experimental object in the habitat is drawn from a deterministic record (engine {p.rec?.engine ?? '...'}). The surrounding structure is <b>static architecture</b> (no scientific claim).</div>
      <div className="eco-row">
        <button onClick={() => p.setPlaying(!p.playing)} className={p.playing ? 'on' : ''}>{p.playing ? 'PAUSE' : 'RUN'}</button>
        <button onClick={() => step(-1)}>STEP -</button><button onClick={() => step(1)}>STEP +</button>
        <button onClick={() => { p.setPlaying(false); p.live.current.playhead = 0; p.setTick(0); }}>RESET</button>
        <button onClick={p.doReplay} title="re-run from the recorded seed, configuration and interventions and compare the result digests">REPLAY</button>
      </div>
      <div className="eco-row"><span className="dim">speed</span><input type="range" min={1} max={60} value={p.rate} onChange={(e) => p.setRate(Number(e.target.value))} style={{ width: 150 }} /><span className="mono">{p.rate} ticks/s</span></div>
      {p.replay && <div className="eco-note mono">{p.replay}</div>}
      {mv && <dl className="eco-kv"><dt>status</dt><dd>{mv.label} — {mv.reason}</dd><dt>cycles in window</dt><dd>{mv.cycles} ({mv.reentry} with history re-entry), last {mv.age ?? '-'} ticks ago</dd><dt>criteria</dt><dd>{mv.criteria}</dd><dt>result digest</dt><dd>{p.rec?.result_digest.slice(0, 20)}...</dd></dl>}
      <h3>Run</h3>
      <div className="eco-row">
        <label>seed <input type="number" value={p.seed} min={0} style={{ width: 70 }} onChange={(e) => p.setSeed(Number(e.target.value))} /></label>
        <label>horizon <select value={p.horizon} onChange={(e) => p.setHorizon(Number(e.target.value))}>{[240, 360, 480].map((h) => <option key={h}>{h}</option>)}</select></label>
        <label>quality <select value={p.quality} onChange={(e) => p.setQuality(e.target.value as Quality)}>{QUALITY.map((q) => <option key={q}>{q}</option>)}</select></label>
      </div>
      <h3>Observation (Observation Array)</h3>
      <div className="eco-row">
        <label title="ticks between samples">interval <select value={p.obs.sampling_interval} onChange={(e) => p.setObs({ ...p.obs, sampling_interval: Number(e.target.value) })}>{[1, 2, 3, 4, 6, 8].map((h) => <option key={h}>{h}</option>)}</select></label>
        <label title="every n-th cell of the arena is resolved">spatial stride <select value={p.obs.spatial_stride} onChange={(e) => p.setObs({ ...p.obs, spatial_stride: Number(e.target.value) })}>{[1, 2, 3, 4].map((h) => <option key={h}>{h}</option>)}</select></label>
        <label title="events closer in time than this are one observed event">aggregation <select value={p.obs.aggregation} onChange={(e) => p.setObs({ ...p.obs, aggregation: Number(e.target.value) })}>{[1, 2, 4, 8].map((h) => <option key={h}>{h}</option>)}</select></label>
        <label title="ticks over which the observer counts cycles">window <select value={p.obs.window} onChange={(e) => p.setObs({ ...p.obs, window: Number(e.target.value) })}>{[12, 24, 48, 96].map((h) => <option key={h}>{h}</option>)}</select></label>
        <label title="the region of the arena the observer looks at">region <select value={p.obs.region ? p.obs.region.join(',') : 'all'} onChange={(e) => p.setObs({ ...p.obs, region: e.target.value === 'all' ? null : e.target.value.split(',').map(Number) })}>
          <option value="all">whole arena</option><option value="0,0,6,13">left half</option><option value="7,0,13,13">right half</option><option value="3,3,10,10">centre</option><option value="0,0,3,3">corner</option></select></label>
        <button disabled={p.fullObs} onClick={() => p.setObs(FULL_OBSERVATION)}>full resolution</button>
      </div>
      <div className="eco-note">covers {(observationCoverage(p.obs, p.rec?.config.grid ?? 14) * 100).toFixed(0)}% of the arena cells at the sampled ticks. Operational state is the run's own status; observed state is computed from what this observation resolves; observability status says why they differ.</div>
      {p.out?.observed ? <dl className="eco-kv"><dt>operational state</dt><dd><span className={`eco-chip ${p.out.observed.operational_state}`}>{p.out.observed.operational_state}</span> ({p.out.observed.true_cycles} cycles counted by the engine)</dd>
        <dt>observed state</dt><dd><span className={`eco-chip ${p.out.observed.observed_state}`}>{p.out.observed.observed_state}</span> ({p.out.observed.observed_cycles} cycles resolved)</dd>
        <dt>observability</dt><dd>{p.out.observed.observability_status}{p.out.observed.limiting_parameters.length ? ` — limited by ${p.out.observed.limiting_parameters.join(', ')}` : ''}</dd></dl>
        : <div className="eco-note">full-resolution observation: the observed state is the operational state.</div>}
      <h3>Connections</h3>
      <div className="eco-row">
        <label title="A1 also senses M2, the alteration A2's reconfiguration leaves">M2 → A1 <select value={p.conn.m2} onChange={(e) => p.setConn({ ...p.conn, m2: e.target.value })}>{['none', 'direct', 'delayed', 'noisy'].map((m) => <option key={m}>{m}</option>)}</select></label>
        <label>weight <input type="number" step="0.25" min={0.25} max={4} value={p.conn.m2w} style={{ width: 54 }} onChange={(e) => p.setConn({ ...p.conn, m2w: Number(e.target.value) })} /></label>
        <label title="first-stage Philosophical operations: expression, scorekeeping, norm-sensitive revision">philosophical <select value={p.conn.phil} onChange={(e) => p.setConn({ ...p.conn, phil: e.target.value })}>{['none', 'expression', 'scorekeeping', 'revision'].map((m) => <option key={m}>{m}</option>)}</select></label>
        <label>channel <select value={p.conn.channel} onChange={(e) => p.setConn({ ...p.conn, channel: e.target.value })}>{['clean', 'noisy', 'slow'].map((m) => <option key={m}>{m}</option>)}</select></label>
      </div>
      <div className="eco-note">A connection that is off is absent from the run, not switched off inside it: the default run is the baseline. A philosophical operation costs power and is not designed to help; the module appears in the third expansion bay only when one is configured.</div>
      <h3>Camera</h3>
      <div className="eco-row">{Object.entries(CAMERA_PRESETS).map(([k, v]) => <button key={k} className={p.cam === k && !p.follow ? 'on' : ''} onClick={() => p.goCam(k)}>{v.label}</button>)}</div>
      <div className="eco-row"><span className="dim">follow</span>{ENTITY_NAMES.map((e) => <button key={e} className={p.follow === e ? 'on' : ''} onClick={() => p.setFollow(p.follow === e ? null : e)}>{e}</button>)}<button disabled={!p.sel} onClick={p.focusSel}>focus selection</button></div>
      <div className="eco-note">orbit: drag · pan: right-drag · zoom: wheel · click A1 / A2 / a chamber to inspect. The camera never changes the experiment.</div>
      <h3>Layers</h3>
      <div className="eco-layers">{LAYERS.map((l) => <button key={l.id} title={l.what} className={p.layers.has(l.id) ? 'on' : ''} onClick={() => p.toggleLayer(l.id)}>{l.label}</button>)}</div>
      <div className="eco-note">{LAYERS.filter((l) => p.layers.has(l.id)).map((l) => <div key={l.id}><b>{l.label}</b> {l.what}</div>)}</div>
      <h3>Experimental intervention (at tick {p.tick})</h3>
      <div className="eco-row">
        <select value={op} onChange={(e) => setOp(e.target.value)}>{(p.spec?.operations ?? []).map((o) => <option key={o}>{o}</option>)}</select>
        {(op === 'REMOVE' || op === 'ISOLATE' || op === 'RECONNECT') && <select value={target} onChange={(e) => setTarget(e.target.value)}>{(p.spec?.components ?? []).map((c) => <option key={c}>{c}</option>)}</select>}
        {op === 'RECONFIGURE' && <><select value={path} onChange={(e) => setPath(e.target.value)}>{settable.map((k) => <option key={k}>{k}</option>)}</select><input type="number" step="any" value={value} style={{ width: 70 }} onChange={(e) => setValue(Number(e.target.value))} /></>}
        {op === 'CHANGE_BOUNDARY' && <label>arena radius <input type="number" min={1} max={14} value={radius} style={{ width: 54 }} onChange={(e) => setRadius(Number(e.target.value))} /></label>}
        {op === 'DISABLE_HISTORY' && <select value={hMode} onChange={(e) => setHMode(e.target.value)}><option>removed</option><option>prevented</option></select>}
        {op === 'ADDRESS' && <><select value={addr.mode} onChange={(e) => setAddr({ ...addr, mode: e.target.value })}>{['loss', 'reassign', 'fragment', 'collision', 'partial', 'restore'].map((m) => <option key={m}>{m}</option>)}</select>
          <select value={addr.target} onChange={(e) => setAddr({ ...addr, target: e.target.value })}>{['A1', 'A2', 'both'].map((m) => <option key={m}>{m}</option>)}</select>
          {addr.mode === 'reassign' && (['x', 'y'] as const).map((k) => <label key={k}>{k} <input type="number" min={0} max={13} value={addr[k]} style={{ width: 46 }} onChange={(e) => setAddr({ ...addr, [k]: Number(e.target.value) })} /></label>)}
          {(addr.mode === 'fragment' || addr.mode === 'partial') && <label>fraction <input type="number" step="0.25" min={0} max={1} value={addr.fraction} style={{ width: 54 }} onChange={(e) => setAddr({ ...addr, fraction: Number(e.target.value) })} /></label>}</>}
        {op === 'ALTER_SSS' && (['scale', 'size', 'speed'] as const).map((k) => <label key={k}>{k} <input type="number" step="0.25" min={0.25} max={4} value={sssV[k]} style={{ width: 54 }} onChange={(e) => setSssV({ ...sssV, [k]: Number(e.target.value) })} /></label>)}
        {op === 'ALTER_RESOURCE' && <><select value={resPath} onChange={(e) => setResPath(e.target.value)}><option value="power.charge">power.charge</option><option value="power.reserve">power.reserve</option><option value="environment.regrow">environment.regrow</option><option value="environment.relax">environment.relax</option><option value="inject">inject a resource pulse</option></select>
          {resPath === 'inject' ? (['x', 'y', 'amount'] as const).map((k) => <label key={k}>{k} <input type="number" step="any" value={inj[k]} style={{ width: 54 }} onChange={(e) => setInj({ ...inj, [k]: Number(e.target.value) })} /></label>) : <input type="number" step="any" value={resVal} style={{ width: 70 }} onChange={(e) => setResVal(Number(e.target.value))} />}</>}
        <button onClick={apply} disabled={!p.spec}>APPLY</button>
      </div>
      <div className="eco-note">The run is recomputed from the recorded seed with the intervention added; the past before this tick is unchanged. Ticks before it replay identically.</div>
      <h3>Intervention log</h3>
      {p.ivs.length === 0 ? <div className="eco-note eco-sparse">no interventions: the unperturbed MEOS-0 run</div> : (
        <ul className="eco-log">{p.ivs.map((iv, i) => <li key={i}><span>t={iv.tick} {iv.op} {iv.target ?? iv.path ?? ''} {iv.value ?? iv.arena_radius ?? iv.mode ?? (iv.inject ? `pulse ${iv.inject.amount}@(${iv.inject.x},${iv.inject.y})` : '')}{iv.scale || iv.size || iv.speed ? ` sss ${iv.scale ?? ''}/${iv.size ?? ''}/${iv.speed ?? ''}` : ''}</span></li>)}</ul>
      )}
      <div className="eco-row"><button disabled={!p.ivs.length} onClick={() => void p.execute(p.ivs.slice(0, -1), p.tick)}>undo last</button><button disabled={!p.ivs.length} onClick={() => void p.execute([], 0)}>clear all</button></div>
      <h3>Research device (live state of the structure)</h3>
      {p.rec && (() => {
        const d = deviceState(p.rec, p.tick, p.obs);
        return <dl className="eco-kv">
          <dt>Observation Array</dt><dd>aimed at cell ({d.array.aim[0].toFixed(1)}, {d.array.aim[1].toFixed(1)}); {d.array.activeDishes}/12 dishes lit (coverage {(d.array.coverage * 100).toFixed(0)}%); {d.array.sampling ? 'sampling at this tick' : 'not a sampled tick'}</dd>
          <dt>Boundary Layer</dt><dd>{d.boundary.closed ? 'closed: every coupling channel intact' : `open: ${d.boundary.open.join(', ')}`}; arena radius {d.boundary.arenaRadius ?? 'whole grid'}</dd>
          <dt>Recovery</dt><dd>{d.recovery.phase === 'none' ? 'no collapse so far' : d.recovery.phase === 'collapsed' ? `collapsed since tick ${d.recovery.since}` : `recovered at tick ${d.recovery.since} (${d.recovery.recoveries} recovery event${d.recovery.recoveries === 1 ? '' : 's'})`}</dd>
          <dt>Resource pulse</dt><dd>{d.pulse.active ? `amount ${d.pulse.amount} at (${d.pulse.x}, ${d.pulse.y}), ${d.pulse.age} ticks ago` : 'none in the last 14 ticks'}</dd>
          <dt>Philosophical module</dt><dd>{d.phil.enabled ? `mode ${d.phil.mode}; ${d.phil.expressions} expressions, power spent ${d.phil.power.toFixed(2)}; A1 reliability ${d.phil.reliability.toFixed(2)}, A2 trust ${d.phil.trust.toFixed(2)}; measured renewal efficiency ${d.phil.measuredEfficiency.toFixed(2)}; renewal boost ×${d.phil.boost.toFixed(2)}` : 'not configured: the bay is empty'}</dd>
        </dl>;
      })()}
      <details><summary className="dim">which space serves which experimental function</summary><table className="eco-table"><thead><tr><th>space</th><th>function</th><th>driven by</th></tr></thead><tbody>{SPACES.map((x) => <tr key={x.space}><td>{x.space}</td><td>{x.function}</td><td>{x.driven_by}</td></tr>)}</tbody></table></details>
      <h3>MEOS and MFS</h3>
      <div className="eco-note"><b>MFS</b> is the minimal relational operational configuration relative to a specified operation, physical conditions, scale and admissible reductions. <b>MEOS</b> is an ecosystem-level application: several operational sequences recursively modify one another's subsequent conditions. Minimality here is operational and relational (what must be retained for the cycle to persist) and never a count of visible objects. A1 and A2 are operational configurations: a sensing window, a threshold, a firing persistence and an action rule — not organisms, subjects or minds; their operational boundary is a specification you can change.</div>
    </>
  );
}

function InspectPane({ rec, tick, sel, setSel, ad, mfs, trials }: { rec: RunOut['record']; tick: number; sel: Sel; setSel: (s: Sel) => void; ad: ReturnType<typeof adAt>; mfs: MfsOut | null; trials: Array<Trial | null> }) {
  return (
    <>
      <h3>Inspect</h3>
      <div className="eco-row">{ENTITY_NAMES.map((e) => <button key={e} className={sel?.kind === 'entity' && sel.name === e ? 'on' : ''} onClick={() => setSel({ kind: 'entity', name: e })}>{e}</button>)}</div>
      {!sel && <div className="eco-note">Select A1 or A2 (here or by clicking it in the habitat), or a subsurface chamber. Nothing shown is invented: each value is read from the record at tick {tick}.</div>}
      {sel?.kind === 'entity' && <EntityCard rec={rec} tick={tick} name={sel.name} ad={ad} mfs={mfs} />}
      {sel?.kind === 'trial' && (() => {
        const tr = trials[sel.i];
        return <dl className="eco-kv"><dt>Object ID</dt><dd>subsurface trial chamber {sel.i + 1}</dd><dt>trial</dt><dd>{tr ? tr.label : 'empty (no trial run: use REDUCTIONS → run ablation)'}</dd>{tr && <><dt>MEOS status</dt><dd>{tr.status}</dd><dt>removed</dt><dd>{tr.removed.join(', ') || 'nothing (baseline)'}</dd><dt>failed dependency</dt><dd>{tr.note ?? 'none: the operation persists'}</dd></>}</dl>;
      })()}
    </>
  );
}

function EntityCard({ rec, tick, name, ad, mfs }: { rec: RunOut['record']; tick: number; name: EntityName; ad: ReturnType<typeof adAt>; mfs: MfsOut | null }) {
  const f = frameAt(rec, tick)[name], fv = firingView(rec, name, tick), av = addressView(rec, name, tick, ad), partner = name === 'A1' ? 'A2' : 'A1';
  const part = frameAt(rec, tick)[partner];
  const trans = rec.events.filter((e) => e.tick <= tick && (e.actor === name || e.kind === 'status' || e.kind === 'intervention')).slice(-7).reverse();
  const cfg = rec.final_config.entities[name];
  const role = name === 'A1' ? 'senses the resource field R, differentiates it from an adapted baseline, fires, consumes R and deposits alteration M1' : 'senses the alteration M1, differentiates it, fires, moves to it and reconfigures R from the finite power reserve';
  return (
    <>
      <dl className="eco-kv">
        <dt>Object ID</dt><dd>{name} (operational configuration)</dd>
        <dt>configuration</dt><dd>{role}. threshold {String(cfg.threshold)}, sensing radius {String(cfg.sensor_radius)}, window {String(cfg.window)}, persistence {String(cfg.persist)}, refractory {String(cfg.refractory)}</dd>
        <dt>Address Domain</dt><dd>{av ? <>position ({av.spatial.x}, {av.spatial.y}); sensing boundary radius {av.boundary.sensor_radius}, footprint {av.boundary.footprint}, arena {av.boundary.arena_radius ?? 'whole grid'}; temporal window {av.window.window}/{av.window.persist}/{av.window.refractory} (window/persist/refractory); speed {av.speed}; history trace {av.history.trace.toFixed(3)} (re-entry {av.history.enabled ? 'on' : 'off'}, {av.history.fires} firings, last {av.history.lastFire ?? '-'}); connectivity {Object.entries(av.connectivity).map(([k, v]) => `${k}:${v ? 'on' : 'OFF'}`).join(' ')}; local M1 {av.environment.M1_local}, mark persistence {av.environment.mark_persistence}; local R {av.resource.R_local}, energy {av.resource.energy}, power reserve {av.resource.power_reserve}</> : 'not recorded'}</dd>
        <dt>SSS</dt><dd>{av ? `scale ${av.sss.scale} · size ${av.sss.size} · speed ${av.sss.speed}` : '-'}</dd>
        <dt>MFS membership</dt><dd>{mfsMembership(mfs, name)}</dd>
        <dt>MEOS membership</dt><dd>{meosMembership(rec, name, tick) ? 'yes: it fired in a counted cycle within the last 48 ticks' : 'no cycle of the last 48 ticks includes its firing'}</dd>
        <dt>firing state</dt><dd>{fv.state}; stimulus {f.s.toFixed(3)} − baseline {f.baseline.toFixed(3)} = {f.d.toFixed(3)} against threshold {f.theta.toFixed(3)} (history lowered it by {f.reentry.toFixed(3)}); active {f.active}, refractory {f.cool}; {fv.lastFire !== null ? `last fired at tick ${fv.lastFire}` : 'has not fired'}</dd>
        <dt>unmet preconditions now</dt><dd>{fv.failed.length ? fv.failed.join('; ') : 'none: it can fire when the stimulus allows'}</dd>
        <dt>resource state</dt><dd>R here {f.r_local.toFixed(3)}; {name === 'A1' ? `energy ${f.energy.toFixed(2)}` : `power reserve ${frameAt(rec, tick).power.toFixed(2)}`}</dd>
        <dt>interaction partners</dt><dd>{partner} at ({part.x}, {part.y}){part.present ? '' : ' — absent'}; via {name === 'A1' ? 'alteration M1 → A2' : 'reconfigured R → A1'}</dd>
        <dt>operational boundary</dt><dd>{av ? `sensing window ${2 * av.boundary.sensor_radius + 1}×${2 * av.boundary.sensor_radius + 1} cells${av.boundary.arena_radius != null ? `, confined to arena radius ${av.boundary.arena_radius}` : ''}` : '-'}</dd>
      </dl>
      {fv.checks && <><h3>why it fired (preconditions of the firing at tick {fv.lastFire})</h3><table className="eco-table"><tbody>{fv.checks.map((c, i) => <tr key={i}><td>{c.ok ? '■' : '□'}</td><td>{c.precondition}</td><td>{c.value != null ? String(c.value) : ''}{c.need != null ? ` / ${String(c.need)}` : ''}</td></tr>)}</tbody></table></>}
      {fv.consequences.length > 0 && <><h3>downstream consequences of that firing</h3><ul className="eco-log">{fv.consequences.map((e) => <li key={e.id}><span>t={e.tick} {e.kind} {e.actor ?? ''} {String(e.action ?? e.reason ?? '')}</span></li>)}</ul></>}
      <h3>recent state transitions</h3>
      <ul className="eco-log">{trans.map((e) => <li key={e.id}><span>t={e.tick} {e.kind} {e.actor ?? ''} {String(e.action ?? e.label ?? e.op ?? '')}</span></li>)}</ul>
    </>
  );
}

function ChipS({ s }: { s: Label | string }) { return <span className={`eco-chip ${s}`}>{s}</span>; }

function ReductionsPane(p: { spec: Spec | null; abl: AblationRow[] | null; mfsRes: MfsOut | null; bnd: BoundaryOut | null; hist: HistoryOut | null; sss: Array<{ axis: string; value: number; status: Label; cycles: number; first_collapse_tick: number | null }> | null; addr: Array<{ path: string; value: number; status: Label; cycles: number; first_collapse_tick: number | null }> | null; runAblation: () => void; runMfs: (x: boolean) => void; runBoundary: () => void; runHistory: () => void; runSss: () => void; runAddr: () => void; busy: string | null }) {
  const dis = !p.spec || !!p.busy;
  return (
    <>
      <h3>MEOS reduction experiments</h3>
      <div className="eco-note">Every button runs the real engine and recomputes whether the target operation survives. The unperturbed run is the reference; outcomes are properties of this model.</div>
      <div className="eco-row"><button disabled={dis} onClick={p.runAblation}>ablate each component</button><button disabled={dis} onClick={() => p.runMfs(false)}>find minimal configuration</button><button disabled={dis} onClick={() => p.runMfs(true)}>exhaustive (512 runs)</button></div>
      <div className="eco-row"><button disabled={dis} onClick={p.runBoundary}>XenoBody boundaries</button><button disabled={dis} onClick={p.runHistory}>H+ / H−</button><button disabled={dis} onClick={p.runSss}>SSS sweep</button><button disabled={dis} onClick={p.runAddr}>Address Domain sweep</button></div>
      {p.abl && <><h3>ablation (also shown in the subsurface chambers)</h3><table className="eco-table"><thead><tr><th>removed</th><th>status</th><th>cycles</th><th>collapse</th><th>failed dependency</th></tr></thead><tbody>{p.abl.map((r, i) => <tr key={i}><td>{r.removed.join(' + ') || 'baseline'}</td><td><ChipS s={r.outcomes[0].status} /></td><td>{r.outcomes[0].cycles}</td><td>{r.outcomes[0].first_collapse_tick ?? '-'}</td><td>{r.outcomes[0].failed_dependency?.detail ?? ''}</td></tr>)}</tbody></table></>}
      {p.mfsRes && <><h3>minimal operational configuration (MFS relation)</h3><div className="eco-note">operation: {p.mfsRes.operation}</div>
        {p.mfsRes.note ? <div className="eco-note">{p.mfsRes.note}</div> : <dl className="eco-kv"><dt>retained</dt><dd>{p.mfsRes.retained.join(', ')}</dd><dt>removable</dt><dd>{p.mfsRes.removed.join(', ') || 'none'}</dd><dt>1-minimal</dt><dd>{String(p.mfsRes.retained_is_one_minimal)} (removing any retained component ends the operation)</dd>
          {p.mfsRes.single_removal_persists && <><dt>single removal</dt><dd>{Object.entries(p.mfsRes.single_removal_persists).map(([k, v]) => `${k}:${v ? 'survives' : 'ends it'}`).join(' · ')}</dd></>}
          {p.mfsRes.exhaustive && <><dt>exhaustive</dt><dd>{p.mfsRes.exhaustive.minimal_retained_sets.length} minimal retained set(s) of {p.mfsRes.exhaustive.subsets_evaluated}: {p.mfsRes.exhaustive.minimal_retained_sets.map((s) => `{${s.join(', ')}}`).join(' | ')}</dd></>}</dl>}</>}
      {p.bnd && <><h3>XenoBody operational boundaries (same arrangement)</h3><table className="eco-table"><thead><tr><th>body</th><th>closure</th><th>persists if only it is retained</th><th>failed dependency</th></tr></thead><tbody>{p.bnd.partitions.map((b) => <tr key={b.id}><td>{b.id} {b.label}</td><td>{(b.closure * 100).toFixed(0)}%</td><td><ChipS s={b.status_when_only_the_body_is_retained} /> {b.cycles} cycles</td><td>{b.failed_dependency?.detail ?? ''}</td></tr>)}</tbody></table></>}
      {p.hist && <><h3>history re-entry: H+ against H−</h3><table className="eco-table"><thead><tr><th>condition</th><th>status</th><th>cycles</th><th>diverges at</th><th>mean threshold reduction</th></tr></thead><tbody>{Object.entries(p.hist).map(([k, v]) => <tr key={k}><td>{k}</td><td><ChipS s={v.status} /></td><td>{v.cycles}</td><td>{v['first_divergence_from_H+'] ?? '-'}</td><td>{v.mean_threshold_reduction}</td></tr>)}</tbody></table></>}
      {p.sss && <><h3>SSS perturbation</h3><table className="eco-table"><tbody>{p.sss.map((r, i) => <tr key={i}><td>{r.axis} = {r.value}</td><td><ChipS s={r.status} /></td><td>{r.cycles} cycles</td><td>{r.first_collapse_tick != null ? `collapse @${r.first_collapse_tick}` : ''}</td></tr>)}</tbody></table></>}
      {p.addr && <><h3>Address Domain perturbation</h3><table className="eco-table"><tbody>{p.addr.map((r, i) => <tr key={i}><td>{r.path} = {r.value}</td><td><ChipS s={r.status} /></td><td>{r.cycles} cycles</td><td>{r.first_collapse_tick != null ? `collapse @${r.first_collapse_tick}` : ''}</td></tr>)}</tbody></table></>}
    </>
  );
}

function DataPane({ rec, tick, traj, setTick }: { rec: RunOut['record']; tick: number; traj: ReturnType<typeof trajectories>; setTick: (t: number) => void }) {
  const markers = rec.intervention_log.map((i) => ({ t: i.tick, color: '#ffffff', label: i.op }));
  const g = interactionGraph(rec, tick);
  const fires = (a: string) => rec.events.filter((e) => e.kind === 'fire' && e.actor === a).map((e) => e.tick);
  const W = 340, n = rec.frames.length - 1;
  return (
    <>
      <h3>Data &amp; model generation</h3>
      <div className="eco-note">Outputs of the run itself: trajectories, firing events, the accumulated interaction graph, resource distribution and the MEOS status trajectory. Click a chart to move the playhead.</div>
      <Chart title="MEOS status (0 collapsed, 1 degraded, 2 active)" series={[{ label: 'status', t: rec.frames.map((f) => f.t), v: rec.frames.map((f) => STATUS_VALUE[f.status]) }]} markers={markers} height={90} onPick={setTick} />
      <Chart title="cycles in the last 48 ticks" series={traj.cycles} markers={markers} height={80} onPick={setTick} />
      <Chart title="resource: total R and power reserve" series={traj.resource} markers={markers} height={100} onPick={setTick} />
      <Chart title="history traces" series={traj.history} markers={markers} height={90} onPick={setTick} />
      <Chart title="A1 energy" series={traj.energy} markers={markers} height={80} onPick={setTick} />
      {rec.traces && <Traces rec={rec} markers={markers} setTick={setTick} />}
      <h3>firing events</h3>
      <svg width={W} height={52} style={{ background: '#050507', border: '1px solid #1c1c21' }} role="img" aria-label="firing raster">
        {(['A1', 'A2'] as const).map((a, row) => fires(a).map((t) => <line key={a + t} x1={4 + (t / n) * (W - 8)} x2={4 + (t / n) * (W - 8)} y1={6 + row * 22} y2={22 + row * 22} stroke="#fff" strokeWidth={1} opacity={0.85} />))}
        <line x1={4 + (tick / n) * (W - 8)} x2={4 + (tick / n) * (W - 8)} y1={0} y2={52} stroke="#8a8a90" strokeDasharray="3 3" />
        <text x={6} y={10} fontSize={8} fill="#7a7a82">A1</text><text x={6} y={32} fontSize={8} fill="#7a7a82">A2</text>
      </svg>
      <h3>interaction graph (accumulated to tick {tick})</h3>
      <svg width={W} height={150} style={{ background: '#050507', border: '1px solid #1c1c21' }} role="img" aria-label="interaction graph">
        {[['A1', 50, 40], ['M1', 170, 20], ['A2', 290, 40], ['R', 170, 110], ['H', 50, 120]].map(([k, x, y]) => <g key={String(k)}><circle cx={Number(x)} cy={Number(y)} r={16} fill="#000" stroke="#fff" /><text x={Number(x)} y={Number(y) + 4} textAnchor="middle" fontSize={11} fill="#fff">{String(k)}</text></g>)}
        {g.map((e, i) => { const pos: Record<string, [number, number]> = { A1: [50, 40], M1: [170, 20], A2: [290, 40], R: [170, 110], H: [50, 120] }; const [x1, y1] = pos[e.from], [x2, y2] = pos[e.to]; return <g key={i}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#fff" strokeWidth={Math.min(4, 0.4 + e.count / 12)} opacity={e.count ? 0.8 : 0.15} strokeDasharray={e.label === 're-entry' ? '4 3' : undefined} /><text x={(x1 + x2) / 2 + 3} y={(y1 + y2) / 2 - 3} fontSize={8} fill="#a8a8ad">{e.label} {e.count}</text></g>; })}
      </svg>
      <h3>resource distribution at tick {tick}</h3>
      <ResourceBars rec={rec} tick={tick} />
    </>
  );
}

/** Intermediate quantities of the run: the status is counted from cycles and never reads these, so they show how the operation is sustained, not whether it is. */
function Traces({ rec, markers, setTick }: { rec: RunOut['record']; markers: Array<{ t: number; color: string; label: string }>; setTick: (t: number) => void }) {
  const tr = rec.traces!, t = tr.t ?? rec.frames.map((f) => f.t);
  const S = (label: string, key: string) => ({ label, t, v: tr[key] ?? [] });
  return (
    <>
      <h3>resource flow</h3>
      <Chart title="resource consumed / renewed per tick" series={[S('consumed', 'resource_consumed'), S('renewed', 'resource_renewed')]} markers={markers} height={90} onPick={setTick} />
      <Chart title="energy / power balance (reserve, draw, intake)" series={[S('reserve', 'power_reserve'), S('draw', 'power_draw'), S('in', 'power_in')]} markers={markers} height={90} onPick={setTick} />
      <h3>activity, interaction and history</h3>
      <Chart title="A1 / A2 activity (firings in the window)" series={[S('A1', 'a1_activity'), S('A2', 'a2_activity')]} markers={markers} height={80} onPick={setTick} />
      <Chart title="interaction strength (A2's M1 signal) and reconfiguration signal" series={[S('interaction', 'interaction_strength'), S('reconfiguration', 'reconfiguration_signal')]} markers={markers} height={80} onPick={setTick} />
      <Chart title="history contribution to the thresholds" series={[S('A1', 'history_contribution_a1'), S('A2', 'history_contribution_a2')]} markers={markers} height={80} onPick={setTick} />
      <Chart title="target margin (≥ 0 ⇔ ACTIVE)" series={[S('margin', 'target_margin')]} markers={markers} height={80} onPick={setTick} />
      {tr.phil_boost && <Chart title="Philosophical operations: renewal boost and A1 reliability" series={[S('boost', 'phil_boost'), S('reliability', 'phil_reliability_scarcity'), S('measured efficiency', 'phil_measured_efficiency')]} markers={markers} height={90} onPick={setTick} />}
    </>
  );
}

function ResourceBars({ rec, tick }: { rec: RunOut['record']; tick: number }) {
  const fields = useMemo(() => decodeFields(rec.fields, rec.frames.length), [rec]);
  const R = fieldAt(fields, 'R', Math.min(tick, rec.frames.length - 1)), n = fields.n;
  const cols = Array.from({ length: n }, (_, x) => { let s = 0; for (let y = 0; y < n; y++) s += R[y * n + x]; return (s / n) * fields.rTop; });
  const max = Math.max(0.01, ...cols);
  return <svg width={340} height={64} style={{ background: '#050507', border: '1px solid #1c1c21' }} role="img" aria-label="resource distribution along x">{cols.map((v, i) => <rect key={i} x={6 + i * 23} y={58 - (v / max) * 50} width={18} height={(v / max) * 50} fill="#fff" opacity={0.8} />)}<text x={6} y={10} fontSize={8} fill="#7a7a82">mean R by column x (source at x=0), max {max.toFixed(2)}</text></svg>;
}

export { WORLD };
