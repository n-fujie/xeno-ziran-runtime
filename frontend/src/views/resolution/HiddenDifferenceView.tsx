import { useState } from 'react';
import { Labels, MissingSummary, RESOLUTIONS, Strip, pct, useSummary } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function HiddenDifferenceView() {
  const { data, error } = useSummary(['structures', 'rules', 'matrix.rows', 'floor']);
  const [only, setOnly] = useState('HIDDEN AT COARSE RESOLUTION');
  if (!data?.structures) return <MissingSummary error={error} loaded={!!data} study="matrix" />;
  const rows: any[] = data.matrix.rows.filter((r: any) => r.comparison !== 'C~' && (only === 'all' || r.labels.includes(only)));
  return (
    <div className="panel-view research">
      <p className="dim small">A structural difference is <b>hidden at coarse resolution</b> when exact trajectories (or node /
        local summaries) differ but macro and global aggregates are equivalent within {pct(data.rules.sesoi, 0)} (90% confidence
        half-width of the paired difference). Hidden is not redundant: only bit-identical represented runs are labelled redundant (no difference detected within
        the represented and measured state under this comparison, not a claim of absence). When the coarse
        aggregates cannot be shown equivalent the cell is unresolved.</p>
      <h4>Per structural difference</h4>
      <table className="list small">
        <thead><tr><td>vs C</td><td>difference</td><td>conditions</td><td>visible (meso+)</td><td>visible at macro / global</td>
          <td>local only</td><td>hidden</td><td>unresolved</td><td>bit-identical</td><td>labels</td></tr></thead>
        <tbody>{Object.entries(data.structures).map(([k, s]: [string, any]) => (
          <tr key={k}><td className="mono">{k}</td><td className="dim">{s.description}</td><td className="mono">{s.conditions}</td>
            <td className="mono">{s.visible.length}</td><td className="mono">{s.visible_coarse.length}</td>
            <td className="mono">{s.locally_only.length}</td><td className="mono">{s.hidden.length}</td>
            <td className="mono">{s.unresolved.length}</td><td className="mono">{s.redundant.length}</td>
            <td><Labels ls={s.labels} /></td></tr>))}</tbody>
      </table>
      <h4>Resolution floor (noise control, median 90% CI half-width of time-aggregated summaries)</h4>
      <table className="list mono small">
        <thead><tr><td>design</td>{RESOLUTIONS.map((r) => <td key={r}>{r}</td>)}<td>conditions</td></tr></thead>
        <tbody>{Object.entries(data.floor).map(([k, v]: [string, any]) => (
          <tr key={k}><td>{k}</td>{RESOLUTIONS.map((r) => <td key={r}>{pct(v[r])}</td>)}<td>{v.conditions}</td></tr>))}</tbody>
      </table>
      <h4>Cells <select value={only} onChange={(e) => setOnly(e.target.value)}>
        {['HIDDEN AT COARSE RESOLUTION', 'NON-REDUNDANT', 'UNRESOLVED', 'REDUNDANT', 'all'].map((x) => <option key={x}>{x}</option>)}</select>
        <span className="dim small"> strip: x exact · N node · L local · m meso · M macro · G global (white detected, grey equivalent, amber unresolved)</span></h4>
      <table className="list small">
        <thead><tr><td>condition</td><td>vs C</td><td>resolutions</td><td>finest / coarsest visible</td><td>kind</td><td>labels</td></tr></thead>
        <tbody>{rows.slice(0, 400).map((r) => (
          <tr key={`${r.condition}|${r.comparison}`}><td className="mono">{r.condition}</td><td className="mono">{r.comparison}</td>
            <td><Strip row={r} /></td><td className="mono dim">{r.visible_from ?? '—'} / {r.visible_up_to ?? '—'}</td>
            <td className="dim small">{r.hidden_kind ?? ''}</td><td><Labels ls={r.labels} /></td></tr>))}</tbody>
      </table>
    </div>
  );
}
