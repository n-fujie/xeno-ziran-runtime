// The interactive 3D body. Three kinds of values are drawn apart and never blended:
//   reference    the model's own state (solid light body)            — simulator-internal
//   observation  what the deployed devices delivered (cyan)          — delayed, noisy, with dropouts; unobserved segments are not drawn
//   estimate     what the controller believes / what can be computed from observations only (amber markers)
// The scene reads runtime data each frame through `read()`; nothing here is a stored picture of a result.
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { BodyInfo } from '../../api/xbtro';
import { chain } from './logic';

export type Layer = 'reference' | 'observation' | 'estimate';

export interface SceneData {
  t: number;
  theta: number[];                       // reference absolute segment angles
  drive: number[];                       // reference net muscle drive per joint (-1..1)
  cop: number; com: number; xref: number; pushForce: number; alive: boolean;
  controllerCom: number | null;          // the controller's own estimate (a model estimate)
  obsAngles: (number | null)[] | null;   // observed absolute segment angles; null entries = unobserved
  obsAge: number;                        // seconds since the shown observation arrived
  obsEmg: (number | null)[] | null;      // observed muscle activity per joint (device output)
  obsCop: number | null;
  obsCom: number | null;                 // COM computed from observations only
  linesActive: number;                   // how many operation lines are active now
}

interface Props {
  info: BodyInfo;
  layer: Layer;
  overlay: boolean;
  selected: string | null;
  onSelect: (part: string | null) => void;
  read: () => SceneData | null;
}

const KIND_COLOR: Record<string, number> = { posture: 0x5fd0e8, imu: 0x9fe08a, emg: 0xe8a05f, contact: 0xd08ae8, respiration: 0x8ab4e8, eeg: 0xe88a8a };

function driveColor(d: number): THREE.Color {
  const c = new THREE.Color();
  const a = Math.min(1, Math.abs(d) * 1.6);
  c.setRGB(0.22 + 0.7 * (d > 0 ? a : 0), 0.22 + 0.25 * a, 0.22 + 0.7 * (d < 0 ? a : 0));
  return c;
}

function capsuleBetween(m: THREE.Mesh, a: THREE.Vector3, b: THREE.Vector3, len: number) {
  m.position.copy(a).add(b).multiplyScalar(0.5);
  const dir = b.clone().sub(a).normalize();
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
  m.scale.set(1, len > 1e-6 ? a.distanceTo(b) / len : 1, 1);
}

