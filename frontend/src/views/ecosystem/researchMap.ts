// XENO ECOSYSTEM — the research map of the technical inspection sheet: a plan of the arena at one tick, drawn from the record, that puts on one sheet what the run's own state, the
// observation and the boundaries are. It is a drawing spec (primitives in cell coordinates), not a canvas call, so that it can be tested.
//
// Three different boundaries are drawn with three different line types and never merged:
//   XenoBody boundary      solid, heavy      what is retained as the operational body (A1, A2 and their sensing windows); a cut coupling opens a gap in it
//   Address Domain         dash-dot          the arena the configurations are addressable in (arena radius, or the whole grid); a stale / delayed / lost address is a pointer to the cell it names
//   observation            dashed            the region the observer looks at, with its sampling lattice and an occluder (hatched) if there is one
// Operational paths (resource, coupling, history access, observation, recovery) are arrows whose line type says their state: solid = active, dotted = quiet, red dashed with a cross = cut.
import type { Observation, MeosRecord, PathId } from './meosApi';
import { PATH_IDS } from './meosApi';
import { pathStatesAt, type Inspect, type Marker, type PathState } from './research';
import type { PathActivity } from './meosApi';

export type LineStyle = 'solid' | 'dash' | 'dashdot' | 'dot';
export type Ink = 'ink' | 'active' | 'cut' | 'mute' | 'green' | 'violet';
export type Prim =
  | { t: 'poly'; id: string; pts: Array<[number, number]>; style: LineStyle; w: number; ink: Ink; arrow?: boolean }
  | { t: 'rect'; id: string; x0: number; y0: number; x1: number; y1: number; style: LineStyle; w: number; ink: Ink; hatch?: boolean }
  | { t: 'dots'; id: string; pts: Array<[number, number]>; ink: Ink }
  | { t: 'cross'; id: string; x: number; y: number; ink: Ink }
  | { t: 'text'; id: string; x: number; y: number; text: string; ink: Ink; align?: 'left' | 'center' }
  | { t: 'flag'; id: string; x: number; y: number; text: string; ink: Ink };

export type MapLayer = 'boundary.xenobody' | 'boundary.address' | 'boundary.observation' | 'observation' | 'interventions' | `path.${PathId}`;
export const MAP_LAYERS: Array<{ id: MapLayer; label: string; what: string }> = [
  { id: 'boundary.xenobody', label: 'XenoBody boundary', what: 'solid heavy line round the operational body (A1, A2 and their sensing windows)' },
  { id: 'boundary.address', label: 'Address Domain', what: 'dash-dot: the addressable arena; pointers to the cell a stale, delayed or lost address names' },
  { id: 'boundary.observation', label: 'observation boundary', what: 'dashed: the observed region, with the occluder hatched' },
  { id: 'observation', label: 'observation lattice', what: 'dots on the sampling lattice, and the interval, resolution and window of the observation' },
  { id: 'path.resource', label: 'resource path', what: 'material from the source field to A1 and back through renewal' },
  { id: 'path.coupling', label: 'coupling path', what: "A1's alteration reaching A2" },
  { id: 'path.history_access', label: 'history-access path', what: 'recorded traces re-entering the next firing' },
  { id: 'path.observation', label: 'observation path', what: 'the stimulus each configuration senses (not the research observer)' },
  { id: 'path.recovery', label: 'recovery path', what: 'renewal and the pulse that restores a collapsed operation' },
  { id: 'interventions', label: 'interventions', what: 'flags at the cells an intervention names; a strip for the others' },
];
export const ALL_MAP_LAYERS = new Set<MapLayer>(MAP_LAYERS.map((l) => l.id));

const style = (s: PathState): LineStyle => (s === 'active' ? 'solid' : s === 'cut' ? 'dash' : 'dot');
const ink = (s: PathState, base: Ink): Ink => (s === 'cut' ? 'cut' : s === 'quiet' ? 'mute' : base);

export interface MapSpec { n: number; prims: Prim[]; summary: Record<string, string> }

