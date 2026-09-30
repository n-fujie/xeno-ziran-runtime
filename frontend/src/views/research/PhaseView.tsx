import Chart, { type Marker } from '../../components/Chart';
import { Missing, useExperiment } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// a world effect counts as demonstrated only if it is not a single borderline summary
const strength = (c: any): string => {
  if (!c.world_effect_detected) return 'no';
  const eff = Object.values(c.effects ?? {}) as { t: number | string }[];
  const strong = eff.length > 1 || eff.some((e) => e.t === 'inf' || Math.abs(Number(e.t)) >= 5);
  return strong ? 'yes' : 'marginal';
};

const PHASE_COLOR: Record<string, string> = { pre: '#3a3a40', not_enabled: '#50648c', reasoning: '#3f7a52', collapsed: '#8a3a30' };

export default function PhaseView() {
  const { data, error } = useExperiment('reason');
  if (!data) return <Missing name="reason" error={error} />;
  const ph = data.phases;
  const tl: any[] = ph.timeline;
  const t = tl.map((r) => r.t);
  const markers: Marker[] = tl.map((r) => ({ t: r.t, color: PHASE_COLOR[r.phase] ?? '#333' }));
  const cond = (i: number) => tl.map((r) => r.conditions?.[i] ?? NaN);
  return (
    <div className="panel-view research">
      <p className="dim small">One world passes through three intervals: pre-reasoning (t &lt; {ph.schedule.reasoning_from}: no
        scorekeeping), reasoning (allowed; active only while the enabling conditions hold), and degradation at
        t = {ph.schedule.degrade_at} ({ph.schedule.degradation}). Background marks: <span style={{ color: PHASE_COLOR.pre }}>■</span> pre ·
        {' '}<span style={{ color: PHASE_COLOR.not_enabled }}>■</span> allowed, not enabled · <span style={{ color: PHASE_COLOR.reasoning }}>■</span> reasoning ·
        {' '}<span style={{ color: PHASE_COLOR.collapsed }}>■</span> collapsed.</p>
      <div className="cards">
        <div className="card"><div className="dim small">enabled at</div><div className="mono big">t{ph.enabled_at ?? '—'}</div></div>
        <div className="card"><div className="dim small">collapsed at</div><div className="mono big">t{ph.collapsed_at ?? '—'}</div></div>
        <div className="card"><div className="dim small">commitment distinction first operative</div><div className="mono big">t{ph.first_commitment_distinction ?? 'never'}</div></div>
        <div className="card"><div className="dim small">entitlement distinction first operative</div><div className="mono big">t{ph.first_entitlement_distinction ?? 'never'}</div></div>
      </div>
      <div className="grid2">
        <Chart title="enabling conditions: memory in R · stability of R · mutation rate" markers={markers} series={[
          { label: 'memory R', t, v: cond(0), color: '#e6e6ea' },
          { label: 'stability R ×10', t, v: cond(1).map((x) => 10 * x), color: '#8f8f96' },
          { label: 'mutation', t, v: cond(2), color: '#5a5a61' }]} />
        <Chart title="distinctions operative (1 = compiled interventions would differ)" markers={markers} series={[
          { label: 'commitment/entitlement split', t, v: tl.map((r) => (r.commitment_distinction ? 1 : 0)), color: '#e6e6ea' },
          { label: 'entitlement tracking', t, v: tl.map((r) => (r.entitlement_distinction ? 0.9 : 0)), color: '#8f8f96', dashed: true }]} />
        <Chart title="operational interventions in force · grounded revisions" markers={markers} series={[
          { label: 'interventions', t, v: tl.map((r) => r.overlay_items), color: '#e6e6ea' },
          { label: 'revisions', t, v: tl.map((r) => r.revisions), color: '#8f8f96' }]} />
        <Chart title="effective strengths (K1, K4, K9)" markers={markers} series={['K1', 'K4', 'K9'].map((k, i) => ({
          label: k, t, v: tl.map((r) => r.effective?.[k] ?? 0), color: ['#e6e6ea', '#8f8f96', '#5a5a61'][i] }))} />
      </div>
      <h4>Checks per phase</h4>
      <table className="list mono small">
        <thead><tr><td>phase</td><td>checks</td><td>commitment distinction operative</td><td>entitlement distinction operative</td><td>intervention changes</td></tr></thead>
        <tbody>{Object.entries(ph.by_phase).map(([k, v]: [string, any]) => (
          <tr key={k}><td>{k}</td><td>{v.checks}</td><td>{v.commitment_distinction}</td><td>{v.entitlement_distinction}</td><td>{v.overlay_changes}</td></tr>))}</tbody>
      </table>
      <h4>Sensitivity to a reasoning edit (remove concept “responsibility”) by phase</h4>
      <table className="list mono small">
        <thead><tr><td>t</td><td>phase</td><td>first divergence</td><td>event distance (edit / noise)</td><td>exceeds noise on</td></tr></thead>
        <tbody>{Object.entries(ph.sensitivity_to_reasoning_edit).map(([k, v]: [string, any]) => (
          <tr key={k}><td>{k}</td><td>{v.phase}</td><td>{v.edit_first_divergence ?? 'none'}</td>
            <td>{v.edit_event_distance.toFixed(3)} / {v.noise_event_distance.toFixed(3)}</td><td>{v.exceeds_noise_on.join(', ') || '—'}</td></tr>))}</tbody>
      </table>
      {data.enabling_matrix && (<>
        <h4>Enabling conditions: each degraded at t = {data.enabling_matrix.degradation_at} ({data.enabling_matrix.seeds.length} paired world seeds)</h4>
        <p className="dim small">{data.enabling_matrix.note}. Probe for counterfactual discrimination: {data.enabling_matrix.probe_edit}.
          “interventions ≠” = share of checks at which the applied operational interventions differ (exact);
          “world” = a systematic world effect (paired |t| &gt; 4 and &gt; 2%).</p>
        <table className="list mono small">
          <thead><tr><td>condition</td><td>gated: collapsed</td><td>adaptivity</td><td>vs none: interventions ≠ · world</td>
            <td>vs memoryless</td><td>counterfactual (P1 vs P2)</td><td>world value on</td></tr></thead>
          <tbody>{Object.entries(data.enabling_matrix.conditions).map(([k, v]: [string, any]) => {
            const cell = (c: any) => `${c.intervention_checks_differing.toFixed(2)} · ${strength(c)}`;
            const robust = Object.entries(v.ungated).filter(([, c]) => strength(c) === 'yes').map(([n]) => n);
            return (<tr key={k}><td>{k}{v.measured_by_gate || k.startsWith('none') ? '' : ' *'}</td><td>{v.gated_collapsed_share.toFixed(2)}</td>
              <td>{v.adaptivity.toFixed(2)}</td><td>{cell(v.ungated.world_effect_vs_none)}</td>
              <td>{cell(v.ungated.persistence_vs_memoryless)}</td><td>{cell(v.ungated.counterfactual_discrimination)}</td>
              <td>{robust.join(', ') || 'none'}</td></tr>);
          })}</tbody>
        </table>
        <p className="dim small">* not measured by any enabling gate: a gated collapse can only happen indirectly.
          “marginal” = a single summary just over threshold (|t| &lt; 5): not counted as a demonstrated effect.</p>
      </>)}
      <h4>Mutation sweep (connection mutation in the record region R from t = {data.edit_at})</h4>
      <table className="list mono small">
        <thead><tr><td>rate</td><td>collapsed share after</td><td>first collapse</td><td>stability of R</td><td>revisions</td></tr></thead>
        <tbody>{Object.entries(data.mutation_sweep).map(([k, v]: [string, any]) => (
          <tr key={k}><td>{k}</td><td>{v.collapsed_share_after.toFixed(2)}</td><td>{v.first_collapse ?? '—'}</td>
            <td>{v.stability_R_after_mean?.toFixed(3)}</td><td>{v.revisions}</td></tr>))}</tbody>
      </table>
    </div>
  );
}