export default function BodyScene({ info, layer, overlay, selected, onSelect, read }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const live = useRef({ layer, overlay, selected, read, onSelect });
  useEffect(() => { live.current = { layer, overlay, selected, read, onSelect }; });

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const n = info.links.length;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setClearColor(0x050507);
    el.appendChild(renderer.domElement);
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.touchAction = 'none';
    renderer.domElement.setAttribute('role', 'img');
    renderer.domElement.setAttribute('aria-label', 'Interactive 3D view of the simulated planar body: reference, observed and estimated values are drawn apart');

    const scene = new THREE.Scene();
    const height = info.links.reduce((s, l) => s + l.length, 0);
    const camera = new THREE.PerspectiveCamera(34, 1, 0.05, 50);
    camera.position.set(height * 1.1, height * 0.62, height * 1.75);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0.0, height * 0.46, 0);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI * 0.52;
    controls.minDistance = height * 0.8;
    controls.maxDistance = height * 5;
    controls.update();

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const sun = new THREE.DirectionalLight(0xffffff, 1.1);
    sun.position.set(2, 4, 3);
    scene.add(sun);

    // ground, grid and the base of support (the foot, from heel to toe)
    const grid = new THREE.GridHelper(4, 40, 0x2a2a31, 0x15151a);
    scene.add(grid);
    const footW = 0.1;
    const bos = new THREE.Mesh(new THREE.PlaneGeometry(info.foot.toe + info.foot.heel, footW * 2),
      new THREE.MeshBasicMaterial({ color: 0x3a3a46, transparent: true, opacity: 0.55, side: THREE.DoubleSide }));
    bos.rotation.x = -Math.PI / 2;
    bos.position.set((info.foot.toe - info.foot.heel) / 2, 0.002, 0);
    scene.add(bos);
    const bosEdge = new THREE.LineSegments(new THREE.EdgesGeometry(bos.geometry), new THREE.LineBasicMaterial({ color: 0x8a8a96 }));
    bosEdge.rotation.copy(bos.rotation);
    bosEdge.position.copy(bos.position);
    scene.add(bosEdge);

    // body: capsules and joint spheres (reference), and a second set for the observation layer
    const radius = (m: number) => 0.035 + 0.012 * Math.cbrt(m);
    const group = (opts: { color: number; wire?: boolean; opacity?: number }) => {
      const links: THREE.Mesh[] = []; const joints: THREE.Mesh[] = [];
      info.links.forEach((l, i) => {
        const g = new THREE.CapsuleGeometry(radius(l.mass), l.length, 6, 16);
        const mat = new THREE.MeshStandardMaterial({ color: opts.color, roughness: 0.6, metalness: 0.05, wireframe: !!opts.wire, transparent: true, opacity: opts.opacity ?? 1 });
        const mesh = new THREE.Mesh(g, mat);
        mesh.userData = { part: `link:${l.id}`, len: l.length + 2 * radius(l.mass) };
        scene.add(mesh); links.push(mesh);
        const js = new THREE.Mesh(new THREE.SphereGeometry(radius(l.mass) * 1.25, 16, 12),
          new THREE.MeshStandardMaterial({ color: 0x555560, roughness: 0.5, wireframe: !!opts.wire, transparent: true, opacity: opts.opacity ?? 1 }));
        js.userData = { part: `joint:${info.joints[i].id}` };
        scene.add(js); joints.push(js);
      });
      return { links, joints };
    };
    const ref = group({ color: 0xcfcfd6 });
    const obs = group({ color: 0x5fd0e8 });
    const ghost = group({ color: 0xcfcfd6, wire: true, opacity: 0.35 });

    // markers
    const mk = (geo: THREE.BufferGeometry, color: number) => { const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color })); scene.add(m); return m; };
    const comRef = mk(new THREE.SphereGeometry(0.03, 16, 12), 0xffffff);
    const comEst = mk(new THREE.SphereGeometry(0.03, 16, 12), 0xf0b45a);
    const comObs = mk(new THREE.SphereGeometry(0.026, 16, 12), 0x5fd0e8);
    const copRef = mk(new THREE.BoxGeometry(0.03, 0.012, 0.05), 0xffffff);
    const copObs = mk(new THREE.BoxGeometry(0.03, 0.012, 0.05), 0x5fd0e8);
    const target = mk(new THREE.RingGeometry(0.035, 0.05, 24), 0x78e696);
    target.rotation.x = -Math.PI / 2;
    const dropLine = (color: number) => {
      const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 1, 0)]);
      const l = new THREE.Line(g, new THREE.LineBasicMaterial({ color })); scene.add(l); return l;
    };
    const dropRef = dropLine(0xffffff);
    const gapLine = dropLine(0xf0b45a);    // the distance between the believed and the actual COM, on the ground
    const arrow = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(), 0.3, 0xff8a70, 0.08, 0.05);
    scene.add(arrow);

    // sensor placements (observation devices) at the parts they cover
    const sensors: { mesh: THREE.Mesh; model: string; kind: string; target: string; retired: boolean }[] = [];
    const sensorGroup = new THREE.Group();
    scene.add(sensorGroup);
    for (const m of info.observation.models) {
      const color = KIND_COLOR[m.kind] ?? 0x8a8a96;
      const place = (target: string, geo: THREE.BufferGeometry) => {
        const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color }));
        mesh.userData = { part: null, sensor: m.id };
        sensorGroup.add(mesh); sensors.push({ mesh, model: m.id, kind: m.kind, target, retired: m.blind_windows.some((w) => w[1] > 1e8) });
      };
      const joints = m.joints === undefined || m.joints === 'all' ? info.joints.map((_, i) => i) : (m.joints as number[]);
      if (m.kind === 'posture' || m.kind === 'emg') {
        for (const j of joints) place(`joint:${j}`, m.kind === 'posture' ? new THREE.OctahedronGeometry(0.03) : new THREE.TorusGeometry(0.04, 0.008, 6, 16));
      } else if (m.kind === 'imu') {
        for (const s of m.segments ?? [Math.min(2, n - 1)]) place(`link:${s}`, new THREE.BoxGeometry(0.05, 0.05, 0.05));
      } else if (m.kind === 'contact') place('foot', new THREE.TorusGeometry(0.09, 0.008, 6, 24));
      else if (m.kind === 'respiration') place(`chest:${Math.min(2, n - 1)}`, new THREE.SphereGeometry(0.025, 10, 8));
      else if (m.kind === 'eeg') place('head', new THREE.TorusGeometry(0.1, 0.008, 6, 24));
    }

    const ray = new THREE.Raycaster();
    const pickables = [...ref.links, ...ref.joints, ...obs.links, ...obs.joints];
    let down: { x: number; y: number } | null = null;
    const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY }; };
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) { down = null; return; }
      down = null;
      const r = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = ray.intersectObjects(pickables.filter((m) => m.visible), false)[0];
      const part = hit?.object.userData.part as string | undefined;
      live.current.onSelect(part ?? null);
    };
    renderer.domElement.addEventListener('pointerdown', onDown);
    renderer.domElement.addEventListener('pointerup', onUp);

    const resize = () => {
      const w = el.clientWidth || 300; const h = el.clientHeight || 300;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = '100%'; renderer.domElement.style.height = '100%';
      camera.aspect = w / h; camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    const place = (set: { links: THREE.Mesh[]; joints: THREE.Mesh[] }, angles: (number | null)[], opts: { visibleKnown: boolean; drive?: (number | null)[]; sel: string | null }) => {
      const { points, known } = chain(info, angles.map((a) => a ?? 0));
      set.links.forEach((m, i) => {
        const a = new THREE.Vector3(points[i].x, points[i].y, 0); const b = new THREE.Vector3(points[i + 1].x, points[i + 1].y, 0);
        capsuleBetween(m, a, b, m.userData.len - 0);
        m.visible = opts.visibleKnown ? known[i] : true;
        (m.material as THREE.MeshStandardMaterial).emissive.setHex(opts.sel === m.userData.part ? 0x444466 : 0x000000);
      });
      set.joints.forEach((m, i) => {
        m.position.set(points[i].x, points[i].y, 0);
        m.visible = opts.visibleKnown ? (i === 0 || known[i - 1]) : true;
        const d = opts.drive?.[i];
        const mat = m.material as THREE.MeshStandardMaterial;
        if (d === undefined) mat.color.setHex(0x555560);
        else if (d === null) mat.color.setHex(0x2c2c33);
        else mat.color.copy(driveColor(d));
        mat.emissive.setHex(opts.sel === m.userData.part ? 0x444466 : 0x000000);
      });
      return points;
    };

    let raf = 0;
    const tmp = new THREE.Vector3();
    const frame = () => {
      raf = requestAnimationFrame(frame);
      const { layer: L, overlay: O, selected: S, read: R } = live.current;
      const d = R();
      if (d) {
        const refPts = place(ref, d.theta, { visibleKnown: false, drive: d.drive, sel: S });
        const showRef = L === 'reference';
        ref.links.forEach((m) => { m.visible = showRef; (m.material as THREE.MeshStandardMaterial).opacity = d.alive ? 1 : 0.5; });
        ref.joints.forEach((m) => { m.visible = showRef; });
        place(ghost, d.theta, { visibleKnown: false, sel: null });
        const ghostOn = !showRef && (O || L === 'estimate');
        ghost.links.forEach((m) => { m.visible = ghostOn; });
        ghost.joints.forEach((m) => { m.visible = ghostOn; });
        // observation layer: only segments an observation delivers; the rest is not drawn
        const showObs = L === 'observation';
        if (d.obsAngles) place(obs, d.obsAngles, { visibleKnown: true, drive: d.obsEmg ?? undefined, sel: S });
        obs.links.forEach((m) => { if (!showObs) m.visible = false; else (m.material as THREE.MeshStandardMaterial).opacity = Math.max(0.25, 1 - Math.min(1, d.obsAge / 1.0)); });
        obs.joints.forEach((m) => { if (!showObs) m.visible = false; });
        if (showObs && !d.obsAngles) { obs.links.forEach((m) => { m.visible = false; }); obs.joints.forEach((m) => { m.visible = false; }); }
        // markers
        const comY = refPts.reduce((s, p) => s + p.y, 0) / refPts.length * 0.9 + 0.05;
        comRef.position.set(d.com, comY, 0);
        dropRef.position.set(d.com, 0, 0); dropRef.scale.set(1, comY, 1);
        comRef.visible = dropRef.visible = true;
        copRef.position.set(d.cop, 0.008, 0);
        copRef.visible = showRef || L === 'estimate';
        target.position.set(d.xref, 0.004, 0);
        comEst.visible = L === 'estimate' && d.controllerCom !== null;
        if (d.controllerCom !== null) comEst.position.set(d.controllerCom, comY, 0);
        comObs.visible = (L === 'estimate' || showObs) && d.obsCom !== null;
        if (d.obsCom !== null) comObs.position.set(d.obsCom, comY * 0.96, 0);
        copObs.visible = showObs && d.obsCop !== null;
        if (d.obsCop !== null) copObs.position.set(d.obsCop, 0.008, 0);
        const gapTo = d.controllerCom;
        gapLine.visible = L === 'estimate' && gapTo !== null;
        if (gapTo !== null) { gapLine.position.set(Math.min(gapTo, d.com), 0.01, 0.08); gapLine.rotation.z = -Math.PI / 2; gapLine.scale.set(1, Math.max(1e-4, Math.abs(gapTo - d.com)), 1); }
        // the push on the trunk
        const k = Math.min(2, n - 1);
        const att = new THREE.Vector3(refPts[k].x + (refPts[k + 1].x - refPts[k].x) * 0.8, refPts[k].y + (refPts[k + 1].y - refPts[k].y) * 0.8, 0);
        arrow.visible = Math.abs(d.pushForce) > 0.5;
        if (arrow.visible) { arrow.position.copy(att).add(tmp.set(-Math.sign(d.pushForce) * 0.25, 0, 0)); arrow.setDirection(tmp.set(Math.sign(d.pushForce), 0, 0)); arrow.setLength(0.2 + Math.min(0.5, Math.abs(d.pushForce) / 200), 0.08, 0.05); }
        // sensor markers follow the segment they sit on (reference geometry: where the device is placed on the body)
        for (const s of sensors) {
          const [kind, idx] = s.target.split(':');
          const i = Number(idx);
          if (kind === 'joint') s.mesh.position.set(refPts[i].x, refPts[i].y, 0.07);
          else if (kind === 'link') s.mesh.position.set((refPts[i].x + refPts[i + 1].x) / 2, (refPts[i].y + refPts[i + 1].y) / 2, 0.08);
          else if (kind === 'chest') s.mesh.position.set((refPts[i].x + refPts[i + 1].x) / 2 + 0.05, (refPts[i].y + refPts[i + 1].y) / 2 + 0.05, 0.06);
          else if (kind === 'head') { s.mesh.position.set(refPts[n].x, refPts[n].y + 0.09, 0); s.mesh.rotation.x = Math.PI / 2; }
          else if (kind === 'foot') { s.mesh.position.set((info.foot.toe - info.foot.heel) / 2, 0.01, 0); s.mesh.rotation.x = Math.PI / 2; }
          (s.mesh.material as THREE.MeshBasicMaterial).opacity = s.retired ? 0.25 : 1;
          (s.mesh.material as THREE.MeshBasicMaterial).transparent = s.retired;
        }
      }
      controls.update();
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onDown);
      renderer.domElement.removeEventListener('pointerup', onUp);
      controls.dispose();
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose()); else mat?.dispose?.();
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [info]);

  return <div className="xb-scene" ref={host} />;
}
