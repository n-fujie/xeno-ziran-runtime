import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { makeLoader, type SectionIndex, type Select } from '../../api/results';

export const STATUS_COLOR: Record<string, string> = {
  'NON-REDUNDANT': '#e6e6ea', REDUCIBLE: '#a0c8ff', DERIVED: '#9fe0b4', 'DESCRIPTIVE ONLY': '#8a8a92',
  UNRESOLVED: '#ffbe5a', 'NOT RUN': '#55555e',
};

export function Status({ s }: { s: string }) {
  const key = Object.keys(STATUS_COLOR).find((k) => s.startsWith(k)) ?? 'NOT RUN';
  return <span className="status-chip mono" style={{ borderColor: STATUS_COLOR[key], color: STATUS_COLOR[key] }}>{s}</span>;
}

export function Yes({ v, invert = false }: { v: boolean | null | undefined; invert?: boolean }) {
  if (v === null || v === undefined) return <span className="dim">—</span>;
  const on = invert ? !v : v;
  return <span className={on ? 'up' : 'dim'}>{v ? 'yes' : 'no'}</span>;
}

// The static mirror's result files never change: each is read once per page load there, and a large file is read
// only in the sections the view renders (see api/results.ts; the 4.6 MB resolution summary feeds six views). With the
// local server a file can be regenerated, so every view load reads the whole file afresh.
const staticLoad = import.meta.env.VITE_STATIC === '1'
  ? makeLoader((url) => fetch(url).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status} ${url}`)))),
    JSON.parse(import.meta.env.VITE_SECTIONS || '{}') as SectionIndex)
  : null;

// Sections a view never reads, by file (the full file stays available as the download).
const DEFAULT_SELECT: Record<string, Select> = { reduction: { exclude: ['systematic.raw'] } };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useExperiment<T = any>(name: string, select?: Select): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sel = JSON.stringify(select ?? DEFAULT_SELECT[name] ?? null);
  useEffect(() => {
    const s = JSON.parse(sel) as Select | null;
    (staticLoad ? staticLoad<T>(name, s ?? undefined) : api.experiment<T>(name)).then(setData).catch((e) => setError(String(e)));
  }, [name, sel]);
  return { data, error };
}

export function Missing({ name, error }: { name: string; error: string | null }) {
  return (
    <div className="panel-view dim">
      {error ? <>No result file <span className="mono">{name}.json</span> yet. Run the experiment:
        <pre className="mono">{name === 'reduction' ? 'make experiments-reduction' : 'make experiments-reason'}</pre></> : 'loading…'}
    </div>
  );
}

export function Ratio({ r }: { r: number }) {
  // distance / tolerance: ≤ 1 within tolerance
  const c = r <= 1 ? `rgba(160,160,170,${0.15 + 0.5 * r})` : r < 3 ? '#ffbe5a' : '#ff5c48';
  return <span className="ratio" title={`distance / tolerance = ${r.toFixed(2)}`} style={{ background: c }} />;
}
