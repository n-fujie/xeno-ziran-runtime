import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { buildBodies, type BodySet } from './bodies';
import { bodyState } from './bodyState';
import type { MeosRecord, Observation, Observed, PathActivity, PathId } from './meosApi';
import { deltaSnapshots, inspectAt, pathStatesAt, snapshotTicks, type Marker, type Snapshot, type SssRegion } from './research';
import { ALL_MAP_LAYERS, DEFAULT_MAP_LAYERS, buildResearchMap, MAP_LAYERS, affected, type BodiesSpec, type MapLayer } from './researchMap';
import { drawResearchMap } from './researchMapDraw';
import type { RepairBlock } from './meosApi';
import { repairStateAt } from './repair';
import { drawRepairFigure } from './repairFigureDraw';
import { routeGraph, topologyAt, type LibraryMfs, type Outcome, type RejectedCandidate, type Topology } from './routeGraph';
import { drawRouteGraph, ROUTE_TOGGLES, type RouteToggle } from './routeGraphDraw';
import { probeDimensions } from './probes';
import { cableRoutes, collectInstances, collectSegments, componentRows, dimensionLines, measure, partStates, project, type PartState, type Segments, type ViewName } from './technical';

// The technical inspection sheet: three orthographic drawings (front, side, top) of the selected body's real geometry in the pose the record gives at the current tick, a detail
// drawing of one probe, the component table and the state panel. Dimensions are measured on the geometry (scene units, u); nothing on the sheet is typed in.

const INK = '#15171a', ACTIVE = '#0b4a8f', CUT = '#a3261b', MUTE = '#7a7d83', PAPER = '#f4f4f1';
const COLOR: Record<PartState, string> = { active: ACTIVE, idle: INK, inactive: MUTE, retracted: MUTE, overloaded: CUT, cut: CUT, asleep: MUTE };
const LABELLED = ['node', 'probe', 'ring', 'cluster', 'optic', 'reservoir', 'archive', 'joint', 'module', 'sensor', 'chassis'];

/** The research readings the sheet adds to the drawings (all computed from the record by the view): the observed state, the path activity, the event markers and the SSS region. */
export interface SheetResearch { observed: Observed | null; paths: PathActivity | null; markers: Marker[]; sssRegion: SssRegion; compare: boolean; bodies: BodiesSpec | null; body: string; setBody: (b: string) => void; topology: Topology | null; library: LibraryMfs[]; rejected?: RejectedCandidate[]; outcomes: Outcome[]; repair?: RepairBlock | null; repairable?: boolean }
// cable id -> the operational path it carries (the cable network of the non-central body, by what moves along it)
const CABLE_PATH: Record<string, PathId> = { BCb: 'coupling', BCc: 'coupling', BCa: 'coupling', JB: 'coupling', JC: 'resource', AC: 'resource', AB: 'resource', AJ: 'resource', CRES: 'resource', ARCH: 'history_access', OBSV: 'observation', REC: 'recovery' };

