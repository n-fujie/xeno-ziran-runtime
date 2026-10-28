// Draws a research map spec (researchMap.ts) on a 2-D canvas context in the sheet's ink-on-paper style.
import type { Ink, LineStyle, MapSpec } from './researchMap';

export const INKS: Record<Ink, string> = { ink: '#15171a', active: '#0b4a8f', cut: '#a3261b', mute: '#9a9da3', green: '#2f6f4f', violet: '#6a4a8a' };
const DASH: Record<LineStyle, number[]> = { solid: [], dash: [7, 4], dashdot: [9, 3, 2, 3], dot: [1.5, 3.5] };

/** Draw ``spec`` into a ``W`` x ``H`` box of ``g`` (paper background included). Cell coordinates are mapped so that the arena fills the box with a margin for the text. */
export function drawResearchMap(g: CanvasRenderingContext2D, spec: MapSpec, W: number, H: number, paper = '#f4f4f1'): void {
  const top = 26, bottom = 78, left = 14, right = 14, sc = Math.min((W - left - right) / spec.n, (H - top - bottom) / spec.n);
  const X = (x: number) => left + x * sc, Y = (y: number) => top + y * sc;
  g.save(); g.fillStyle = paper; g.fillRect(0, 0, W, H); g.lineCap = 'round'; g.textBaseline = 'middle';
  for (const p of spec.prims) {
    g.setLineDash([]); g.globalAlpha = 1;
    if (p.t === 'poly') {
      g.strokeStyle = INKS[p.ink]; g.lineWidth = p.w; g.setLineDash(DASH[p.style]); g.globalAlpha = p.id === 'grid' ? 0.45 : 0.95; g.beginPath();
      p.pts.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y)))); g.stroke(); g.setLineDash([]);
      if (p.arrow && p.pts.length > 1) {
        const [x1, y1] = p.pts[p.pts.length - 2], [x2, y2] = p.pts[p.pts.length - 1], a = Math.atan2(Y(y2) - Y(y1), X(x2) - X(x1));
        g.fillStyle = INKS[p.ink]; g.beginPath(); g.moveTo(X(x2), Y(y2)); g.lineTo(X(x2) - 7 * Math.cos(a - 0.4), Y(y2) - 7 * Math.sin(a - 0.4)); g.lineTo(X(x2) - 7 * Math.cos(a + 0.4), Y(y2) - 7 * Math.sin(a + 0.4)); g.closePath(); g.fill();
      }
    } else if (p.t === 'rect') {
      g.strokeStyle = INKS[p.ink]; g.lineWidth = p.w; g.setLineDash(DASH[p.style]);
      if (p.hatch) { g.save(); g.beginPath(); g.rect(X(p.x0), Y(p.y0), (p.x1 - p.x0) * sc, (p.y1 - p.y0) * sc); g.clip(); g.lineWidth = 0.7; g.setLineDash([]); g.beginPath(); for (let k = -200; k < 400; k += 5) { g.moveTo(X(p.x0) + k, Y(p.y1)); g.lineTo(X(p.x0) + k + 200, Y(p.y0) - 0); } g.stroke(); g.restore(); g.setLineDash(DASH[p.style]); }
      g.strokeRect(X(p.x0), Y(p.y0), (p.x1 - p.x0) * sc, (p.y1 - p.y0) * sc); g.setLineDash([]);
    } else if (p.t === 'dots') {
      g.fillStyle = INKS[p.ink]; g.globalAlpha = 0.75; for (const [x, y] of p.pts) { g.beginPath(); g.arc(X(x), Y(y), 1.5, 0, Math.PI * 2); g.fill(); }
    } else if (p.t === 'cross') {
      g.strokeStyle = INKS[p.ink]; g.lineWidth = 2; g.beginPath(); g.moveTo(X(p.x) - 6, Y(p.y) - 6); g.lineTo(X(p.x) + 6, Y(p.y) + 6); g.moveTo(X(p.x) + 6, Y(p.y) - 6); g.lineTo(X(p.x) - 6, Y(p.y) + 6); g.stroke();
    } else if (p.t === 'text') {
      g.fillStyle = INKS[p.ink]; g.font = '10px ui-monospace, Menlo, monospace'; g.textAlign = p.align === 'center' ? 'center' : 'left'; g.fillText(p.text, p.align === 'center' ? X(p.x) : X(p.x), Y(p.y));
    } else if (p.t === 'flag') {
      g.strokeStyle = INKS[p.ink]; g.fillStyle = INKS[p.ink]; g.lineWidth = 1.2; g.beginPath(); g.moveTo(X(p.x), Y(p.y)); g.lineTo(X(p.x), Y(p.y) - 14); g.lineTo(X(p.x) + 8, Y(p.y) - 11); g.lineTo(X(p.x), Y(p.y) - 8); g.stroke(); g.beginPath(); g.arc(X(p.x), Y(p.y), 2, 0, Math.PI * 2); g.fill();
      g.font = '8px ui-monospace, Menlo, monospace'; g.textAlign = 'left'; g.fillText(p.text, X(p.x) + 10, Y(p.y) - 15);
    }
  }
  g.restore();
}
