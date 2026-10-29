// XENO ECOSYSTEM — deep links: a state of the view that can be written as a URL and restored from it. Pure functions (parse, format, plan), so that the restoration is tested without a browser.
//
//   seed=3                      the seed of the run
//   tick=165                    the playhead
//   mfs=MFS-F14-2               run the configuration of that saved MFS (its condition, only its retained components in place)
//   route=fixed:history lost    a controlled run: controller (none, fixed, adaptive, adaptive_shed, delayed, noisy) and scenario of experiment I   (``reconf`` is accepted as an alias)
//   experiment=F14              open the RESEARCH tab at that condition of experiment F
//   sssmap=MFS-F14-2            open the SSS map of that MFS
//   sss=1.2/1/1                 the SSS setting from tick 0
//   address=loss@100:A2         an Address Domain fault: mode@tick[:target[:x,y|fraction|delay]]  (reassign@100:A2:11,6, partial@100:A2:0.5, delayed@100:A2:11,6)
//   obs=interval:3,stride:2     the observation (interval, stride, window, region a.b.c.d, occluder a.b.c.d, threshold, resolution)
//   layer=route.fallback,mfs.current   the research-map layers   routelayers=active,failed   the route-graph toggles   (``maplayers`` is accepted as an alias of ``layer``)
//   cam=body   quality=balanced   the camera preset and the quality tier
import type { Intervention, Observation } from './meosApi';
import { FULL_OBSERVATION } from './meosApi';

export interface DeepLink {
  seed?: number; tick?: number; mfs?: string; route?: { controller: string; scenario: string }; experiment?: string; sssmap?: string; sss?: [number, number, number];
  address?: { mode: string; tick: number; target: string; x?: number; y?: number; fraction?: number; delay?: number }; obs?: Partial<Observation>; layers?: string[]; routelayers?: string[]; cam?: string; quality?: string;
}
const list = (v: string) => v.split('.').map(Number);
const num = (v: string | null): number | undefined => { if (v === null || v === '') return undefined; const n = Number(v); return Number.isFinite(n) ? n : undefined; };

export function parseObs(v: string | null): Partial<Observation> {
  const o: Partial<Observation> = {};
  for (const kv of (v ?? '').split(',').filter(Boolean)) {
    const [k, x] = kv.split(':');
    if (k === 'interval') o.sampling_interval = Number(x); else if (k === 'stride') o.spatial_stride = Number(x); else if (k === 'window') o.window = Number(x); else if (k === 'region') o.region = list(x);
    else if (k === 'occluder') o.occluder = list(x); else if (k === 'threshold') o.threshold = Number(x); else if (k === 'resolution') o.address_resolution = Number(x);
  }
  return o;
}
export function formatObs(o: Partial<Observation>): string {
  const p: string[] = [];
  if (o.sampling_interval !== undefined) p.push(`interval:${o.sampling_interval}`);
  if (o.spatial_stride !== undefined) p.push(`stride:${o.spatial_stride}`);
  if (o.window !== undefined) p.push(`window:${o.window}`);
  if (o.region) p.push(`region:${o.region.join('.')}`);
  if (o.occluder) p.push(`occluder:${o.occluder.join('.')}`);
  if (o.threshold !== undefined && o.threshold !== null) p.push(`threshold:${o.threshold}`);
  if (o.address_resolution !== undefined && o.address_resolution !== null) p.push(`resolution:${o.address_resolution}`);
  return p.join(',');
}

