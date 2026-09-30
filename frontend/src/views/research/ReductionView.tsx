import { Fragment, useState } from 'react';
import { Missing, Ratio, Status, useExperiment } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
const METRICS = ['event_sequence', 'graph_edit', 'difference_w1', 'signature', 'response', 'criterion:reachable_structure',
  'criterion:branching', 'criterion:closure', 'criterion:recurrent_loops', 'criterion:fragmentation',
  'criterion:concentration', 'criterion:persistence', 'criterion:amplification_regime', 'criterion:path_dependence'];

export default function ReductionView() {
  const { data, error } = useExperiment('reduction');
  const [open, setOpen] = useState<string | null>(null);
  if (!data) return <Missing name="reduction" error={error} />;
  const configs: string[] = Object.keys(data.floors);
  const perf = data.audits?.performance ?? {};
  const fullMs = perf.full?.ms_per_step ?? 1;
  return (
    <div className="panel-view research">
      <p className="dim small">Full vs reduced primitive sets. {data.configs.length} dynamic regimes × {data.seeds.length} seeds,
        {' '}{data.horizon} steps, {data.n} configurations; paired runs share seed, initial graph, local state, interventions and
        length. Stage 1 tolerance: <span className="mono">{data.tolerance_rule}</span> (noise = same run under another random
        stream). Stage 2: {data.systematic?.seeds?.length} seeds × {data.systematic?.horizon} steps, paired t on scalar summaries
        (|t| &gt; {data.systematic?.t_threshold} and effect &gt; {100 * (data.systematic?.practical ?? 0)}%).</p>
      <h4>Primitive status</h4>
      <table className="list small">
        <thead><tr><td>primitive</td><td>status</td><td>diverges in</td><td>reduced to / note</td></tr></thead>
        <tbody>{data.classification.map((r: any) => (
          <Fragment key={r.primitive}>
            <tr className="clickable" onClick={() => setOpen(open === r.primitive ? null : r.primitive)}>
              <td>{r.primitive}</td><td><Status s={r.status} /></td>
              <td className="mono">{(r.diverges_in ?? []).join(', ') || '—'}</td>
              <td className="dim">{r.reduced_to ?? r.why_unresolved ?? ''}</td>
            </tr>
            {open === r.primitive && (
              <tr><td colSpan={4}>
                <div className="evidence"><div className="dim">{r.question}</div><div className="mono small">rule: {r.rule}</div>
                  <ul className="mono small">{r.evidence.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul></div>
              </td></tr>
            )}
          </Fragment>
        ))}</tbody>
      </table>
      {data.minimal_verification && (<>
        <h4>Full vs MINIMAL: {data.minimal_verification.verdict}</h4>
        <table className="list mono small">
          <thead><tr><td>regime</td><td>stage 1</td><td>exceeded</td><td>stage 2 downstream effects</td><td>worst criterion (÷ tolerance)</td></tr></thead>
          <tbody>{Object.entries(data.minimal_verification.per_regime).map(([c, p]: [string, any]) => {
            const worst = Object.entries(p.criteria_distance_over_tolerance as Record<string, number>).sort((a, b) => b[1] - a[1])[0];
            return (<tr key={c}><td>{c}</td><td>{p.stage1_verdict}</td><td>{p.stage1_exceeded.join(', ') || '—'}</td>
              <td>{Object.keys(p.stage2_downstream_effects).join(', ') || 'none'}</td>
              <td>{worst ? `${worst[0]} ${worst[1].toFixed(2)}` : '—'}</td></tr>);
          })}</tbody>
        </table>
      </>)}
      <h4>Divergence (stage 1): distance ÷ tolerance, worst regime</h4>
      <div className="heat">
        <div className="heat-row head"><span />{METRICS.map((m) => <span key={m} className="mono">{m.replace('criterion:', '').slice(0, 9)}</span>)}</div>
        {Object.entries(data.variants).map(([name, v]: [string, any]) => (
          <div className="heat-row" key={name}>
            <span className="mono small">{name}</span>
            {METRICS.map((m) => {
              const r = Math.max(...configs.map((c) => v.configs[c].distance[m] / v.configs[c].tolerance[m]));
              return <Ratio key={m} r={Number.isFinite(r) ? r : 0} />;
            })}
          </div>
        ))}
      </div>
      <h4>Systematic effects (stage 2)</h4>
      <table className="list mono small">
        <thead><tr><td>variant</td>{configs.map((c) => <td key={c}>{c}</td>)}</tr></thead>
        <tbody>{Object.entries(data.systematic?.variants ?? {}).map(([name, v]: [string, any]) => (
          <tr key={name}><td>{name}</td>{configs.map((c) => {
            const eff = Object.entries(v[c].systematic_effects as Record<string, any>);
            return <td key={c} className={eff.length ? '' : 'dim'}>{eff.length ? eff.slice(0, 3).map(([k, x]) =>
              `${k.replace(/^[sg]:|rate:/, '')} ${(100 * x.relative).toFixed(0)}%`).join(', ') + (eff.length > 3 ? ` +${eff.length - 3}` : '') : 'none'}</td>;
          })}</tr>))}</tbody>
      </table>
      <h4>Cost (engine only, sequential, regime "intermittent")</h4>
      <div className="bars">
        {Object.entries(perf).map(([name, p]: [string, any]) => (
          <div key={name} className="bar-row"><span className="mono small">{name}</span>
            <span className="bar" style={{ width: `${Math.min(100, 45 * p.ms_per_step / fullMs)}%` }} />
            <span className="mono small">{p.ms_per_step.toFixed(2)} ms/step</span></div>))}
      </div>
      <h4>Floors</h4>
      <table className="list mono small">
        <thead><tr><td>regime</td><td>ignitions/step</td><td>noise: event</td><td>noise: response</td><td>1e-9 perturbation diverged at</td></tr></thead>
        <tbody>{configs.map((c) => (
          <tr key={c}><td>{c}</td><td>{data.floors[c].full_ignitions_per_step.toFixed(1)}</td>
            <td>{data.floors[c].noise.event_sequence.toFixed(3)}</td><td>{data.floors[c].noise.response.toFixed(3)}</td>
            <td>{data.floors[c].perturbation.first_divergence.map((x: any) => x ?? 'never').join(', ')}</td></tr>))}</tbody>
      </table>
    </div>
  );
}
