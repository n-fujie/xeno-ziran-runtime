import type { ReactNode } from 'react';

/* eslint-disable @typescript-eslint/no-explicit-any */
export const fmt = (x: any, d = 3): string => {
  if (x === null || x === undefined || (typeof x === 'number' && !Number.isFinite(x))) return '—';
  if (typeof x !== 'number') return String(x);
  return Math.abs(x) >= 1e4 ? x.toFixed(0) : Number(x.toPrecision(d)).toString();
};

const GREY: Record<string, string> = {
  DETECTED: '#ececf0', EQUIVALENT: '#a6a6ae', UNRESOLVED: '#7a7a82', IDENTICAL: '#56565e', 'NOT MEASURED': '#45454c',
  ok: '#9fe0b4', failed: '#ff7a6a', timeout: '#ffbe5a', finished: '#9fe0b4', running: '#a0c8ff', stopped: '#ffbe5a', created: '#8a8a92',
};

export function Chip({ s }: { s: string | undefined | null }) {
  const c = GREY[s ?? ''] ?? '#8a8a92';
  return <span className="status-chip mono" style={{ borderColor: c, color: c, borderStyle: s === 'UNRESOLVED' ? 'dashed' : 'solid' }}>{s ?? '—'}</span>;
}

/** The banner every functional-check output carries: these numbers are not evidence. */
export function ModeBanner({ mode }: { mode: string | undefined }) {
  if (mode === 'functional') {
    return <div className="study-banner" role="note"><b>Functional check</b> — a software verification on a reserved seed range with a small
      sample. These numbers are not evidence and must not be reported as results.</div>;
  }
  if (mode === 'exploratory') return <div className="study-banner soft" role="note"><b>Exploratory</b> — nothing is pre-registered; results are labelled exploratory.</div>;
  return null;
}

export function Section({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return <section className="study-section"><h4>{title}</h4>{note && <p className="small dim">{note}</p>}{children}</section>;
}

export function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="study-table"><table><thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table></div>
  );
}
