import { Fragment, useMemo, useState } from 'react';
import { ABBR, LABEL_COLOR, Labels, MissingSummary, RESOLUTIONS, Strip, pct, useSummary } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
const ORDER = ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'C~'];

function Table({ rows, refs, title }: { rows: any[]; refs?: Record<string, any>; title: string }) {
  const [factor, setFactor] = useState('all');
  const [open, setOpen] = useState<string | null>(null);
  const factors = useMemo(() => ['all', ...Array.from(new Set(rows.map((r) => r.factor)))], [rows]);
  const conds = useMemo(() => {
    const m = new Map<string, any[]>();
    for (const r of rows) if (factor === 'all' || r.factor === factor) m.set(r.condition, [...(m.get(r.condition) ?? []), r]);
    return [...m.entries()];
  }, [rows, factor]);
  const cols = ORDER.filter((k) => rows.some((r) => r.comparison === k));
  return (<>
    <h4>{title} <select value={factor} onChange={(e) => setFactor(e.target.value)}>{factors.map((f) => <option key={f}>{f}</option>)}</select></h4>
    <table className="list small matrix">
      <thead><tr><td>condition</td><td>n · steps</td><td title="reference C: share of checks with reasoning active · share collapsed (the rest: before reasoning, or never enabled)">active · collapsed</td>
        {cols.map((k) => <td key={k} className="mono">{k}</td>)}</tr></thead>
      <tbody>{conds.map(([cid, rs]) => {
        const byK = Object.fromEntries(rs.map((r) => [r.comparison, r]));
        const ref = refs?.[cid];
        const sel = rs.find((r) => `${cid}|${r.comparison}` === open);
        return (<Fragment key={cid}>
          <tr><td className="mono">{cid}</td><td className="mono dim">{rs[0].n.toLocaleString()} · {rs[0].horizon.toLocaleString()}</td>
            <td className="mono dim">{ref ? `${pct(ref.reasoning_share, 0)} · ${pct(ref.collapsed_share, 0)}` : '—'}</td>
            {cols.map((k) => {
              const r = byK[k];
              if (!r) return <td key={k} className="dim">·</td>;
              const c = LABEL_COLOR[r.primary] ?? '#888';
              return <td key={k} className="mono clickable-cell" style={{ color: c }} title={`${r.primary} — ${r.labels.join(', ')}`}
                onClick={() => setOpen(open === `${cid}|${k}` ? null : `${cid}|${k}`)}>{ABBR[r.primary] ?? r.primary}</td>;
            })}</tr>
          {sel && <tr><td colSpan={cols.length + 3}><div className="evidence small">
            <div><span className="mono">{sel.comparison}</span> vs C · <Labels ls={sel.labels} /> <Strip row={sel} /></div>
            <div className="mono dim">exact identical {pct(sel.exact_identical_share, 0)} of seeds · interventions differ at
              {' '}{pct(sel.intervention_checks_differing, 0)} of checks · seeds {sel.seeds}</div>
            <div className="mono dim">90% CI half-width (time-aggregated, relative): {RESOLUTIONS.map((r) => `${r} ${pct(sel.ci_half[r])}`).join(' · ')}</div>
            {sel.largest && <div className="mono">largest systematic effect: {sel.largest.resolution} · {sel.largest.feature}
              {' '}{pct(sel.largest.relative)} ({sel.largest.family}{sel.largest.segment !== undefined ? `, segment ${sel.largest.segment}` : ''})</div>}
            <div className="mono dim">time pattern: {RESOLUTIONS.map((r) => `${r} ${sel.pattern[r]}`).join(' · ')}</div>
          </div></td></tr>}
        </Fragment>);
      })}</tbody>
    </table>
  </>);
}

export default function ResolutionMatrixView() {
  const { data, error } = useSummary(['rules', 'matrix.rows', 'matrix.references', 'clusters', 'noise_control']);
  if (!data?.matrix) return <MissingSummary error={error} loaded={!!data} study="matrix" />;
  const nc = data.noise_control;
  return (
    <div className="panel-view research">
      <p className="dim small">Each cell compares a structural variant with the reference structure C in one condition
        ({data.matrix.rows[0]?.seeds ?? '?'} paired engine seeds; same world, stream and schedule). Classification per cell:
        {' '}<b>NR</b> systematic difference at meso / macro / global · <b>HID</b> trajectories differ, macro and global
        equivalent within {pct(data.rules.sesoi, 0)} · <b>UNR</b> coarse equivalence not established · <b>RED</b> bit-identical represented output (no difference detected within the represented and measured state; not a claim of absence).
        {' '}Family-wise α {data.rules.alpha_family} (split over resolutions and time families); practical threshold {pct(data.rules.practical, 0)}.
        {' '}Noise control (C under another stream): {nc.false_positive_conditions.length} of {nc.comparisons} conditions with a detection.</p>
      <p className="dim small">A no reasoning · B vocabulary · D one status · E no eligibility · F least fixpoint · G sticky conflicts ·
        {' '}H no records · I local records · J persistent records · K mixed rules · C~ noise control. Click a cell for the evidence.</p>
      <Table rows={data.matrix.rows} refs={data.matrix.references} title="Resolution matrix" />
      {data.clusters && <Table rows={data.clusters.rows} title="Interacting reasoning clusters" />}
    </div>
  );
}
