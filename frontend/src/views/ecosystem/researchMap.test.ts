// The research map is a drawing spec computed from the record: three boundary kinds with three line types, five path layers whose line type is their state, an observation lattice and
// the interventions. Layers can be switched off; nothing on the map is typed in.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { MeosRecord, PathActivity } from './meosApi';
import { inspectAt } from './research';
import { ALL_MAP_LAYERS, buildResearchMap, MAP_LAYERS, type MapLayer, type Prim } from './researchMap';

const rec = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage2.json'), 'utf8')) as MeosRecord;
const paths = { coupling: { state_intervals: [{ from: 0, to: 99, state: 'active' }, { from: 100, to: 149, state: 'cut' }, { from: 150, to: 359, state: 'active' }] }, resource: { state_intervals: [{ from: 0, to: 359, state: 'active' }] } } as unknown as PathActivity;
const map = (tick: number, obs = {}, layers?: Set<MapLayer>) => buildResearchMap({ rec, tick, obs, inspect: inspectAt(rec, null, tick, paths), paths, markers: [], layers });
const byId = (s: Prim[], id: string) => s.filter((p) => p.id === id);

describe('the research map', () => {
  it('draws the three boundaries with three different line types', () => {
    const m = map(60, { region: [2, 3, 9, 9] }).prims;
    const x = byId(m, 'boundary.xenobody')[0] as Extract<Prim, { t: 'poly' }>, a = byId(m, 'boundary.address')[0] as Extract<Prim, { t: 'rect' }>, o = byId(m, 'boundary.observation')[0] as Extract<Prim, { t: 'rect' }>;
    expect([x.style, a.style, o.style]).toEqual(['solid', 'dashdot', 'dash']);
    expect(x.w).toBeGreaterThan(a.w);
    expect(o.x0).toBe(2); expect(o.x1).toBe(10);  // the observation region is the cells it names (inclusive)
  });
  it('opens a gap in the XenoBody boundary while the coupling is cut', () => {
    expect(byId(map(60).prims, 'boundary.xenobody').filter((p) => p.t === 'poly')).toHaveLength(1);
    const cut = byId(map(120).prims, 'boundary.xenobody').filter((p) => p.t === 'poly');
    expect(cut).toHaveLength(2); expect((cut[0] as Extract<Prim, { t: 'poly' }>).ink).toBe('cut');
  });
  it('draws a path with the line type of its state: solid active, dashed with a cross when cut, dotted when quiet', () => {
    const at = (t: number, id: string) => byId(map(t).prims, id);
    const c60 = at(60, 'path.coupling')[0] as Extract<Prim, { t: 'poly' }>, c120 = at(120, 'path.coupling'), q = byId(map(60).prims, 'path.recovery')[0] as Extract<Prim, { t: 'poly' }>;
    expect(c60.style).toBe('solid'); expect((c120[0] as Extract<Prim, { t: 'poly' }>).style).toBe('dash'); expect(c120.some((p) => p.t === 'cross')).toBe(true); expect(q.style).toBe('dot');
  });
  it('draws the sampling lattice at the observation stride, inside the region, and the occluder hatched', () => {
    const d = (m: Prim[]) => (byId(m, 'observation').find((p) => p.t === 'dots') as Extract<Prim, { t: 'dots' }>).pts.length;
    expect(d(map(60).prims)).toBe(14 * 14); expect(d(map(60, { spatial_stride: 2 }).prims)).toBe(7 * 7); expect(d(map(60, { region: [0, 0, 6, 6] }).prims)).toBe(49);
    const occ = byId(map(60, { occluder: [4, 4, 6, 6] }).prims, 'boundary.observation').find((p) => p.t === 'rect' && p.hatch);
    expect(occ).toBeTruthy();
  });
  it('shows the interval, the window and whether this tick is sampled', () => {
    const text = (m: Prim[]) => (byId(m, 'observation').filter((p) => p.t === 'text') as Array<Extract<Prim, { t: 'text' }>>).map((p) => p.text).join(' | ');
    expect(text(map(60, { sampling_interval: 3, window: 24 }).prims)).toContain('interval 3 · stride 1 · window 24 · sampled tick');
    expect(text(map(61, { sampling_interval: 3 }).prims)).toContain('not a sampled tick');
  });
  it('marks the Address Domain fault and the cell a stale address names', () => {
    const t = byId(map(210).prims, 'boundary.address').filter((p) => p.t === 'text') as Array<Extract<Prim, { t: 'text' }>>;
    expect(t.some((p) => p.text.includes('A2 address fragment'))).toBe(true);
    const fake = { ...rec, frames: rec.frames.map((f, i) => (i === 50 ? { ...f, address: { A1: { mode: 'stale', integrity: 0, at: [3, 6] as [number, number] }, A2: { mode: null, integrity: 1 } } } : f)) } as MeosRecord;
    const m = buildResearchMap({ rec: fake, tick: 50, obs: {}, inspect: inspectAt({ ...fake, frames: fake.frames.map((f, i) => (i === 50 ? { ...f, A1: { ...f.A1, x: 8, y: 6 } } : f)) } as MeosRecord, null, 50, paths), paths, markers: [] });
    expect(byId(m.prims, 'boundary.address').some((p) => p.t === 'poly' && p.style === 'dot' && p.arrow)).toBe(true);
  });
  it('draws the interventions that have happened by the tick, at their cells when they name one', () => {
    const flags = (t: number) => byId(map(t).prims, 'interventions').filter((p) => p.t === 'flag');
    expect(flags(100)).toHaveLength(0); expect(flags(155)).toHaveLength(1);
    expect(byId(map(155).prims, 'interventions').some((p) => p.t === 'text' && p.text.includes('coupling path'))).toBe(true);
  });
  it('removes a layer when it is switched off, and only that layer', () => {
    const off = new Set(ALL_MAP_LAYERS); off.delete('path.coupling');
    const m = map(120, {}, off).prims;
    expect(byId(m, 'path.coupling')).toHaveLength(0); expect(byId(m, 'path.resource').length).toBeGreaterThan(0); expect(byId(m, 'boundary.xenobody').length).toBeGreaterThan(0);
    expect(MAP_LAYERS.map((l) => l.id).sort()).toEqual([...ALL_MAP_LAYERS].sort());
  });
});
