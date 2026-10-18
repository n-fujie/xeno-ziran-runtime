// SVG charts and tables of the XenoBody view. Every mark is drawn from values the runtime returned (live frames or a stored record).
import { useId } from 'react';
import type { Table } from '../../api/xbtro';
import { STATUS_COLOR, fmt } from './logic';

export interface Line { label: string; t: number[]; v: (number | null)[]; color?: string; dashed?: boolean; sd?: (number | null)[]; layer?: 'reference' | 'observation' | 'estimate' }

const PAL = ['#d8d8dc', '#5fd0e8', '#f0b45a', '#9fe08a', '#d08ae8', '#e88a8a', '#8ab4e8'];
const niceTicks = (lo: number, hi: number, n = 4): number[] => {
  if (!(hi > lo)) return [lo];
  const step0 = (hi - lo) / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 5, 10].map((k) => k * mag).find((s) => s >= step0) ?? step0;
  const out: number[] = [];
  for (let x = Math.ceil(lo / step) * step; x <= hi + 1e-12; x += step) out.push(Number(x.toPrecision(10)));
  return out;
};

export function LineChart({ lines, height = 150, title, yLabel, xLabel = 's', band }: {
  lines: Line[]; height?: number; title?: string; yLabel?: string; xLabel?: string; band?: [number, number];
}) {
  const id = useId();
  const W = 520; const H = height;
  const pad = { l: 46, r: 8, t: title ? 20 : 8, b: 20 };
  let t0 = Infinity; let t1 = -Infinity; let v0 = Infinity; let v1 = -Infinity;
  for (const s of lines) s.t.forEach((t, i) => {
    const v = s.v[i];
    if (v === null || v === undefined || !Number.isFinite(v)) return;
    const sd = s.sd?.[i] ?? 0;
    t0 = Math.min(t0, t); t1 = Math.max(t1, t); v0 = Math.min(v0, v - (sd || 0)); v1 = Math.max(v1, v + (sd || 0));
  });
  if (band) { v0 = Math.min(v0, band[0]); v1 = Math.max(v1, band[1]); }
  if (!Number.isFinite(t0)) return <div className="xb-chart empty small dim">{title ? `${title}: ` : ''}no data yet</div>;
  if (t1 === t0) t1 = t0 + 1;
  if (v1 === v0) { v0 -= 0.5; v1 += 0.5; }
  const X = (t: number) => pad.l + ((t - t0) / (t1 - t0)) * (W - pad.l - pad.r);
  const Y = (v: number) => H - pad.b - ((v - v0) / (v1 - v0)) * (H - pad.t - pad.b);
  const path = (s: Line) => {
    let d = ''; let pen = false;
    s.t.forEach((t, i) => {
      const v = s.v[i];
      if (v === null || v === undefined || !Number.isFinite(v)) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${X(t).toFixed(1)},${Y(v).toFixed(1)}`; pen = true;
    });
    return d;
  };
  const bandPath = (s: Line) => {
    if (!s.sd) return '';
    const up: string[] = []; const dn: string[] = [];
    s.t.forEach((t, i) => { const v = s.v[i]; const sd = s.sd?.[i]; if (v !== null && v !== undefined && sd !== null && sd !== undefined && Number.isFinite(v) && Number.isFinite(sd)) { up.push(`${X(t).toFixed(1)},${Y(v + sd).toFixed(1)}`); dn.unshift(`${X(t).toFixed(1)},${Y(v - sd).toFixed(1)}`); } });
    return up.length ? `M${up.join('L')}L${dn.join('L')}Z` : '';
  };
  return (
    <figure className="xb-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={`${id}-t`} preserveAspectRatio="none">
        <title id={`${id}-t`}>{title ?? 'chart'}{yLabel ? ` (${yLabel})` : ''}: {lines.map((l) => l.label).join(', ')}</title>
        {niceTicks(v0, v1, 3).map((v) => (
          <g key={v}><line x1={pad.l} x2={W - pad.r} y1={Y(v)} y2={Y(v)} className="grid" /><text x={pad.l - 4} y={Y(v) + 3} textAnchor="end" className="tick">{fmt(v, 2)}</text></g>
        ))}
        {niceTicks(t0, t1, 4).map((t) => <text key={t} x={X(t)} y={H - 5} textAnchor="middle" className="tick">{fmt(t, 3)}</text>)}
        {band && <rect x={pad.l} width={W - pad.l - pad.r} y={Y(band[1])} height={Math.max(0, Y(band[0]) - Y(band[1]))} className="band" />}
        {lines.map((s, k) => {
          const c = s.color ?? (s.layer === 'observation' ? '#5fd0e8' : s.layer === 'estimate' ? '#f0b45a' : PAL[k % PAL.length]);
          return <g key={s.label}>{s.sd && <path d={bandPath(s)} fill={c} opacity={0.16} />}<path d={path(s)} fill="none" stroke={c} strokeWidth={1.4} strokeDasharray={s.dashed ? '4 3' : undefined} vectorEffect="non-scaling-stroke" /></g>;
        })}
        {title && <text x={pad.l} y={12} className="ctitle">{title}{yLabel ? `  (${yLabel})` : ''}</text>}
        <text x={W - pad.r} y={H - 5} textAnchor="end" className="tick">{xLabel}</text>
      </svg>
      {lines.length > 1 && (
        <figcaption className="legend small">
          {lines.map((s, k) => (
            <span key={s.label}><i style={{ background: s.color ?? (s.layer === 'observation' ? '#5fd0e8' : s.layer === 'estimate' ? '#f0b45a' : PAL[k % PAL.length]) }} />{s.label}</span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}

/** A table of a record, as stored. Status words are coloured but always shown as words. */
export function DataTable({ table, limit = 400 }: { table: Table; limit?: number }) {
  const rows = table.rows.slice(0, limit);
  const statusCols = table.columns.map((c, i) => (/status|label|class|decision/i.test(c) ? i : -1)).filter((i) => i >= 0);
  return (
    <div className="xb-table-wrap">
      <table className="xb-table">
        <thead><tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((v, k) => {
              const word = typeof v === 'string' ? v : '';
              const color = statusCols.includes(k) ? STATUS_COLOR[word] ?? (word.startsWith('unobserved') ? STATUS_COLOR.unobserved : undefined) : undefined;
              return <td key={k} className={typeof v === 'number' ? 'num' : ''} style={color ? { color } : undefined}>{fmt(v)}</td>;
            })}</tr>
          ))}
        </tbody>
      </table>
      {table.rows.length > limit && <div className="small dim">showing {limit} of {table.rows.length} rows; the full table is in the export</div>}
    </div>
  );
}

/** rows × columns of status words (the Fragility Transfer matrix, the observability table). */
export function Matrix({ rows, cols, cell, rowLabel, colLabel }: {
  rows: string[]; cols: string[]; cell: (r: string, c: string) => { word: string; title?: string; value?: string } | undefined;
  rowLabel?: (r: string) => string; colLabel?: (c: string) => string;
}) {
  return (
    <div className="xb-table-wrap">
      <table className="xb-matrix">
        <thead><tr><th />{cols.map((c) => <th key={c} className="rot"><span>{colLabel?.(c) ?? c}</span></th>)}</tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}><th className="rowh">{rowLabel?.(r) ?? r}</th>
              {cols.map((c) => {
                const x = cell(r, c);
                const color = x ? STATUS_COLOR[x.word] ?? '#4a4a52' : '#222';
                return <td key={c} title={x ? `${x.word}${x.title ? ` — ${x.title}` : ''}` : 'not computed'} style={{ background: `${color}33`, borderColor: color }}>
                  <span style={{ color }}>{x ? (x.value ?? x.word.slice(0, 3)) : '·'}</span></td>;
              })}</tr>
          ))}
        </tbody>
      </table>
      <div className="small dim">Cells show the word as well as the colour: improved / worsened / no detectable effect. A cell is not a verdict on a principle; see the table for effect sizes.</div>
    </div>
  );
}

/** The coupling network of Experiment B: nodes are operation lines, edges are couplings classed by what supports them. */
export function CouplingNetwork({ nodes, edges }: {
  nodes: string[]; edges: { source: string; target: string; correlation: number; lag_s: number; predictive_gain: number; class: string; interventional: { intervention: string; d: number; p: number } | null }[];
}) {
  const W = 520; const H = 360; const cx = W / 2; const cy = H / 2; const R = Math.min(W, H) / 2 - 62;
  const pos = new Map(nodes.map((n, i) => [n, { x: cx + R * Math.cos((2 * Math.PI * i) / nodes.length - Math.PI / 2), y: cy + R * Math.sin((2 * Math.PI * i) / nodes.length - Math.PI / 2) }]));
  const style: Record<string, { c: string; dash?: string; w: number }> = {
    'interventionally-supported': { c: '#7fe0a0', w: 2.2 }, 'correlational-only': { c: '#e0c07f', dash: '5 3', w: 1.3 }, untested: { c: '#6e6e78', dash: '2 3', w: 1 },
  };
  return (
    <figure className="xb-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Coupling network between operation lines">
        <defs>{Object.entries(style).map(([k, s]) => <marker key={k} id={`ar-${k}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L8,4L0,8z" fill={s.c} /></marker>)}</defs>
        {edges.map((e, i) => {
          const a = pos.get(e.source); const b = pos.get(e.target);
          if (!a || !b) return null;
          const dx = b.x - a.x; const dy = b.y - a.y; const len = Math.hypot(dx, dy) || 1;
          const ox = (-dy / len) * 5; const oy = (dx / len) * 5;     // two directions of a pair do not overlap
          const s = style[e.class] ?? style.untested;
          return <line key={i} x1={a.x + ox + (dx / len) * 12} y1={a.y + oy + (dy / len) * 12} x2={b.x + ox - (dx / len) * 14} y2={b.y + oy - (dy / len) * 14}
            stroke={s.c} strokeWidth={s.w} strokeDasharray={s.dash} markerEnd={`url(#ar-${e.class in style ? e.class : 'untested'})`}>
            <title>{`${e.source} → ${e.target}: ${e.class}; r=${fmt(e.correlation, 2)} at lag ${fmt(e.lag_s, 2)} s; predictive gain ${fmt(e.predictive_gain, 2)}${e.interventional ? `; intervention ${e.interventional.intervention}: d=${fmt(e.interventional.d, 2)}, p=${fmt(e.interventional.p, 2)}` : '; no intervention targets the source'}`}</title></line>;
        })}
        {nodes.map((n) => {
          const p = pos.get(n)!;
          return <g key={n}><circle cx={p.x} cy={p.y} r={9} fill="#101015" stroke="#8a8a96" /><text x={p.x} y={p.y + (p.y < cy ? -14 : 22)} textAnchor="middle" className="tick">{n}</text></g>;
        })}
      </svg>
      <figcaption className="legend small">
        {Object.entries(style).map(([k, s]) => <span key={k}><i style={{ background: s.c }} />{k}</span>)}
      </figcaption>
    </figure>
  );
}
