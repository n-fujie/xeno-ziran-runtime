import { Fragment, useState } from 'react';
import { Missing, Yes, useExperiment } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
const REPS = ['none', 'scorekeeping_no_entitlement', 'support_single', 'support', 'support_greatest'];
const REP_LABEL: Record<string, string> = {
  none: 'operational only', scorekeeping_no_entitlement: 'no entitlement', support_single: 'alt · one status',
  support: 'alt · least fixpoint', support_greatest: 'alt · greatest fixpoint',
};

export default function ReasonView() {
  const { data, error } = useExperiment('reason');
  const [open, setOpen] = useState<string | null>(null);
  if (!data) return <Missing name="reason" error={error} />;
  const eq = data.representation_equivalence;
  const cr = data.criteria;
  return (
    <div className="panel-view research">
      <p className="dim small">Suite <span className="mono">philosophical_nonredundancy</span> on scenario
        {' '}<span className="mono">{data.scenario}</span>: every scenario runs the same world, seed, edits and length under each
        representation. Cells show whether the representation's world trajectory is identical to scorekeeping (=) or
        diverges beyond the noise floor on some criteria (≠ n), or differs within noise (~).</p>
      <h4>Scenarios</h4>
      <table className="list small">
        <thead><tr><td>scenario</td>{REPS.map((r) => <td key={r}>{REP_LABEL[r]}</td>)}
          <td>vocabulary non-redundant</td><td>replay exact</td><td>edit effect</td></tr></thead>
        <tbody>{Object.entries(data.scenarios).map(([name, s]: [string, any]) => (
          <Fragment key={name}>
            <tr className="clickable" onClick={() => setOpen(open === name ? null : name)}>
              <td className="mono">{name}</td>
              {REPS.map((r) => {
                const x = s.representations[r];
                return <td key={r} className="mono">{x.identical_to_scorekeeping ? '=' : x.exceeds.length ? `≠ ${x.exceeds.length}` : '~'}</td>;
              })}
              <td><Yes v={s.vocabulary_nonredundant} /></td>
              <td><Yes v={s.replay_reproduces_scorekeeping_exactly} /></td>
              <td className="mono">{s.edit_effect.identical ? 'none' : s.edit_effect.exceeds.length ? `≠ ${s.edit_effect.exceeds.length}` : '~'}</td>
            </tr>
            {open === name && <tr><td colSpan={9}><div className="evidence small">{s.statement}
              <div className="mono dim">collapsed share (scorekeeping): {s.representations.scorekeeping.collapsed_share} ·
                revisions: {s.representations.scorekeeping.revisions} · intervention changes: {s.representations.scorekeeping.overlay_changes}</div>
              {REPS.map((r) => s.representations[r].exceeds.length > 0 &&
                <div key={r} className="mono dim">{REP_LABEL[r]} exceeds: {s.representations[r].exceeds.join(', ')}</div>)}
            </div></td></tr>}
          </Fragment>
        ))}</tbody>
      </table>
      {data.world_effects && (<>
        <h4>World effects, {data.world_effects.seeds.length} paired seeds × {data.world_effects.horizon} steps</h4>
        <table className="list small">
          <thead><tr><td>comparison</td><td>identical runs</td><td>interventions differ (checks)</td><td>systematic world effects</td></tr></thead>
          <tbody>{Object.entries(data.world_effects.pairs).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td><td className="mono">{v.identical_runs}/{v.seeds}</td>
              <td className="mono">{v.intervention_checks_differing.toFixed(2)}</td>
              <td className="mono">{Object.entries(v.world_effects).slice(0, 3).map(([n, e]: [string, any]) =>
                `${n.replace(/^[sg]:|rate:/, '')} ${(100 * e.relative).toFixed(0)}% (t ${e.t})`).join(', ') || 'none'}</td></tr>))}</tbody>
        </table>
        <p className="dim small">schedule adaptivity (share of checks differing between world seeds):
          {' '}{Object.entries(data.world_effects.adaptivity).map(([k, v]) => `${k} ${v}`).join(' · ')}</p>
      </>)}
      <h4>Representation equivalence on random claim graphs ({eq.states.toLocaleString()} states)</h4>
      <table className="list small">
        <thead><tr><td>representation</td><td>vs</td><td>disagreements</td><td>located in cause (cycle · unentitled support · conflict scope)</td></tr></thead>
        <tbody>{Object.entries(eq.vs_scorekeeping).map(([k, v]: [string, any]) => (
          <tr key={k}><td className="mono">{k}</td><td className="mono">{v.reference}</td>
            <td className="mono">{v.disagreements} ({v.explained} located)</td>
            <td className="mono dim">{v.disagreements ? `${v.by_cause.cycle} · ${v.by_cause.unentitled_support} · ${v.by_cause.conflict_scope}` : 'identical in every state'}</td></tr>))}</tbody>
      </table>
      <h4>Non-redundancy criteria</h4>
      <div className="grid2 small">
        <div>
          <b>Transition prediction</b> <span className="dim">(held-out seeds)</span>
          <table className="list mono"><thead><tr><td>features</td><td>intervention change acc.</td><td>activity R²</td></tr></thead>
            <tbody>{Object.entries(cr.transition_prediction).map(([k, v]: [string, any]) => (
              <tr key={k}><td>{k}</td><td>{v.overlay_change.accuracy.toFixed(3)} <span className="dim">(base {v.overlay_change.base_rate.toFixed(2)})</span></td>
                <td>{v.activity_AB.r2.toFixed(3)}</td></tr>))}</tbody></table>
        </div>
        <div>
          <b>Reconfiguration control</b> <span className="dim">(share of checks inside grounding bands)</span>
          <table className="list mono"><tbody>{Object.entries(cr.reconfiguration_control).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td><td>{v.in_band_mean.toFixed(3)}</td><td className="dim">{v.in_band_by_seed.join(' ')}</td></tr>))}</tbody></table>
        </div>
        <div>
          <b>Intervention precision</b>
          <div className="mono">mean side effects of the best single reasoning edit: {String(cr.intervention_precision.reasoning_edit_mean_side_effects)}
            {' '}· unreachable: {cr.intervention_precision.unreachable_by_single_reasoning_edit} of {cr.intervention_precision.modifiers}
            {' '}· direct operational edit: 0</div>
        </div>
        <div>
          <b>Dependency tracing</b> <span className="dim">({cr.dependency_tracing.note})</span>
          <table className="list mono"><tbody>{Object.entries(cr.dependency_tracing.scores).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td><td>recall {v.recall.toFixed(2)}</td></tr>))}</tbody></table>
        </div>
        <div>
          <b>Error detection</b> <span className="dim">({cr.error_detection.note})</span>
          <table className="list mono"><tbody>{Object.entries(cr.error_detection.rates).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td><td>{Object.entries(v).map(([kk, n]) => `${kk} ${n}`).join(' · ')}</td></tr>))}</tbody></table>
        </div>
        <div>
          <b>Compression</b> <span className="dim">(tokens: operational item changes vs reasoning revisions + schedule)</span>
          <table className="list mono"><tbody>{Object.entries(cr.compression).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td><td>{v.operational_tokens} vs {v.reasoning_tokens_dynamic} + {v.reasoning_tokens_static} static
              {v.compresses ? ' · compresses' : ' · no'}</td></tr>))}</tbody></table>
        </div>
      </div>
      <h4>Closed loop (world ↔ reason)</h4>
      <p className="small dim">revisions {data.closed_loop.revisions} · intervention recompilations {data.closed_loop.overlay_changes} ·
        gate calls {data.closed_loop.gate_calls}</p>
      <ul className="events mono small">{data.closed_loop.chain.slice(0, 40).map((c: any, i: number) => (
        <li key={i}><span className="dim">t{c.t}</span> {c.event}</li>))}</ul>
    </div>
  );
}
