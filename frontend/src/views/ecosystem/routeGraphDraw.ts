// Draws a route graph (routeGraph.ts) on a 2-D canvas in the technical sheet's ink-on-paper style. Every line is an edge of the graph, and every edge was derived from the record, the saved
// library and the path definitions: nothing is drawn that they do not contain.
import type { EdgeKind, GraphEdge, RouteGraph } from './routeGraph';

export type RouteToggle = 'active' | 'dormant' | 'failed' | 'fallback' | 'adaptive' | 'rejected' | 'reconfiguration' | 'mfs' | 'address' | 'history' | 'm2' | 'resource';
export const ROUTE_TOGGLES: Array<{ id: RouteToggle; label: string; what: string }> = [
  { id: 'active', label: 'active operational path', what: 'paths made of enabled components (solid blue)' },
  { id: 'dormant', label: 'dormant path', what: 'paths that need an installed component that is not in use (grey dashed)' },
  { id: 'failed', label: 'failed path', what: 'paths with a removed or isolated component (red dotted, crossed)' },
  { id: 'fallback', label: 'fixed fallback route', what: 'paths the fixed M2 fallback switched on (green, thick)' },
  { id: 'adaptive', label: 'adaptive route', what: 'paths the adaptive controller switched on (violet, dash-dot)' },
  { id: 'rejected', label: 'rejected candidate', what: 'candidate retaining sets that failed the search criterion or validation: dotted outline, never an MFS' },
  { id: 'reconfiguration', label: 'transitions between MFS', what: 'arrows between MFS, labelled with tick and cost (from the controller log)' },
  { id: 'mfs', label: 'MFS boundary', what: 'the components of the current MFS (solid) and of the alternatives (faint)' },
  { id: 'address', label: 'Address path', what: 'the address path (A1, A2)' },
  { id: 'history', label: 'history path', what: 'the history-access path' },
  { id: 'm2', label: 'M2 path', what: 'the M2 path (the tap)' },
  { id: 'resource', label: 'resource path', what: 'the resource path' },
];
const INK = '#15171a', ACTIVE = '#0b4a8f', CUT = '#a3261b', MUTE = '#9a9da3', GREEN = '#2f6f4f', VIOLET = '#6b3fa0', PAPER = '#f4f4f1';
const PATH_TOGGLE: Record<string, RouteToggle> = { address: 'address', history_access: 'history', m2: 'm2', resource: 'resource' };

export function visibleEdge(e: GraphEdge, on: Set<RouteToggle>): boolean {
  if (e.kind === 'reconfiguration') return on.has('reconfiguration');
  if (e.kind === 'membership') return on.has('mfs');
  if (e.kind === 'candidate') return on.has('rejected');
  if (e.state === 'absent') return false;
  if (e.path && PATH_TOGGLE[e.path] && !on.has(PATH_TOGGLE[e.path])) return false;
  return on.has(e.state as RouteToggle);
}