/** The research map at ``tick``. ``inspect`` is the state at that tick (``research.inspectAt``); ``paths`` are the run's path activity; ``markers`` its event markers. */
export function buildResearchMap(o: { rec: MeosRecord; tick: number; obs: Partial<Observation>; inspect: Inspect; paths: PathActivity | null | undefined; markers: Marker[]; layers?: Set<MapLayer> }): MapSpec {
  const { rec, inspect: ins } = o, L = o.layers ?? ALL_MAP_LAYERS, n = rec.config.grid, t = ins.tick, f = rec.frames[t];
  const P: Prim[] = [], on = (l: MapLayer) => L.has(l), ps = pathStatesAt(o.paths, t);
  const a1 = [f.A1.x + 0.5, f.A1.y + 0.5] as [number, number], a2 = [f.A2.x + 0.5, f.A2.y + 0.5] as [number, number];
  const r1 = Number(rec.final_config.entities.A1.sensor_radius ?? 2) * ins.sss.scale, r2 = Number(rec.final_config.entities.A2.sensor_radius ?? 2) * ins.sss.scale;
  const obs = { sampling_interval: 1, spatial_stride: 1, region: null as number[] | null, aggregation: 1, window: 48, ...o.obs };

  // the cell grid
  for (let i = 0; i <= n; i++) {
    P.push({ t: 'poly', id: 'grid', pts: [[i, 0], [i, n]], style: 'solid', w: 0.25, ink: 'mute' }, { t: 'poly', id: 'grid', pts: [[0, i], [n, i]], style: 'solid', w: 0.25, ink: 'mute' });
  }
  P.push({ t: 'text', id: 'source', x: 0.1, y: -0.45, text: 'source field R (x = 0)', ink: 'mute', align: 'left' });

  // Address Domain: the addressable arena, and pointers from a configuration to the cell its address names
  if (on('boundary.address')) {
    const ar = ins.boundary.arenaRadius;
    if (ar === null) P.push({ t: 'rect', id: 'boundary.address', x0: -0.18, y0: -0.18, x1: n + 0.18, y1: n + 0.18, style: 'dashdot', w: 1.1, ink: 'violet' });
    else {
      const cx = n / 2, pts: Array<[number, number]> = [];
      for (let k = 0; k <= 48; k++) { const a = (k / 48) * Math.PI * 2; pts.push([cx + Math.cos(a) * ar, cx + Math.sin(a) * ar]); }
      P.push({ t: 'poly', id: 'boundary.address', pts, style: 'dashdot', w: 1.1, ink: 'violet' });
    }
    for (const nm of ['A1', 'A2'] as const) {
      const a = ins.address[nm], body = nm === 'A1' ? a1 : a2;
      if (a.mode === 'loss') P.push({ t: 'cross', id: 'boundary.address', x: body[0], y: body[1], ink: 'cut' }, { t: 'text', id: 'boundary.address', x: body[0] + 0.5, y: body[1] - 0.6, text: `${nm} address lost`, ink: 'cut', align: 'left' });
      else if (a.mode) P.push({ t: 'text', id: 'boundary.address', x: body[0] + 0.5, y: body[1] - 0.6, text: `${nm} address ${a.mode}${a.integrity < 1 ? ` ${(a.integrity * 100).toFixed(0)}%` : ''}`, ink: 'violet', align: 'left' });
      if (a.names[0] !== a.cell[0] || a.names[1] !== a.cell[1]) {
        const to: [number, number] = [a.names[0] + 0.5, a.names[1] + 0.5];
        P.push({ t: 'poly', id: 'boundary.address', pts: [body, to], style: 'dot', w: 1.1, ink: 'violet', arrow: true }, { t: 'text', id: 'boundary.address', x: to[0], y: to[1] + 0.9, text: `${nm} address names (${a.names.join(',')})`, ink: 'violet', align: 'center' });
      }
    }
  }

  // XenoBody boundary: round the retained operational body; the coupling's cut opens a gap between the two halves
  if (on('boundary.xenobody')) {
    const x0 = Math.min(a1[0] - r1, a2[0] - r2) - 0.2, x1 = Math.max(a1[0] + r1, a2[0] + r2) + 0.2, y0 = Math.min(a1[1] - r1, a2[1] - r2) - 0.2, y1 = Math.max(a1[1] + r1, a2[1] + r2) + 0.2;
    const cut = ins.boundary.open.includes('interaction_channel') || ins.boundary.open.includes('feedback'), mx = (x0 + x1) / 2;
    const half = (xa: number, xb: number, id: string) => P.push({ t: 'poly', id, pts: [[xa, y0], [xb, y0], [xb, y1], [xa, y1], [xa, y0]], style: 'solid', w: 2.4, ink: cut ? 'cut' : 'ink' });
    if (cut) { half(x0, mx - 0.25, 'boundary.xenobody'); half(mx + 0.25, x1, 'boundary.xenobody'); } else half(x0, x1, 'boundary.xenobody');
    P.push({ t: 'text', id: 'boundary.xenobody', x: x0, y: y0 - 0.35, text: `XenoBody ${cut ? '(coupling cut: open)' : '(closed)'}${ins.boundary.open.length ? ` · cut: ${ins.boundary.open.join(', ')}` : ''}`, ink: cut ? 'cut' : 'ink', align: 'left' });
  }

  // observation: region, lattice, occluder
  const stride = Math.max(1, obs.spatial_stride), reg = obs.region ?? [0, 0, n - 1, n - 1];
  if (on('boundary.observation')) {
    P.push({ t: 'rect', id: 'boundary.observation', x0: reg[0], y0: reg[1], x1: reg[2] + 1, y1: reg[3] + 1, style: 'dash', w: 1.2, ink: 'active' });
    if (obs.occluder) P.push({ t: 'rect', id: 'boundary.observation', x0: obs.occluder[0], y0: obs.occluder[1], x1: obs.occluder[2] + 1, y1: obs.occluder[3] + 1, style: 'solid', w: 0.8, ink: 'active', hatch: true });
  }
  if (on('observation')) {
    const dots: Array<[number, number]> = [], ox = obs.spatial_offset?.[0] ?? 0, oy = obs.spatial_offset?.[1] ?? 0;
    for (let x = 0; x < n; x++) for (let y = 0; y < n; y++) if ((x - ox) % stride === 0 && (y - oy) % stride === 0 && x >= reg[0] && x <= reg[2] && y >= reg[1] && y <= reg[3]) dots.push([x + 0.5, y + 0.5]);
    P.push({ t: 'dots', id: 'observation', pts: dots, ink: 'active' });
    const sampled = t % Math.max(1, obs.sampling_interval) === 0;
    P.push({ t: 'text', id: 'observation', x: n, y: n + 0.9, text: `interval ${obs.sampling_interval} · stride ${stride} · window ${obs.window}${obs.aggregation > 1 ? ` · aggregation ${obs.aggregation}` : ''}${obs.threshold != null ? ` · threshold ${obs.threshold}` : ''}${obs.address_resolution != null ? ` · address resolution ${obs.address_resolution}` : ''} · ${sampled ? 'sampled tick' : 'not a sampled tick'}`, ink: 'active', align: 'left' });
    P.push({ t: 'text', id: 'observation', x: 0.1, y: n + 0.9, text: `observability ${ins.observability ?? 'full observation'}${ins.limiting.length ? ` (${ins.limiting.join(', ')})` : ''}`, ink: ins.observability && ins.observability !== 'SUFFICIENT' ? 'cut' : 'active', align: 'left' });
  }

  // the configurations
  for (const [nm, p] of [['A1', a1], ['A2', a2]] as const) {
    const present = f[nm].present;
    P.push({ t: 'rect', id: `entity.${nm}`, x0: p[0] - 0.42, y0: p[1] - 0.42, x1: p[0] + 0.42, y1: p[1] + 0.42, style: present ? 'solid' : 'dot', w: 1.6, ink: present ? 'ink' : 'mute' }, { t: 'text', id: `entity.${nm}`, x: p[0], y: p[1] + 0.28, text: nm, ink: present ? 'ink' : 'mute', align: 'center' });
  }

  // operational paths
  const mid: [number, number] = [(a1[0] + a2[0]) / 2, (a1[1] + a2[1]) / 2 + 0.9];
  const path = (id: PathId, pts: Array<[number, number]>, base: Ink, label: string) => {
    if (!on(`path.${id}`)) return;
    const s = ps[id];
    P.push({ t: 'poly', id: `path.${id}`, pts, style: style(s), w: s === 'active' ? 1.6 : 1.2, ink: ink(s, base), arrow: true }, { t: 'text', id: `path.${id}`, x: pts[Math.floor(pts.length / 2)][0], y: pts[Math.floor(pts.length / 2)][1] - 0.22, text: `${label} ${s}`, ink: ink(s, base), align: 'center' });
    if (s === 'cut') P.push({ t: 'cross', id: `path.${id}`, x: (pts[0][0] + pts[pts.length - 1][0]) / 2, y: (pts[0][1] + pts[pts.length - 1][1]) / 2, ink: 'cut' });
  };
  path('resource', [[0.2, a1[1] + 1.1], [(0.2 + a1[0]) / 2, a1[1] + 1.4], [a1[0], a1[1] + 0.5]], 'green', 'resource');
  path('coupling', [[a1[0] + 0.45, a1[1]], [(a1[0] + a2[0]) / 2, a1[1] - 0.15], [a2[0] - 0.45, a2[1]]], 'active', 'coupling');
  path('history_access', [[a1[0] - 0.3, a1[1] - 0.45], [a1[0] - 0.9, a1[1] - 1.3], [a1[0] + 0.3, a1[1] - 1.3], [a1[0] + 0.1, a1[1] - 0.45]], 'violet', 'history');
  path('observation', [[n / 2, -0.15], [(reg[0] + reg[2] + 1) / 2, 0.8]], 'active', 'observation');
  path('recovery', [[a2[0] + 0.3, a2[1] + 0.5], [mid[0] + 1.5, mid[1] + 1.1], [a1[0] + 0.4, a1[1] + 0.5]], 'green', 'recovery');

  // interventions: flags at the cells they name; the others in a strip under the map
  if (on('interventions')) {
    let strip = 0;
    for (const iv of rec.intervention_log) {
      if (iv.tick > t) continue;
      const inj = iv.inject as { x: number; y: number; amount: number } | undefined, label = `t${iv.tick} ${iv.op}${iv.target ? ' ' + String(iv.target) : ''}`;
      if (inj) P.push({ t: 'flag', id: 'interventions', x: inj.x + 0.5, y: inj.y + 0.5, text: `t${iv.tick} pulse ${inj.amount}`, ink: 'green' });
      else if (iv.op === 'ADDRESS' && typeof iv.x === 'number') P.push({ t: 'flag', id: 'interventions', x: (iv.x as number) + 0.5, y: (iv.y as number) + 0.5, text: `t${iv.tick} ${String(iv.address_mode)} → (${iv.x},${iv.y})`, ink: 'violet' });
      else P.push({ t: 'text', id: 'interventions', x: 0.1, y: n + 1.9 + 0.8 * strip++, text: `${label}${iv.address_mode ? ' ' + String(iv.address_mode) : ''} → ${affected(iv)}`, ink: iv.tick === t ? 'cut' : 'ink', align: 'left' });
    }
  }
  return { n, prims: P, summary: { tick: String(t), operational: ins.operational, observed: String(ins.observed ?? 'full observation'), observability: String(ins.observability ?? 'full observation'), xenobody: ins.boundary.open.length ? `open: ${ins.boundary.open.join(', ')}` : 'closed' } };
}

/** The path or component an intervention names, in words. */
export function affected(iv: MeosRecord['intervention_log'][number]): string {
  const tgt = String(iv.target ?? '');
  if (iv.op === 'ADDRESS') return `Address Domain of ${tgt}`;
  if (iv.op === 'CHANGE_BOUNDARY') return `Address Domain boundary (arena radius ${String(iv.arena_radius)})`;
  if (tgt === 'interaction_channel') return 'coupling path';
  if (tgt === 'feedback' || tgt === 'resource_renewal') return 'resource and recovery paths';
  if (tgt === 'history' || iv.op === 'DISABLE_HISTORY') return 'history-access path';
  if (tgt.startsWith('sensor')) return 'observation path';
  if (iv.op === 'ALTER_RESOURCE') return 'resource and recovery paths';
  if (iv.op === 'ALTER_SSS') return 'SSS (all paths: scale, size and speed)';
  return tgt || iv.op;
}

export { PATH_IDS };
