// BODY / TOTAL OBSERVATION — what View A draws, as pure functions of the backend's data (no clock, no fetch, no state).
//
// A part of the drawing is coloured by the *provenance class of the records that refer to it*, and by nothing else. A part with no record is neutral and says so: not observed is
// not absent. The layout is a drawing (a concept layout stored in the preset, or a circle for a body with no concept layout): it is not an anatomical measurement.
import type { Coverage, DisplayClass, TargetState, TeooBody, TeooRecord, TeooVersion } from './bodyApi';

export interface ClassStyle { label: string; fill: string; stroke: string; dash: string; pattern: 'none' | 'hatch' | 'stripes' | 'dots'; legend: string }
// Each class differs in more than colour (dash, pattern), so the drawing reads without colour.
export const CLASS_STYLE: Record<DisplayClass, ClassStyle> = {
  measured: { label: 'measured', fill: '#e8e8ec', stroke: '#ffffff', dash: '', pattern: 'none', legend: 'has MEASURED records (real data, declared by their source)' },
  synthetic: { label: 'SYNTHETIC', fill: '#5a6b86', stroke: '#9bb0d0', dash: '', pattern: 'stripes', legend: 'has SYNTHETIC records (artificial functional-test data)' },
  estimated: { label: 'estimated', fill: '#2f2f35', stroke: '#c9a227', dash: '4 2', pattern: 'dots', legend: 'has only estimates or reconstructions (not observed)' },
  conceptual: { label: 'conceptual', fill: '#1b1b20', stroke: '#8a8a92', dash: '1 2', pattern: 'none', legend: 'drawn only (a concept, no data)' },
  unmeasured: { label: 'no record', fill: '#111114', stroke: '#45454c', dash: '', pattern: 'hatch', legend: 'no record refers to this part: not observed (which is not the same as absent)' },
  limited: { label: 'limited', fill: '#16161a', stroke: '#ff8a70', dash: '2 2', pattern: 'hatch', legend: 'records exist but no valid sample (an observation limit applies)' },
};
export const CLASS_ORDER: DisplayClass[] = ['measured', 'synthetic', 'estimated', 'conceptual', 'limited', 'unmeasured'];

export interface Layout { kind: 'concept' | 'circle'; viewBox: string; pos: Record<string, [number, number]> }

/** Concept coordinates stored in the preset when every component has them; otherwise the components are placed on a circle (the layout of a body that has no concept drawing). */
export function layoutOf(v: TeooVersion): Layout {
  const have = v.components.every((c) => c.attrs.concept_layout);
  if (have && v.components.length) {
    return { kind: 'concept', viewBox: '0 0 100 200', pos: Object.fromEntries(v.components.map((c) => [c.id, [c.attrs.concept_layout!.x, c.attrs.concept_layout!.y] as [number, number]])) };
  }
  const n = Math.max(1, v.components.length), pos: Record<string, [number, number]> = {};
  v.components.forEach((c, i) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    pos[c.id] = [Math.round((100 + 70 * Math.cos(a)) * 100) / 100, Math.round((100 + 70 * Math.sin(a)) * 100) / 100];
  });
  return { kind: 'circle', viewBox: '0 0 200 200', pos };
}

export const classOfRef = (ref: string, cov: Coverage | null): DisplayClass => cov?.by_ref[ref] ?? 'unmeasured';

export interface Mark { id: string; ref: string; shape: 'node' | 'joint' | 'link'; x: number; y: number; x2?: number; y2?: number; cls: DisplayClass; label: string; severed: boolean }

/** The marks of the drawing: one per component (a node), one per relation (a link, and a joint marker at its middle when it is a joint). */
export function marksOf(body: TeooBody, cov: Coverage | null): Mark[] {
  const v = body.versions[body.versions.length - 1], L = layoutOf(v), out: Mark[] = [];
  for (const r of v.relations) {
    const a = L.pos[r.source], b = L.pos[r.target];
    if (!a || !b) continue;
    out.push({ id: `l:${r.id}`, ref: r.id, shape: 'link', x: a[0], y: a[1], x2: b[0], y2: b[1], cls: 'conceptual', label: `${r.kind} ${r.id}`, severed: r.state === 'severed' });
    out.push({ id: `j:${r.id}`, ref: r.id, shape: 'joint', x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2, cls: classOfRef(r.id, cov), label: `${r.kind} ${r.id}`, severed: r.state === 'severed' });
  }
  for (const c of v.components) out.push({ id: `n:${c.id}`, ref: c.id, shape: 'node', x: L.pos[c.id][0], y: L.pos[c.id][1], cls: classOfRef(c.id, cov), label: c.label, severed: false });
  return out;
}

/** The synthetic banner is required whenever any record, or any ancestor of one, is SYNTHETIC. It is derived from the data; nothing a user does can switch it off. */
export const needsSyntheticBanner = (records: TeooRecord[]): boolean => records.some((r) => r.provenance === 'SYNTHETIC' || r.lineage_classes.includes('SYNTHETIC'));

export function describeTarget(t: TargetState): string[] {
  const out = [`state: ${t.state}`, `class: ${CLASS_STYLE[t.display_class].label}`];
  if (t.records.length) out.push(`records: ${t.records.join(', ')}`);
  if (t.classes?.length) out.push(`provenance: ${t.classes.join(' + ')}${t.mixed_classes ? ' (mixed: not merged into one reading)' : ''}`);
  const counts = Object.entries(t.counts).map(([k, v]) => `${k} ${v}`);
  if (counts.length) out.push(`samples: ${counts.join(', ')}`);
  if (t.causes.length) out.push(`observation limits: ${t.causes.join(' + ')}`);
  if (t.device_time_range_s) out.push(`device time: ${t.device_time_range_s[0]} – ${t.device_time_range_s[1]} s (unsynchronised unless a synchronisation record says otherwise)`);
  if (t.note) out.push(t.note);
  return out;
}

export const targetsOfRef = (cov: Coverage | null, ref: string): TargetState[] => Object.values(cov?.targets ?? {}).filter((t) => t.ref === ref);