export default function TechnicalView({ rec, tick, obs, observability, which, setWhich, probeId, setProbeId, research }: {
  rec: MeosRecord; tick: number; obs: Observation; observability: string; which: 'ncb' | 'observer'; setWhich: (w: 'ncb' | 'observer') => void; probeId: string; setProbeId: (s: string) => void; research?: SheetResearch;
}) {
  const [mapLayers, setMapLayers] = useState<Set<MapLayer>>(() => { const q = (new URLSearchParams(location.search).get('layer') ?? new URLSearchParams(location.search).get('maplayers')); return q ? new Set(q.split(',').filter((l) => ALL_MAP_LAYERS.has(l as MapLayer)) as MapLayer[]) : new Set(DEFAULT_MAP_LAYERS); });  // ?maplayers=a,b limits the layers (the captures)
  const toggleLayer = (id: MapLayer) => setMapLayers((l) => { const n = new Set(l); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const [routeOn, setRouteOn] = useState<Set<RouteToggle>>(() => { const q = new URLSearchParams(location.search).get('routelayers'); return new Set((q ? q.split(',') : ROUTE_TOGGLES.map((x) => x.id)).filter((x) => ROUTE_TOGGLES.some((r) => r.id === x)) as RouteToggle[]); });  // ?routelayers=a,b limits the route toggles (the captures)
  const toggleRoute = (id: RouteToggle) => setRouteOn((l) => { const n = new Set(l); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const repairCanvas = useRef<HTMLCanvasElement | null>(null), routeCanvas = useRef<HTMLCanvasElement | null>(null), mapCanvas = useRef<HTMLCanvasElement | null>(null), compareCanvases = useRef<Array<HTMLCanvasElement | null>>([]);
  const body = useMemo<BodySet>(() => buildBodies('performance', null, () => 0), []);
  useEffect(() => () => body.dispose(), [body]);
  const region = research?.sssRegion ?? 'ACTIVE';
  const s = useMemo(() => bodyState(rec, tick, obs, observability, region), [rec, tick, obs, observability, region]);
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
        const pid = CABLE_PATH[r.id], pst = pid && research && mapLayers.has(`path.${pid}` as MapLayer) ? pathStatesAt(research.paths, tick)[pid] : null;  // a cable of a path whose layer is on takes the path's state
        g.strokeStyle = pst === 'cut' ? CUT : r.kind === 'power' ? ACTIVE : r.kind === 'resource' ? '#2f6f4f' : '#6a4a8a'; g.lineWidth = 0.8 + r.radius * 6 + (pst === 'active' ? 0.8 : 0); g.setLineDash(pst === 'cut' ? [4, 4] : r.kind === 'power' ? [] : r.kind === 'resource' ? [7, 3] : [1.5, 3.5]); g.globalAlpha = pst === 'quiet' ? 0.35 : 0.8;
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
  }, [data, body, which, states, probeId, mapLayers, research, tick]);

  // the research map (and, in comparison mode, the three snapshots with their differences)
  const routeState = useMemo(() => (research?.topology ? topologyAt(research.topology, tick, research.library) : null), [research, tick]);
  const inspect = useMemo(() => inspectAt(rec, research?.observed, tick, research?.paths, research?.markers, routeState), [rec, research, tick, routeState]);
  const snapshots = useMemo<Snapshot[]>(() => {
    if (!research?.compare) return [];
    const tk = snapshotTicks(rec);
    return ([['baseline', tk.baseline], ['intervention', tk.intervention], ['recovered', tk.recovered]] as const).map(([label, t]) => {
      const st = partStates(body.parts, bodyState(rec, t, obs, observability, region));
      return { label, tick: t, inspect: inspectAt(rec, research.observed, t, research.paths, research.markers), parts: Object.fromEntries(Object.entries(st).map(([k, v]) => [k, v.state])) };
    });
  }, [rec, research, body, obs, observability, region]);
  const deltas = useMemo(() => snapshots.slice(1).map((b, i) => deltaSnapshots(snapshots[i], b)), [snapshots]);
  useEffect(() => {
    const dpr = window.devicePixelRatio || 1;
    const draw = (cv: HTMLCanvasElement | null, t: number, ins: ReturnType<typeof inspectAt>, w: number, h: number) => {
      if (!cv) return;
      cv.width = w * dpr; cv.height = h * dpr; const g = cv.getContext('2d')!; g.scale(dpr, dpr);
      drawResearchMap(g, buildResearchMap({ rec, tick: t, obs, inspect: ins, paths: research?.paths, markers: research?.markers ?? [], layers: mapLayers, body: research?.body, bodies: research?.bodies, route: ins.route, rejected: research?.rejected, repair: research?.repair ? { state: repairStateAt(research.repair, t) as NonNullable<ReturnType<typeof repairStateAt>>, repairable: research.repairable } : null }), w, h);
    };
    draw(mapCanvas.current, tick, inspect, 760, 700);
    snapshots.forEach((sn, i) => draw(compareCanvases.current[i], sn.tick, sn.inspect, 500, 470));
    const pc = repairCanvas.current, rstate = repairStateAt(research?.repair, tick);
    if (pc && research?.repair && rstate) { pc.width = 1060 * dpr; pc.height = 300 * dpr; const g = pc.getContext('2d')!; g.scale(dpr, dpr); drawRepairFigure(g, research.repair, rstate, 1060, 300); }
    const rc = routeCanvas.current;
    if (rc && research?.topology) { rc.width = 1060 * dpr; rc.height = 440 * dpr; const g = rc.getContext('2d')!; g.scale(dpr, dpr); drawRouteGraph(g, routeGraph(research.topology, research.library, tick, research.rejected), 1060, 440, routeOn); }
    // the map depends on the record, the tick, the observation, the layers and the research readings
  }, [rec, tick, obs, inspect, snapshots, mapLayers, research, routeOn]);  // research carries the bodies, the selected body and the route topology

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
        {research && <figure className="eco-sheet-wide" data-testid="eco-research-map"><div className="eco-map-row"><canvas ref={mapCanvas} style={{ width: 760, height: 700 }} aria-label="research map" />
          <dl className="eco-map-legend">{MAP_LAYERS.map((l) => <><dt key={l.id + 't'} className={mapLayers.has(l.id) ? 'on' : ''}>{l.label}</dt><dd key={l.id}>{l.what}</dd></>)}</dl></div>
          <figcaption>research map · plan of the arena at tick {tick} · MODEL RESULT: boundaries, paths, observation and interventions are read from the record · solid heavy = XenoBody boundary · dash-dot = Address Domain · dashed = observation boundary · path arrows: solid active, dotted quiet, red dashed cut</figcaption></figure>}
        {research?.repair && <figure className="eco-sheet-wide" data-testid="eco-repair-figure"><canvas ref={repairCanvas} style={{ width: 1060, height: 300 }} aria-label="repair" />
          <figcaption>repair at tick {tick} · MODEL RESULT, drawn from the events of this run (the stress, the repair actions with their ticks and magnitudes, the status record): a damaged path is red dotted and crossed, a world-state action violet, an internal reconfiguration blue, a temporary bypass green dash-dot, a repaired path green; the repair site is where the action acted and need not be the damaged path.</figcaption></figure>}
        {research?.topology && <figure className="eco-sheet-wide" data-testid="eco-route-topology"><div className="eco-map-row"><canvas ref={routeCanvas} style={{ width: 1060, height: 440 }} aria-label="route topology" />
          <div className="eco-map-legend"><b>Route topology · MODEL RESULT</b><div className="eco-layers">{ROUTE_TOGGLES.map((l) => <button key={l.id} title={l.what} className={routeOn.has(l.id) ? 'on' : ''} onClick={() => toggleRoute(l.id)}>{l.label}</button>)}</div>
            {routeState && <dl><dt>current MFS</dt><dd>{routeState.currentMfs}</dd><dt>enabled</dt><dd>{routeState.enabled.join(', ')}</dd><dt>dormant</dt><dd>{routeState.dormant.join(', ') || 'none'}</dd><dt>failed</dt><dd>{routeState.failed.join(', ') || 'none'}</dd><dt>alternative routes</dt><dd>{routeState.alternative.map((m) => m.id).join(', ') || 'none'} ({routeState.available.length} of {routeState.available.length + routeState.disabled.length} library MFS are open)</dd><dt>routes closed</dt><dd>{routeState.disabled.filter((d) => routeState.named.includes(d.mfs.id)).map((d) => `${d.mfs.id} (needs ${d.because.join(', ')})`).join('; ') || 'none'}</dd><dt>last transition</dt><dd>{routeState.lastTransition ? `t${routeState.lastTransition.tick}: ${routeState.lastTransition.from} → ${routeState.lastTransition.to}, trigger ${routeState.lastTransition.trigger.join(', ')}, cost ${routeState.lastTransition.cost}` : 'none'}</dd></dl>}</div></div>
          <figcaption>route topology at tick {tick} · every line is an edge derived from the record, the saved MFS library and the path definitions (a dashed grey line is a path that needs an installed component not in use; a red crossed line a path with a removed component; green a path a controller switched on)</figcaption></figure>}
        {research?.compare && snapshots.length === 3 && <figure className="eco-sheet-wide" data-testid="eco-compare">
          <div className="eco-compare">{snapshots.map((sn, i) => <div key={sn.label}><canvas ref={(el) => { compareCanvases.current[i] = el; }} style={{ width: 500, height: 470 }} aria-label={`${sn.label} map`} /><b>{sn.label} · tick {sn.tick}</b><span>{sn.inspect.operational} · observed {sn.inspect.observed ?? 'full'} · {sn.inspect.observability ?? 'full observation'}</span></div>)}</div>
          <figcaption>comparison of three snapshots of one record (same seed, same configuration) · MODEL RESULT</figcaption>
          <table className="eco-sheet-table"><thead><tr><th>change</th><th>state</th><th>components</th><th>paths</th><th>boundary</th><th>address</th><th>observability</th></tr></thead><tbody>
            {deltas.map((d) => <tr key={d.to}><td>{d.from} → {d.to}</td><td>{d.status[0]} → {d.status[1]}</td><td>{d.components.length ? d.components.map((c) => `${c.id} ${c.from}→${c.to}`).join('; ') : 'none'}</td><td>{d.paths.length ? d.paths.map((c) => `${c.path} ${c.from}→${c.to}`).join('; ') : 'none'}</td>
              <td>{[...d.boundary.opened.map((c) => `opened ${c}`), ...d.boundary.closed.map((c) => `closed ${c}`), ...(d.boundary.arenaRadius ? [`arena ${d.boundary.arenaRadius.join('→')}`] : [])].join('; ') || 'none'}</td><td>{d.address.length ? d.address.map((a) => `${a.target}: ${a.from} → ${a.to}`).join('; ') : 'none'}</td><td>{d.observabilityChange === 'lost' ? 'LOST' : d.observabilityChange === 'gained' ? 'GAINED' : 'unchanged'} ({d.observability[0] ?? 'full'} → {d.observability[1] ?? 'full'})</td></tr>)}</tbody></table>
        </figure>}
        <div className="eco-sheet-state">
          <h4>MODEL RESULT · state read from the run</h4>
          {research && <dl><dt>operational state</dt><dd>{inspect.operational}</dd><dt>observed state</dt><dd>{inspect.observed ?? 'full observation: the operational state'}</dd><dt>observability</dt><dd>{inspect.observability ?? 'full observation'}{inspect.limiting.length ? ` — limited by ${inspect.limiting.join(', ')}` : ''}</dd>
            <dt>paths</dt><dd>{(Object.entries(inspect.paths) as Array<[string, string]>).map(([k, v]) => `${k}: ${v}`).join(' · ')}</dd></dl>}
          <dl>
            <dt>observation</dt><dd>every {obs.sampling_interval} tick(s), stride {obs.spatial_stride}, window {obs.window}, covers {(s.coverage * 100).toFixed(0)}% of the arena; {s.sampling ? 'a sampled tick' : 'not a sampled tick'}</dd>
            <dt>observability</dt><dd>{observability}</dd>
            <dt>sampling interval</dt><dd>{s.interval} (the ring turns once per interval)</dd>
            <dt>XenoBody boundary</dt><dd>{s.arenaRadius === null ? 'the whole grid' : `arena radius ${s.arenaRadius}`}; interaction channel {s.couplingCut ? 'CUT' : 'intact'}</dd>
            <dt>Address Domain</dt><dd>A1 {s.address.A1 ?? 'intact'} · A2 {s.address.A2 ?? 'intact'}</dd>
            <dt>M2-sensitive</dt><dd>{rec.config.m2 && rec.config.m2.sense !== 'none' ? `yes: A1's sensing also reads M2 (${rec.config.m2.sense}); the M2 tap is node B's probe B2, ${s.m2.state ?? 'idle'} at this tick (A1 senses ${s.m2.sensed.toFixed(3)} of M2)` : 'no (M2 is not connected in this run)'}</dd>
            <dt>SSS</dt><dd>scale {s.sss.scale} · size {s.sss.size} · speed {s.sss.speed}; region {region}</dd>
            <dt>history</dt><dd>re-entry {s.historyEnabled ? 'enabled (archive latch closed)' : 'DISABLED (latch open)'}</dd>
            <dt>resource</dt><dd>{s.pulseAge === null ? 'no pulse in the last 14 ticks' : `pulse ${s.pulseAmount} injected ${s.pulseAge} ticks ago`}</dd>
            <dt>run</dt><dd>{s.collapsed ? 'COLLAPSED: probes retracted, lamps dark' : s.recoveryAge !== null && s.recoveryAge < 24 ? `recovering: ${s.recoveryAge} ticks since recovery` : s.status}</dd>
          </dl>
          {research && <><h4>VISUAL REPRESENTATION · how the bodies are posed</h4>
          <dl><dt>boom reach</dt><dd>{s.mech.boomPreload.toFixed(2)} (SSS scale)</dd><dt>probe ring tilt</dt><dd>{(s.mech.ringTilt * 57.3).toFixed(1)}° (SSS size)</dd><dt>coupling tension</dt><dd>{s.mech.couplingTension.toFixed(2)} (SSS speed)</dd><dt>archive latch ajar</dt><dd>{(s.mech.archiveAjar * 57.3).toFixed(0)}° (SSS region {region})</dd><dt>reservoir regulation</dt><dd>{s.mech.regulation.toFixed(2)} (SSS speed)</dd></dl>
          <p className="dim">A pose is a rule of this view (mechanics.ts); it is never evidence about the run.</p>
          <h4>XenoBody (retained operational body)</h4><div className="eco-layers">{['B1', 'B2', 'B3'].map((k) => <button key={k} className={research.body === k ? 'on' : ''} title={research.bodies?.partitions[k]?.label} onClick={() => research.setBody(k)}>{k}</button>)}</div>
          <h4>research map layers</h4><div className="eco-layers">{MAP_LAYERS.map((l) => <button key={l.id} title={l.what} className={mapLayers.has(l.id) ? 'on' : ''} onClick={() => toggleLayer(l.id)}>{l.label}</button>)}</div>
          {research.markers.filter((m) => m.tick <= tick).slice(-6).length > 0 && <ul>{research.markers.filter((m) => m.tick <= tick).slice(-6).map((m, i) => <li key={i}>t{m.tick} {m.label} → {affected(rec.intervention_log.find((iv) => iv.tick === m.tick && m.label.startsWith(iv.op)) ?? { tick: m.tick, op: m.kind, event: 0 })}</li>)}</ul>}</>}
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
