// XENO ECOSYSTEM — pure helpers that shape the second-stage experiment tables for display. They reformat what the engine returned and add no result.
import type { Json } from './meosApi';

const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const obj = (x: unknown): Record<string, unknown> => (x && typeof x === 'object' ? (x as Record<string, unknown>) : {});

export const fmt = (x: unknown, d = 2): string => (typeof x === 'number' && Number.isFinite(x) ? x.toFixed(d) : x == null ? '-' : String(x));
/** ``{mean, std}`` as ``mean±std``; a missing mean (no collapse, nothing to average) is a dash. */
export function stat(x: unknown, d = 2): string {
  const s = obj(x);
  return typeof s.mean === 'number' ? `${s.mean.toFixed(d)}±${typeof s.std === 'number' ? s.std.toFixed(d) : '?'}` : '-';
}
export function groupBy<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) (out[key(it)] ??= []).push(it);
  return out;
}

export const NECESSITY_CODE: Record<string, string> = {
  'history necessary': 'H', 'persists without history': 'P', 'collapses either way': 'X', 'history reversed (persists only without)': 'R', 'seed-dependent': '?',
};
export function necessityGrid(r: Json): { capacities: number[]; rows: Array<{ charge: number; cells: Array<{ class: string; code: string }> }>; counts: Record<string, number> } {
  const axes = obj(r.axes), charges = arr(axes.charge) as number[], capacities = arr(axes.capacity) as number[];
  const cells = arr(r.cells).map(obj);
  const counts: Record<string, number> = {};
  for (const c of cells) counts[String(c.class)] = (counts[String(c.class)] ?? 0) + 1;
  const rows = charges.map((charge) => ({
    charge,
    cells: capacities.map((cap) => {
      const c = cells.find((x) => x.charge === charge && x.capacity === cap);
      const cls = c ? String(c.class) : 'not run';
      return { class: cls, code: NECESSITY_CODE[cls] ?? '·' };
    }),
  }));
  return { capacities, rows, counts };
}

/** The recovery sweep's regions as contiguous runs of pulse amounts (so a non-monotone response shows as separated runs of the same region). */
export function regionRuns(r: Json): Array<{ region: string; amounts: number[] }> {
  const out: Array<{ region: string; amounts: number[] }> = [];
  for (const row of arr(r.rows).map(obj)) {
    const region = String(row.region), a = Number(row.amount), last = out[out.length - 1];
    if (last && last.region === region) last.amounts.push(a); else out.push({ region, amounts: [a] });
  }
  return out;
}