export function parseDeepLink(search: string): DeepLink {
  const q = new URLSearchParams(search), d: DeepLink = {};
  const seed = num(q.get('seed')), tick = num(q.get('tick'));
  if (seed !== undefined) d.seed = seed;
  if (tick !== undefined) d.tick = tick;
  if (q.get('mfs')) d.mfs = q.get('mfs')!;
  const route = q.get('route') ?? q.get('reconf');
  if (route && (route.includes(':') || route.includes('|'))) { const i = route.search(/[:|]/); d.route = { controller: route.slice(0, i), scenario: route.slice(i + 1) }; }
  if (q.get('experiment')) d.experiment = q.get('experiment')!;
  if (q.get('sssmap')) d.sssmap = q.get('sssmap')!;
  const sss = (q.get('sss') ?? '').split('/').map(Number);
  if (sss.length === 3 && sss.every((x) => x >= 0.25 && x <= 4)) d.sss = [sss[0], sss[1], sss[2]];
  const a = q.get('address');
  if (a) {
    const m = /^([a-z]+)@(\d+)(?::([A-Za-z0-9]+))?(?::(.+))?$/.exec(a);
    if (m) {
      const extra = m[4] ?? '', ad: NonNullable<DeepLink['address']> = { mode: m[1], tick: Number(m[2]), target: m[3] ?? 'A2' };
      if (extra.includes(',')) { const [x, y] = extra.split(',').map(Number); ad.x = x; ad.y = y; } else if (extra) { if (m[1] === 'delayed') ad.delay = Number(extra); else ad.fraction = Number(extra); }
      d.address = ad;
    }
  }
  const obs = parseObs(q.get('obs'));
  if (Object.keys(obs).length) d.obs = obs;
  const layers = q.get('layer') ?? q.get('maplayers'), rl = q.get('routelayers');
  if (layers) d.layers = layers.split(',').filter(Boolean);
  if (rl) d.routelayers = rl.split(',').filter(Boolean);
  if (q.get('cam')) d.cam = q.get('cam')!;
  if (q.get('quality')) d.quality = q.get('quality')!;
  return d;
}

export function formatDeepLink(d: DeepLink): string {
  const q: string[] = [];
  const put = (k: string, v: string | number | undefined) => { if (v !== undefined && v !== '') q.push(`${k}=${encodeURIComponent(String(v)).replace(/%2C/g, ',').replace(/%2F/g, '/').replace(/%40/g, '@').replace(/%3A/g, ':')}`); };
  put('seed', d.seed); put('tick', d.tick); put('mfs', d.mfs);
  if (d.route) put('route', `${d.route.controller}:${d.route.scenario}`);
  put('experiment', d.experiment); put('sssmap', d.sssmap);
  if (d.sss) put('sss', d.sss.join('/'));
  if (d.address) { const a = d.address; put('address', `${a.mode}@${a.tick}:${a.target}${a.x !== undefined ? `:${a.x},${a.y}` : a.delay !== undefined ? `:${a.delay}` : a.fraction !== undefined ? `:${a.fraction}` : ''}`); }
  if (d.obs) put('obs', formatObs(d.obs));
  if (d.layers) put('layer', d.layers.join(','));
  if (d.routelayers) put('routelayers', d.routelayers.join(','));
  put('cam', d.cam); put('quality', d.quality);
  return q.join('&');
}

export interface Plan {
  seed: number; tick: number; obs: Observation; interventions: Intervention[]; run: { kind: 'plain' } | { kind: 'mfs'; mfs: string } | { kind: 'route'; controller: string; scenario: string };
  experiment: string | null; sssmap: string | null; layers: string[] | null; routelayers: string[] | null; cam: string | null; quality: string | null; tab: 'research' | null;
}
/** What the view starts from, given a deep link: the same link always gives the same plan. */
export function deepLinkPlan(d: DeepLink): Plan {
  const iv: Intervention[] = [];
  if (d.sss) iv.push({ tick: 0, op: 'ALTER_SSS', scale: d.sss[0], size: d.sss[1], speed: d.sss[2] });
  if (d.address) { const a = d.address; iv.push({ tick: a.tick, op: 'ADDRESS', target: a.target, mode: a.mode, ...(a.x !== undefined ? { x: a.x, y: a.y } : {}), ...(a.fraction !== undefined ? { fraction: a.fraction } : {}), ...(a.delay !== undefined ? { delay: a.delay } : {}) }); }
  return {
    seed: d.seed ?? 1, tick: Math.max(0, d.tick ?? 0), obs: { ...FULL_OBSERVATION, ...(d.obs ?? {}) }, interventions: iv,
    run: d.mfs ? { kind: 'mfs', mfs: d.mfs } : d.route ? { kind: 'route', ...d.route } : { kind: 'plain' },
    experiment: d.experiment ?? null, sssmap: d.sssmap ?? null, layers: d.layers ?? null, routelayers: d.routelayers ?? null, cam: d.cam ?? null, quality: d.quality ?? null,
    tab: d.experiment || d.sssmap || d.mfs || d.route ? 'research' : null,
  };
}
