import { Labels, MissingSummary, RESOLUTIONS, Strip, pct, useSummary } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
function StudyTable({ rows, variants }: { rows: any[]; variants: string[] }) {
  const conds = Array.from(new Set(rows.map((r) => r.condition)));
  return (
    <table className="list small">
      <thead><tr><td>condition</td>{variants.map((v) => <td key={v} className="mono">{v}</td>)}</tr></thead>
      <tbody>{conds.map((c) => (
        <tr key={c}><td className="mono">{c.split(':').pop()}</td>{variants.map((v) => {
          const r = rows.find((x) => x.condition === c && x.comparison === v);
          if (!r) return <td key={v} className="dim">·</td>;
          return <td key={v}><Strip row={r} /> <span className="dim mono small">{r.primary === 'REDUNDANT' ? 'identical' :
            r.largest ? `${r.largest.resolution} ${r.largest.feature} ${pct(r.largest.relative, 0)}` : ''}</span></td>;
        })}</tr>))}</tbody>
    </table>
  );
}

export default function DisconnectionView() {
  const { data, error } = useSummary(['disconnection', 'topology_triggers']);
  if (!data?.disconnection && !data?.topology_triggers) return <MissingSummary error={error} loaded={!!data} study="disconnection" />;
  const d = data.disconnection;
  const tt = data.topology_triggers;
  return (
    <div className="panel-view research">
      <p className="dim small">Targeted structures in which disconnection should matter if it is operationally non-redundant
        (flow between parts crosses weak connections). Only downstream effects count: disconnection, removal, cut and
        reconfiguration events, connection counts, out-degree and reachable share are excluded. Strip: x exact · N node · L local ·
        m meso · M macro · G global (white systematic difference, grey equivalent, amber unresolved).</p>
      {d && (<>
        <h4>Disconnection: <Labels ls={[d.verdict.status]} /></h4>
        <div className="mono small">removal detectable in: {d.verdict.removal_detected_in.join(', ') || 'none'}<br />
          removal equivalent in: {d.verdict.removal_equivalent_in.join(', ') || 'none'} · unresolved in: {d.verdict.removal_unresolved_in.join(', ') || 'none'}<br />
          replacements equivalent everywhere: {d.verdict.equivalent_replacements.join(', ') || 'none'}</div>
        <StudyTable rows={d.rows} variants={['off', 'weight_zero', 'as_cut', 'as_mutation', 'redirect', 'C~']} />
      </>)}
      {tt && (<>
        <h4>Cut / reconfiguration triggers: <Labels ls={[tt.verdict.status]} /></h4>
        <div className="mono small">removing the reconfiguration trigger (cut only) detectable in: {tt.verdict.removal_detected_in.cut_only.join(', ') || 'nowhere'};
          {' '}removing the cut trigger (reconfiguration only): {tt.verdict.removal_detected_in.reconfigure_only.join(', ') || 'nowhere'}<br />
          merged forms detectable — unified: {tt.verdict.merged_detected_in.unified.join(', ') || 'nowhere'};
          {' '}merged: {tt.verdict.merged_detected_in.merged.join(', ') || 'nowhere'} · shared operation with separate conditions
          {' '}bit-identical everywhere: {tt.verdict.generic_conditions_identical_everywhere ? 'yes' : 'no'}</div>
        <StudyTable rows={tt.rows} variants={['cut_only', 'reconfigure_only', 'unified', 'generic_conditions', 'merged', 'C~']} />
      </>)}
      <p className="dim small">Resolutions: {RESOLUTIONS.join(' · ')}.</p>
    </div>
  );
}
