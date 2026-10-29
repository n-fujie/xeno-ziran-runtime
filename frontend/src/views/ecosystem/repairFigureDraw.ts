// Draws the repair of a run on the technical sheet, in the ink-on-paper style of the route graph: the paths with their state, the stress, each repair action with its tick, magnitude and cost, and the resulting operational outcome. Every element is an event of the
// run (repair.ts / the server's repair block); a repair that did not happen is not drawn, and the repair site is drawn where the action acted, which need not be the damaged path.
import type { RepairBlock } from './meosApi';
import type { RepairState } from './repair';

const INK = '#15171a', CUT = '#a3261b', MUTE = '#9a9da3', GREEN = '#2f6f4f', VIOLET = '#6b3fa0', BLUE = '#0b4a8f', PAPER = '#f4f4f1';
export const REPAIR_PATHS = ['resource', 'coupling', 'history_access', 'observation', 'recovery', 'address', 'm2'] as const;
const NAME: Record<string, string> = { resource: 'resource path', coupling: 'coupling path', history_access: 'history path', observation: 'observation path', recovery: 'recovery path', address: 'Address path', m2: 'M2 path' };

export interface RepairFigureItem { kind: 'node' | 'stress' | 'action' | 'edge' | 'text'; id: string; label: string; state?: string; x: number; y: number; to?: string }
/** The items of the figure (a pure function, so the figure's content is tested without a canvas). */
export function repairFigureItems(rb: RepairBlock, st: RepairState): RepairFigureItem[] {
  const items: RepairFigureItem[] = [];
  REPAIR_PATHS.forEach((p, i) => items.push({ kind: 'node', id: p, label: NAME[p], state: st.paths[p] ?? 'intact', x: (i + 0.5) / REPAIR_PATHS.length, y: 0.48 }));
  const onset = rb.events.find((e) => e.kind === 'stress-onset');
  if (onset && st.damagedPath) { items.push({ kind: 'stress', id: 'stress', label: `${rb.label} @${onset.tick}`, x: (REPAIR_PATHS.indexOf(st.damagedPath as (typeof REPAIR_PATHS)[number]) + 0.5) / REPAIR_PATHS.length, y: 0.12, to: st.damagedPath }); }
  const acts = rb.events.filter((e) => e.kind === 'repair-action' && e.tick <= st.tick);
  acts.forEach((a, i) => {
    const c = rb.evaluation.costs.raw;
    items.push({ kind: 'action', id: `a${i}`, label: `${a.action} ${a.magnitude ?? ''}${a.duration ? ` for ${a.duration}` : ''} @${a.tick} [${a.klass === 'A' ? 'internal' : 'world'}]`, state: a.klass, x: (i + 0.5) / Math.max(1, acts.length), y: 0.86, to: a.path ?? undefined });
    if (i === 0) items.push({ kind: 'text', id: 'cost', label: `cost: switching ${c.switching}, energy ${c.energy_use}, collateral ${c.collateral}`, x: 0.02, y: 0.97 });
  });
  const h = rb.evaluation.horizons;
  items.push({ kind: 'text', id: 'result', label: `operational result: short ${h.short.outcome} · medium ${h.medium.outcome} · long ${h.long.outcome}`, x: 0.02, y: 0.02 });
  return items;
}

export function drawRepairFigure(g: CanvasRenderingContext2D, rb: RepairBlock, st: RepairState, W: number, H: number): void {
  const px = (x: number) => 20 + x * (W - 40), py = (y: number) => 14 + y * (H - 28);
  g.save(); g.fillStyle = PAPER; g.fillRect(0, 0, W, H); g.font = '10px ui-monospace, Menlo, monospace'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineCap = 'round';
  const items = repairFigureItems(rb, st);
  const pos = new Map(items.filter((i) => i.kind === 'node').map((i) => [i.id, [px(i.x), py(i.y)] as [number, number]]));
  for (const it of items) {
    if (it.kind === 'stress' || it.kind === 'action') {
      const target = it.to ? pos.get(it.to) : undefined;
      const [x, y] = [px(it.x), py(it.y)];
      g.strokeStyle = it.kind === 'stress' ? CUT : it.state === 'A' ? BLUE : VIOLET; g.lineWidth = 1.6;
      if (target) { g.setLineDash(it.kind === 'stress' ? [1.5, 3] : []); g.beginPath(); g.moveTo(x, y + (it.kind === 'stress' ? 10 : -10)); g.lineTo(target[0], target[1] + (it.kind === 'stress' ? -12 : 12)); g.stroke(); g.setLineDash([]); }
      const w = Math.min(W / 3, it.label.length * 6 + 12);
      g.fillStyle = PAPER; g.beginPath(); g.roundRect(x - w / 2, y - 10, w, 20, 3); g.fill(); g.stroke(); g.fillStyle = it.kind === 'stress' ? CUT : it.state === 'A' ? BLUE : VIOLET; g.fillText(it.label, x, y + 0.5, w - 6);
    }
  }
  for (const it of items) {
    if (it.kind !== 'node') continue;
    const [x, y] = pos.get(it.id) as [number, number], w = 104;
    const col = it.state === 'damaged' || it.state === 'failed' ? CUT : it.state === 'repaired' ? GREEN : it.state === 'bypass' ? GREEN : it.state === 'repair-active' ? VIOLET : it.state === 'intact' ? MUTE : INK;
    g.strokeStyle = col; g.lineWidth = it.state === 'intact' ? 1.1 : 2.2; g.setLineDash(it.state === 'bypass' ? [8, 3, 2, 3] : it.state === 'damaged' ? [1.5, 3] : []);
    g.fillStyle = PAPER; g.beginPath(); g.roundRect(x - w / 2, y - 14, w, 28, 11); g.fill(); g.stroke(); g.setLineDash([]);
    g.fillStyle = col; g.fillText(it.label, x, y - 3); g.fillText(it.state ?? '', x, y + 8);
    if (it.state === 'damaged' || it.state === 'failed') { g.strokeStyle = CUT; g.lineWidth = 1.6; g.beginPath(); g.moveTo(x - w / 2, y + 14); g.lineTo(x + w / 2, y - 14); g.stroke(); if (it.state === 'failed') { g.beginPath(); g.moveTo(x - w / 2, y - 14); g.lineTo(x + w / 2, y + 14); g.stroke(); } }
  }
  g.fillStyle = INK; g.textAlign = 'left';
  for (const it of items) if (it.kind === 'text') g.fillText(it.label, px(it.x), py(it.y));
  g.restore();
}