export function drawRouteGraph(g: CanvasRenderingContext2D, graph: RouteGraph, W: number, H: number, on: Set<RouteToggle>): void {
  const px = (x: number) => 50 + x * (W - 100), py = (y: number) => 30 + y * (H - 70);
  const pos = new Map(graph.nodes.map((n) => [n.id, [px(n.x), py(n.y)] as [number, number]]));
  g.save(); g.fillStyle = PAPER; g.fillRect(0, 0, W, H); g.textBaseline = 'middle'; g.lineCap = 'round';
  const edge = (e: GraphEdge) => {
    const a = pos.get(e.from), b = pos.get(e.to);
    if (!a || !b) return;
    const kind: EdgeKind = e.kind;
    g.beginPath();
    if (e.from === e.to) { g.ellipse(a[0], a[1] - 26, 16, 22, 0, 0, Math.PI * 2); }
    else if (kind === 'path') { const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2 - 38 - Math.abs(a[0] - b[0]) * 0.12; g.moveTo(a[0], a[1] - 12); g.quadraticCurveTo(mx, my, b[0], b[1] - 12); }
    else { g.moveTo(a[0], a[1] + (kind === 'membership' || kind === 'candidate' ? 12 : 0)); g.lineTo(b[0], b[1] - (kind === 'membership' || kind === 'candidate' ? 12 : 0)); }
    if (kind === 'path') {
      g.setLineDash(e.state === 'dormant' ? [7, 4] : e.state === 'failed' ? [1.5, 4] : e.state === 'adaptive' ? [9, 3, 2, 3] : []);
      g.strokeStyle = e.state === 'failed' ? CUT : e.state === 'dormant' ? MUTE : e.state === 'fallback' ? GREEN : e.state === 'adaptive' ? VIOLET : ACTIVE; g.lineWidth = e.state === 'fallback' ? 3.4 : e.state === 'adaptive' ? 3 : e.state === 'active' ? 2 : 1.4;
    } else if (kind === 'candidate') { g.setLineDash([1.5, 3.5]); g.strokeStyle = CUT; g.lineWidth = 0.9; g.globalAlpha = 0.7; }
    else if (kind === 'reconfiguration') { g.setLineDash([]); g.strokeStyle = GREEN; g.lineWidth = 2.2; }
    else { g.setLineDash(e.state === 'active' ? [] : [2, 4]); g.strokeStyle = e.state === 'active' ? INK : MUTE; g.lineWidth = e.state === 'active' ? 1 : 0.7; g.globalAlpha = e.state === 'active' ? 0.55 : 0.4; }
    g.stroke(); g.setLineDash([]); g.globalAlpha = 1;
    if (kind === 'path' && e.state === 'failed' && e.from !== e.to) { const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2 - 28 - Math.abs(a[0] - b[0]) * 0.06; g.strokeStyle = CUT; g.lineWidth = 2; g.beginPath(); g.moveTo(mx - 5, my - 5); g.lineTo(mx + 5, my + 5); g.moveTo(mx + 5, my - 5); g.lineTo(mx - 5, my + 5); g.stroke(); }
    if (kind === 'reconfiguration') { g.fillStyle = GREEN; g.font = '10px ui-monospace, Menlo, monospace'; g.textAlign = 'center'; g.fillText(e.label ?? '', (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 8); g.beginPath(); g.moveTo(b[0], b[1] + 6); g.lineTo(b[0] - 6, b[1] + 16); g.lineTo(b[0] + 6, b[1] + 16); g.closePath(); g.fill(); }
  };
  for (const e of graph.edges.filter((x) => (x.kind === 'membership' || x.kind === 'candidate') && visibleEdge(x, on))) edge(e);
  for (const e of graph.edges.filter((x) => x.kind !== 'membership' && x.kind !== 'candidate' && visibleEdge(x, on))) edge(e);
  g.font = '10px ui-monospace, Menlo, monospace'; g.textAlign = 'center';
  for (const n of graph.nodes) {
    if (n.kind === 'candidate' && !on.has('rejected')) continue;
    const [x, y] = pos.get(n.id) as [number, number], w = Math.max(24, n.label.length * 6 + 12);
    const col = n.state === 'failed' || n.state === 'rejected' ? CUT : n.state === 'enabled' ? ACTIVE : n.state === 'dormant' ? MUTE : '#c9c9c4';
    g.fillStyle = PAPER; g.strokeStyle = col; g.lineWidth = n.state === 'enabled' ? 2 : 1.1; g.setLineDash(n.state === 'dormant' ? [4, 3] : n.state === 'rejected' ? [1.5, 3] : []);
    g.beginPath(); g.roundRect(x - w / 2, y - 11, w, 22, n.kind === 'component' ? 11 : 3); g.fill(); g.stroke(); g.setLineDash([]);
    g.fillStyle = col; g.fillText(n.label, x, y + 0.5);
    if (n.kind === 'component' && n.state === 'failed') { g.strokeStyle = CUT; g.lineWidth = 1.6; g.beginPath(); g.moveTo(x - w / 2, y + 11); g.lineTo(x + w / 2, y - 11); g.stroke(); }
  }
  g.fillStyle = INK; g.textAlign = 'left'; g.font = '10px ui-monospace, Menlo, monospace'; g.fillText('MFS (library, saved experiment F)', 8, 12); g.fillText('components (state read from the record at the playhead)', 8, H - 10);
  g.restore();
}
