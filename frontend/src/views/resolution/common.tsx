// Shared helpers for the resolution-escalation views. Every number comes from results/resolution/summary.json,
// which is generated from the experiment result files (backend/xzr/experiments/escalation/summary.py).
import { useExperiment } from '../research/common';

/* eslint-disable @typescript-eslint/no-explicit-any */
export const RESOLUTIONS = ['node', 'local', 'meso', 'macro', 'global'] as const;
export const LETTER: Record<string, string> = { node: 'N', local: 'L', meso: 'm', macro: 'M', global: 'G' };
export const LABEL_COLOR: Record<string, string> = {
  'NON-REDUNDANT': '#e6e6ea', 'HIDDEN AT COARSE RESOLUTION': '#a0c8ff', UNRESOLVED: '#ffbe5a', REDUNDANT: '#6f6f78',
  TRANSIENT: '#c9a0ff', 'TIME-WINDOW-DEPENDENT': '#9fe0b4', 'TOPOLOGY-DEPENDENT': '#9fe0b4', 'MEMORY-DEPENDENT': '#9fe0b4',
  'SCALE-DEPENDENT': '#9fe0b4', 'REGIME-DEPENDENT': '#9fe0b4',
};
export const ABBR: Record<string, string> = {
  'NON-REDUNDANT': 'NR', 'HIDDEN AT COARSE RESOLUTION': 'HID', UNRESOLVED: 'UNR', REDUNDANT: 'RED',
};
export const STATUS_COLOR: Record<string, string> = { DETECTED: '#e6e6ea', EQUIVALENT: '#3c3c44', UNRESOLVED: '#8a6a2e' };

export function Label({ s }: { s: string }) {
  const c = LABEL_COLOR[s] ?? '#8a8a92';
  return <span className="status-chip mono" style={{ borderColor: c, color: c }}>{s}</span>;
}

export function Labels({ ls }: { ls: string[] }) {
  return <span className="chips">{ls.map((l) => <Label key={l} s={l} />)}</span>;
}

/** exact → node → local → meso → macro → global: one cell per resolution, coloured by status. */
export function Strip({ row }: { row: any }) {
  const exact = row.exact_identical_share >= 1 ? 'identical' : 'differs';
  return (
    <span className="strip mono" title={`exact ${exact} · ` + RESOLUTIONS.map((r) =>
      `${r} ${row.status[r]} (±${row.ci_half?.[r] ?? '?'})`).join(' · ')}>
      <i style={{ background: exact === 'identical' ? '#3c3c44' : '#e6e6ea' }}>x</i>
      {RESOLUTIONS.map((r) => <i key={r} style={{ background: STATUS_COLOR[row.status[r]] ?? '#222' }}>{LETTER[r]}</i>)}
    </span>
  );
}

/** The resolution summary, in the sections the view reads (`sections`: dotted section paths; static mirror only). */
export function useSummary(sections: string[]) {
  return useExperiment<any>('resolution-summary', { include: sections });
}

export function MissingSummary({ error, loaded = false, study = '' }: { error: string | null; loaded?: boolean; study?: string }) {
  if (loaded) {  // the summary exists but this study has no result file yet
    return (
      <div className="panel-view dim">No results for {study || 'this study'} yet. Run it, then regenerate the summary:
        <pre className="mono">cd backend && python experiments/run_escalation.py {study || '<study>'}{'\n'}python -m xzr.experiments.escalation.summary</pre></div>
    );
  }
  return (
    <div className="panel-view dim">
      {error ? <>No <span className="mono">results/resolution/summary.json</span> yet. Run the experiments, then:
        <pre className="mono">make experiments-escalation{'\n'}python -m xzr.experiments.escalation.summary</pre></> : 'loading…'}
    </div>
  );
}

export const pct = (x: number | null | undefined, d = 1) => (x === null || x === undefined ? '—' : `${(100 * x).toFixed(d)}%`);
export const cellKey = (r: any) => `${r.condition}|${r.comparison}`;
