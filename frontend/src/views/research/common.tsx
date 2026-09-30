import { useEffect, useState } from 'react';
import { api } from '../../api/client';

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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useExperiment<T = any>(name: string): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.experiment<T>(name).then(setData).catch((e) => setError(String(e)));
  }, [name]);
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
