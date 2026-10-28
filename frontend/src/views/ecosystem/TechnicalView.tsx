import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { buildBodies, type BodySet } from './bodies';
import { bodyState } from './bodyState';
import type { MeosRecord, Observation } from './meosApi';
import { probeDimensions } from './probes';
import { cableRoutes, collectInstances, collectSegments, componentRows, dimensionLines, measure, partStates, project, type PartState, type Segments, type ViewName } from './technical';

// The technical inspection sheet: three orthographic drawings (front, side, top) of the selected body's real geometry in the pose the record gives at the current tick, a detail
// drawing of one probe, the component table and the state panel. Dimensions are measured on the geometry (scene units, u); nothing on the sheet is typed in.

const INK = '#15171a', ACTIVE = '#0b4a8f', CUT = '#a3261b', MUTE = '#7a7d83', PAPER = '#f4f4f1';
const COLOR: Record<PartState, string> = { active: ACTIVE, idle: INK, inactive: MUTE, retracted: MUTE, overloaded: CUT, cut: CUT, asleep: MUTE };
const LABELLED = ['node', 'probe', 'ring', 'cluster', 'optic', 'reservoir', 'archive', 'joint', 'module', 'sensor', 'chassis'];

export default function TechnicalView({ rec, tick, obs, observability, which, setWhich, probeId, setProbeId }: {
  rec: MeosRecord; tick: number; obs: Observation; observability: string; which: 'ncb' | 'observer'; setWhich: (w: 'ncb' | 'observer') => void; probeId: string; setProbeId: (s: string) => void;
}) {
  const body = useMemo<BodySet>(() => buildBodies('performance', null, () => 0), []);
  useEffect(() => () => body.dispose(), [body]);
  const s = useMemo(() => bodyState(rec, tick, obs, observability), [rec, tick, obs, observability]);
  const aim = useMemo(() => new THREE.Vector3(-66, 0, 16), []);
  const views: ViewName[] = ['front', 'side', 'top'];
  const canvases = useRef<Record<string, HTMLCanvasElement | null>>({});
  const detail = useRef<HTMLCanvasElement | null>(null);
  const [W, H] = [520, 340];

  // pose the bodies for this tick (the drawing is of the pose, so a state-linked part is drawn where the run puts it)
  const posed = useMemo(() => { body.set(s, aim); body.ncb.updateMatrixWorld(true); body.obs.updateMatrixWorld(true); return which; }, [body, s, aim, which]);
  const root = posed === 'ncb' ? body.ncb : body.obs;
  const rows = useMemo(() => componentRows(body, which, s), [body, which, s]);
  const states = useMemo(() => partStates(body.parts, s), [body, s]);

  const data = useMemo(() => {
    const segs = Object.fromEntries(views.map((v) => [v, collectSegments(root, v)])) as Record<ViewName, Segments>;
    const dots = Object.fromEntries(views.map((v) => [v, collectInstances(root, v)])) as Record<ViewName, Float32Array>;
    const hot = Object.fromEntries(views.map((v) => [v, body.parts.filter((p) => p.body === which && LABELLED.includes(p.kind) && ['active', 'cut', 'overloaded'].includes(states[p.id]?.state ?? 'idle')).map((p) => ({ id: p.id, state: states[p.id].state, segs: collectSegments(p.object, v, { filter: (m) => !(m.parent as THREE.LOD | null)?.isLOD || true }) }))])) as Record<ViewName, Array<{ id: string; state: PartState; segs: Segments }>>;
    return { segs, dots, hot };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [root, which, s, states, body]);

  useEffect(() => {
    // one scale for the three drawings
    const dpr = window.devicePixelRatio || 1, m = 30;
    const sc = Math.min(...views.map((v) => { const g = data.segs[v]; return Math.min((W - 2 * m) / Math.max(0.1, g.maxX - g.minX), (H - 2 * m) / Math.max(0.1, g.maxY - g.minY)); }));
    for (const v of views) {
      const cv = canvases.current[v]; if (!cv) continue;
      cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext('2d')!; g.scale(dpr, dpr);
      g.fillStyle = PAPER; g.fillRect(0, 0, W, H);
      const sg = data.segs[v], cx = (sg.minX + sg.maxX) / 2, cy = (sg.minY + sg.maxY) / 2, X = (x: number) => W / 2 + (x - cx) * sc, Y = (y: number) => H / 2 + (y - cy) * sc;
      g.lineWidth = 0.55; g.strokeStyle = INK; g.globalAlpha = 0.85; g.beginPath();
      for (let i = 0; i < sg.data.length; i += 4) { g.moveTo(X(sg.data[i]), Y(sg.data[i + 1])); g.lineTo(X(sg.data[i + 2]), Y(sg.data[i + 3])); }
      g.stroke(); g.globalAlpha = 1;
      // fasteners as dots
      g.fillStyle = INK; const d = data.dots[v]; for (let i = 0; i < d.length; i += 2) g.fillRect(X(d[i]) - 0.6, Y(d[i + 1]) - 0.6, 1.2, 1.2);
      // components that are active, cut or overloaded are drawn again in the state colour
      for (const h of data.hot[v]) { g.strokeStyle = COLOR[h.state]; g.lineWidth = 0.7; g.globalAlpha = 0.9; g.beginPath(); for (let i = 0; i < h.segs.data.length; i += 4) { g.moveTo(X(h.segs.data[i]), Y(h.segs.data[i + 1])); g.lineTo(X(h.segs.data[i + 2]), Y(h.segs.data[i + 3])); } g.stroke(); g.globalAlpha = 1; }
      // cable routing: power solid, resource dashed, data dotted
      for (const r of cableRoutes(body, which, v)) {
        g.strokeStyle = r.kind === 'power' ? ACTIVE : r.kind === 'resource' ? '#2f6f4f' : '#6a4a8a'; g.lineWidth = 0.8 + r.radius * 6; g.setLineDash(r.kind === 'power' ? [] : r.kind === 'resource' ? [7, 3] : [1.5, 3.5]); g.globalAlpha = 0.8;
        g.beginPath(); r.pts.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y)))); g.stroke(); g.setLineDash([]); g.globalAlpha = 1;
      }
      // component identifiers
      g.font = '9px ui-monospace, Menlo, monospace'; g.textBaseline = 'middle'; g.textAlign = 'center';
      for (const p of body.parts.filter((q) => q.body === which && LABELLED.includes(q.kind))) {
        const e = measure(p.object, root); if (e.size.length() === 0) continue;
        const c = e.min.clone().add(e.max).multiplyScalar(0.5), [px, py] = project(c, v), lx = X(px), ly = Y(py) - (p.kind === 'probe' ? 0 : 0);
        const st = states[p.id]?.state ?? 'idle';
        g.fillStyle = PAPER; g.strokeStyle = COLOR[st]; g.lineWidth = 0.8; const w = Math.max(14, p.id.length * 6 + 6);
        g.beginPath(); g.roundRect(lx - w / 2, ly - 7, w, 14, 7); g.fill(); g.stroke(); g.fillStyle = COLOR[st]; g.fillText(p.id, lx, ly + 0.5);
      }
      // dimensions measured on the geometry
      for (const dm of dimensionLines(body, which, v)) {
        const ax = X(dm.a[0]), ay = Y(dm.a[1]), bx = X(dm.b[0]), by = Y(dm.b[1]), horiz = Math.abs(by - ay) < Math.abs(bx - ax), off = dm.offset * sc * 0.35;
        const ox = horiz ? 0 : off, oy = horiz ? off : 0;
        g.strokeStyle = ACTIVE; g.fillStyle = ACTIVE; g.lineWidth = 0.7; g.beginPath();
        g.moveTo(ax, ay); g.lineTo(ax + ox, ay + oy); g.moveTo(bx, by); g.lineTo(bx + ox, by + oy); g.moveTo(ax + ox, ay + oy); g.lineTo(bx + ox, by + oy); g.stroke();
        const ang = Math.atan2(by - ay, bx - ax);
        for (const [px, py, sg] of [[ax + ox, ay + oy, 1], [bx + ox, by + oy, -1]] as const) { g.beginPath(); g.moveTo(px, py); g.lineTo(px + sg * 6 * Math.cos(ang) + 2.2 * Math.sin(ang), py + sg * 6 * Math.sin(ang) - 2.2 * Math.cos(ang)); g.lineTo(px + sg * 6 * Math.cos(ang) - 2.2 * Math.sin(ang), py + sg * 6 * Math.sin(ang) + 2.2 * Math.cos(ang)); g.closePath(); g.fill(); }
        g.font = '9px ui-monospace, Menlo, monospace'; g.textAlign = 'center'; g.save(); g.translate((ax + bx) / 2 + ox + (horiz ? 0 : 8), (ay + by) / 2 + oy - (horiz ? 5 : 0)); if (!horiz) g.rotate(-Math.PI / 2); g.fillText(`${dm.value} u`, 0, 0); g.restore();
      }
      g.fillStyle = INK; g.font = '10px ui-monospace, Menlo, monospace'; g.textAlign = 'left'; g.fillText(v.toUpperCase(), 8, 12);
    }
    // the detail drawing: one probe, side on, with its measured dimensions
    const dv = detail.current;
    if (dv) {
      const probe = body.nodes.flatMap((n) => n.probes).concat(body.observer.probes).find((p) => p.spec.id === probeId) ?? body.nodes[0].probes[0];
      dv.width = W * dpr; dv.height = H * dpr; const g = dv.getContext('2d')!; g.scale(dpr, dpr); g.fillStyle = PAPER; g.fillRect(0, 0, W, H);
      const dims = probeDimensions(probe), sg = collectSegments(probe.group, 'front'), sc2 = Math.min((W - 90) / Math.max(0.1, sg.maxX - sg.minX), (H - 40) / Math.max(0.1, sg.maxY - sg.minY)), cx = (sg.minX + sg.maxX) / 2, cy = (sg.minY + sg.maxY) / 2;
      const X = (x: number) => W / 2 - 40 + (x - cx) * sc2, Y = (y: number) => H / 2 + (y - cy) * sc2;
      g.strokeStyle = INK; g.lineWidth = 0.7; g.beginPath(); for (let i = 0; i < sg.data.length; i += 4) { g.moveTo(X(sg.data[i]), Y(sg.data[i + 1])); g.lineTo(X(sg.data[i + 2]), Y(sg.data[i + 3])); } g.stroke();
      const top = Y(0), tip = Y(-dims.measuredLength), xr = X(sg.maxX) + 18;
      g.strokeStyle = ACTIVE; g.fillStyle = ACTIVE; g.lineWidth = 0.7; g.beginPath(); g.moveTo(xr, top); g.lineTo(xr, tip); g.moveTo(xr - 4, top); g.lineTo(xr + 4, top); g.moveTo(xr - 4, tip); g.lineTo(xr + 4, tip); g.stroke();
      g.font = '9px ui-monospace, Menlo, monospace'; g.textAlign = 'left';
      const lines = [`probe ${probe.spec.id}`, `length ${dims.measuredLength} u`, `diameter ${dims.diameter} u`, `housing ${dims.housing} u`, `insulated ${dims.insulated} u`, `tip ${dims.tip}`, `retract mechanism ${probe.spec.retractor ? 'yes' : 'no'}`, `strain cable ${probe.spec.strain ? 'yes' : 'no'}`, `state ${states[probe.spec.id]?.state ?? 'idle'}`];
      lines.forEach((t, i) => { g.fillStyle = i === 0 ? INK : ACTIVE; g.fillText(t, W - 118, 24 + i * 13); });
      g.fillStyle = INK; g.font = '10px ui-monospace, Menlo, monospace'; g.fillText('DETAIL', 8, 12);
    }
    // the drawing depends on the data, the body, the selection and the states; W, H, root and views are constants of this component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, body, which, states, probeId]);

  const probes = body.nodes.flatMap((n) => n.probes).concat(body.observer.probes).map((p) => p.spec.id).filter((id) => (which === 'ncb' ? !id.startsWith('O') : id.startsWith('O')));
  const title = which === 'ncb' ? 'NON-CENTRAL EXPERIMENTAL BODY' : 'ADAPTIVE OBSERVATION NODE';
  const sub = which === 'ncb' ? 'three nodes joined by a cable network · presentation of a MEOS-0 run' : 'asymmetric carrier, telescoping boom, retractable probe ring · presentation of a MEOS-0 run';
  const routes = body.cables.concat(which === 'observer' ? body.observer.cables : []).flatMap((cs) => cs.routes.map((r) => ({ id: r.id, kind: r.kind, radius: r.radius, length: +cs.curves[r.id].getLength().toFixed(2) })));
  return (
    <div className="eco-sheet" data-testid="eco-sheet">
      <header>
        <div className="eco-sheet-id"><b>TECHNICAL INSPECTION</b><span>sheet {which === 'ncb' ? '21' : '20'} · tick {tick} · status {s.status}</span></div>
        <h2>{title}</h2><p>{sub}</p>
        <nav><button className={which === 'ncb' ? 'on' : ''} onClick={() => { setWhich('ncb'); setProbeId('A1'); }}>non-central body</button><button className={which === 'observer' ? 'on' : ''} onClick={() => { setWhich('observer'); setProbeId('O1'); }}>observation node</button>
          <span className="dim">detail probe</span>{probes.map((id) => <button key={id} className={probeId === id ? 'on' : ''} onClick={() => setProbeId(id)}>{id}</button>)}</nav>
      </header>
      <div className="eco-sheet-grid">
        {views.map((v) => <figure key={v}><canvas ref={(el) => { canvases.current[v] = el; }} style={{ width: W, height: H }} aria-label={`${v} view`} /><figcaption>{v} · one scale for the three views · units are scene units (u), measured on the geometry</figcaption></figure>)}
        <figure><canvas ref={detail} style={{ width: W, height: H }} aria-label="probe detail" /><figcaption>probe detail · side view</figcaption></figure>
        <div className="eco-sheet-state">
          <h4>state read from the run</h4>
          <dl>
            <dt>observation</dt><dd>every {obs.sampling_interval} tick(s), stride {obs.spatial_stride}, window {obs.window}, covers {(s.coverage * 100).toFixed(0)}% of the arena; {s.sampling ? 'a sampled tick' : 'not a sampled tick'}</dd>
            <dt>observability</dt><dd>{observability}</dd>
            <dt>sampling interval</dt><dd>{s.interval} (the ring turns once per interval)</dd>
            <dt>XenoBody boundary</dt><dd>{s.arenaRadius === null ? 'the whole grid' : `arena radius ${s.arenaRadius}`}; interaction channel {s.couplingCut ? 'CUT' : 'intact'}</dd>
            <dt>Address Domain</dt><dd>A1 {s.address.A1 ?? 'intact'} · A2 {s.address.A2 ?? 'intact'}</dd>
            <dt>M2-sensitive</dt><dd>{rec.config.m2 && rec.config.m2.sense !== 'none' ? `yes: A1's sensing also reads M2 (${rec.config.m2.sense}); drawn on the probes of B / the sensor head` : 'no (M2 is not connected in this run)'}</dd>
            <dt>history</dt><dd>re-entry {s.historyEnabled ? 'enabled (archive latch closed)' : 'DISABLED (latch open)'}</dd>
            <dt>resource</dt><dd>{s.pulseAge === null ? 'no pulse in the last 14 ticks' : `pulse ${s.pulseAmount} injected ${s.pulseAge} ticks ago`}</dd>
            <dt>run</dt><dd>{s.collapsed ? 'COLLAPSED: probes retracted, lamps dark' : s.recoveryAge !== null && s.recoveryAge < 24 ? `recovering: ${s.recoveryAge} ticks since recovery` : s.status}</dd>
          </dl>
          <h4>lines</h4>
          <ul>{routes.map((r) => <li key={r.id}><i className={`eco-line ${r.kind}`} />{r.id}: {r.kind === 'power' ? 'energy line' : r.kind === 'resource' ? 'resource line' : 'data line'}, radius {r.radius}, length {r.length} u</li>)}</ul>
          <p className="dim">state colours: <b style={{ color: ACTIVE }}>active</b> · black idle · <span style={{ color: MUTE }}>inactive / retracted / asleep</span> · <b style={{ color: CUT }}>cut / overloaded</b></p>
        </div>
      </div>
      <table className="eco-sheet-table"><thead><tr><th>ID</th><th>component</th><th>built from</th><th>measured extent (u)</th><th>state</th><th>because</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.id} className={r.state}><td>{r.id}</td><td>{r.name}</td><td>{r.params}</td><td>{r.extent}</td><td>{r.state}</td><td>{r.because}</td></tr>)}</tbody></table>
    </div>
  );
}
