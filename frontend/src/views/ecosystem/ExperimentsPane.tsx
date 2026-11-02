import { useState } from 'react';
import {
  addressExperiments, boundaryExperiments, factorial, m2Experiment, minimalConfigurations, necessity, philExperiment, recoveryPhase, sssPhase,
  type Json, type Label,
} from './meosApi';
import { fmt, groupBy, necessityGrid, regionRuns, stat } from './studies';

// The STUDIES tab: the second-stage experiments, each a button that runs the real engine on the server (same seeds, same periods for every condition) and shows
// the table the engine returned. Nothing here interprets a result beyond naming it; null, reversed and non-monotone results are shown as they come.

type Rows = Array<Record<string, unknown>>;
const arr = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);
const rec = (x: unknown): Record<string, unknown> => (x && typeof x === 'object' ? (x as Record<string, unknown>) : {});
const Chip = ({ s }: { s: Label | string }) => <span className={`eco-chip ${s}`}>{s}</span>;

export default function ExperimentsPane({ config, busy, wrap }: { config: Record<string, unknown>; busy: string | null; wrap: (name: string, fn: () => Promise<void>) => Promise<void> }) {
  const [res, setRes] = useState<Record<string, Json>>({});
  const [power, setPower] = useState<'finite' | 'unlimited'>('finite');
  const [scenario, setScenario] = useState('interaction cut 100-150');
  const run = (key: string, label: string, fn: () => Promise<Json>) => wrap(label, async () => { const r = await fn(); setRes((s) => ({ ...s, [key]: r })); });
  const cfg = power === 'unlimited' ? { ...config, power: { infinite: true } } : config;
  const dis = !!busy;
  return (
    <>
      <h3>Second-stage experiments</h3>
      <div className="eco-note">Each button recomputes the experiment with the real engine on the current configuration. Conditions inside one experiment share their seeds and period. A negative, reversed or non-monotone result is a result and is shown.</div>
      <div className="eco-row"><label>power for the minimal-configuration search <select value={power} onChange={(e) => setPower(e.target.value as 'finite' | 'unlimited')}><option>finite</option><option>unlimited</option></select></label></div>
      <div className="eco-row">
        <button disabled={dis} onClick={() => run('factorial', 'history × gradient × power (8 conditions, 5 seeds)', () => factorial(config))}>history × gradient × power</button>
        <button disabled={dis} onClick={() => run('necessity', 'where history is necessary (charge × capacity)', () => necessity(config))}>where history is necessary</button>
        <button disabled={dis} onClick={() => run('mfs', 'all minimal operational configurations (512 subsets)', () => minimalConfigurations(cfg, { horizon: 160 }))}>all minimal configurations</button>
      </div>
      <div className="eco-row">
        <button disabled={dis} onClick={() => run('boundary', 'XenoBody boundary experiments', () => boundaryExperiments(config))}>XenoBody boundaries</button>
        <select value={scenario} onChange={(e) => setScenario(e.target.value)}><option>interaction cut 100-150</option><option>A2 removed 100-150</option></select>
        <button disabled={dis} onClick={() => run('recovery', 'collapse / recovery phase (resource-pulse sweep)', () => recoveryPhase(config, { scenario }))}>recovery phase</button>
      </div>
      <div className="eco-row">
        <button disabled={dis} onClick={() => run('sss', 'SSS phase regions', () => sssPhase(config, { scales: [0.5, 1, 1.5], sizes: [0.5, 1, 2], speeds: [0.5, 0.75, 1, 1.5, 2] }))}>SSS phase regions</button>
        <button disabled={dis} onClick={() => run('address', 'Address Domain interventions', () => addressExperiments(config))}>Address Domain</button>
        <button disabled={dis} onClick={() => run('m2', 'M2 connected to a follow-on operation', () => m2Experiment(config))}>M2 connection</button>
        <button disabled={dis} onClick={() => run('phil', 'Philosophical operations (first stage)', () => philExperiment(config))}>Philosophical operations</button>
      </div>
      {res.factorial && <Factorial r={res.factorial} />}
      {res.necessity && <Necessity r={res.necessity} />}
      {res.mfs && <Minimal r={res.mfs} />}
      {res.boundary && <Boundary r={res.boundary} />}
      {res.recovery && <Recovery r={res.recovery} />}
      {res.sss && <Sss r={res.sss} />}
      {res.address && <Address r={res.address} />}
      {res.m2 && <M2 r={res.m2} />}
      {res.phil && <Phil r={res.phil} />}
    </>
  );
}

function Factorial({ r }: { r: Json }) {
  const rows = arr(r.rows) as Rows;
  return (
    <>
      <h3>history × gradient × power</h3>
      <div className="eco-note">{String(r.question)} — operation: {String(r.operation)}; seeds {arr(r.seeds).join(', ')}</div>
      <table className="eco-table"><thead><tr><th>H</th><th>G</th><th>power</th><th>state</th><th>persist</th><th>cycles</th><th>throughput</th><th>energy</th><th>renewals</th><th>A1 / A2</th><th>target</th></tr></thead>
        <tbody>{rows.map((x, i) => { const c = rec(x.condition); return <tr key={i}><td>{c.history ? 'on' : 'off'}</td><td>{c.gradient ? 'on' : 'off'}</td><td>{String(c.power)}</td><td><Chip s={String(x.operational_state)} /></td>
          <td>{String(x.persists_seeds)}/{String(x.seeds)}</td><td>{stat(x.cycles)}</td><td>{stat(x.resource_throughput)}</td><td>{stat(x.cumulative_energy_use)}</td><td>{stat(x.renewal_count)}</td><td>{stat(x.a1_activity, 0)} / {stat(x.a2_activity, 0)}</td><td>{stat(x.target_held_share)}</td></tr>; })}</tbody></table>
      <ul className="eco-log">{(arr(r.history_effect_by_condition) as Rows[]).map((e, i) => { const x = e as unknown as Record<string, unknown>; return <li key={i}><span>gradient {x.gradient ? 'on' : 'off'}, {String(x.power)} power: history {x.history_is_necessary ? 'NECESSARY' : x.history_is_reversed ? 'REVERSED (hurts)' : 'not necessary'} ({String(x.history_on)} with, {String(x.history_off)} without; Δcycles {fmt(x.difference_in_cycles)})</span></li>; })}</ul>
    </>
  );
}

function Necessity({ r }: { r: Json }) {
  const g = necessityGrid(r);
  return (
    <>
      <h3>where history is necessary</h3>
      <div className="eco-note">power recharge rate (rows) × reserve capacity (columns), seeds {arr(r.seeds).join(', ')}. H = history necessary (persists with it only), P = persists without it, X = collapses either way, R = history reverses it.</div>
      <table className="eco-table"><thead><tr><th>charge \ capacity</th>{g.capacities.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{g.rows.map((row) => <tr key={row.charge}><td>{row.charge}</td>{row.cells.map((c, i) => <td key={i} title={c.class}>{c.code}</td>)}</tr>)}</tbody></table>
      <div className="eco-note">{Object.entries(g.counts).map(([k, v]) => `${k}: ${v}`).join(' · ')}</div>
    </>
  );
}

function Minimal({ r }: { r: Json }) {
  const sets = arr(r.minimal_sets) as Rows;
  return (
    <>
      <h3>minimal operational configurations</h3>
      <div className="eco-note">MFS is relative to the operation, conditions, scale, observation, window and the admissible reductions listed here.</div>
      <dl className="eco-kv">
        <dt>operation</dt><dd>{String(r.preserved_operation)}</dd>
        <dt>conditions</dt><dd>{JSON.stringify(rec(r.environment_condition))}</dd>
        <dt>observation</dt><dd>{typeof r.observation_condition === 'string' ? r.observation_condition : JSON.stringify(r.observation_condition)}</dd>
        <dt>window</dt><dd>{JSON.stringify(r.temporal_window)}</dd>
        <dt>admissible reductions</dt><dd>{arr(r.allowed_reduction_operations).join(', ')}</dd>
        <dt>subsets run</dt><dd>{String(r.subsets_evaluated)}; {String(r.sets_that_preserve)} preserve the operation</dd>
        <dt>minimal sets</dt><dd>{String(r.minimal_set_count)} (minimum cardinality {String(r.minimum_cardinality)})</dd>
      </dl>
      {sets.map((s, i) => <div key={i} className="eco-note"><b>minimal set {i + 1}</b> (cardinality {String(s.cardinality)}; every proper subset fails: {String(s.every_proper_subset_fails)}): {arr(s.retained).join(', ')}
        <br />operation identity against the unreduced run: {Object.entries(rec(s.operation_identity)).map(([k, v]) => `${k} ${String(v)}`).join(' · ')}</div>)}
      {r.observed_minimal_sets != null && <div className="eco-note">minimal sets seen through this observation: {arr(r.observed_minimal_sets).length ? arr(r.observed_minimal_sets).map((s) => `{${arr(s).join(', ')}}`).join(' | ') : 'none (the observation cannot resolve the operation, so no configuration appears to preserve it)'}</div>}
      {arr(r.non_monotone_examples).length > 0 && <div className="eco-note"><b>non-monotone:</b> {(arr(r.non_monotone_examples) as Rows[]).map((e) => { const x = e as unknown as Record<string, unknown>; return `${String(x.component)} removed alone: ${x.removed_alone_persists ? 'persists' : 'ends it'}; removed together with ${arr(x.removed_together_with).join(', ')}: persists`; }).join(' | ')}</div>}
    </>
  );
}

function Boundary({ r }: { r: Json }) {
  const k = rec(r.kinds), c = rec(r.closure);
  const rows = arr(k.rows) as Rows;
  return (
    <>
      <h3>XenoBody boundary experiments</h3>
      <table className="eco-table"><thead><tr><th>boundary change</th><th>operation (all seeds)</th><th>coupling</th><th>renewed</th><th>history access</th><th>observation</th><th>recovery</th></tr></thead>
        <tbody>{rows.map((x, i) => { const p = rec(arr(x.per_seed)[0]); return <tr key={i}><td>{String(x.boundary_change)}</td><td>{x.operation_persists_in_all_seeds ? 'persists' : 'does not persist'}</td><td>{fmt(p.coupling_mean_interaction_strength)}</td><td>{fmt(p.resource_exchange_renewed)}</td><td>{fmt(p.history_accessibility_mean_threshold_reduction)}</td><td>{String(p.observed_state)} · {String(p.observability_status)}</td><td>{String(p.recovery_after_interruption)}</td></tr>; })}</tbody></table>
      <div className="eco-note">first seed shown per row. B1 = {arr(c.b1).join(', ')}. Of {String(c.sets_evaluated)} bodies, the minimal persisting body adds {arr(c.added_by_b3).join(', ')} to B1 — {String(c.closing_relation)}</div>
    </>
  );
}

function Recovery({ r }: { r: Json }) {
  const runs = regionRuns(r);
  return (
    <>
      <h3>collapse / recovery phase</h3>
      <div className="eco-note">{String(r.scenario)}; {String(r.pulse)}; seeds {arr(r.seeds).join(', ')}. response monotone in the pulse: {String(r.response_is_monotone)}; recovery band {JSON.stringify(r.recovery_band)}</div>
      <table className="eco-table"><thead><tr><th>region</th><th>pulse amounts</th></tr></thead><tbody>{runs.map((x) => <tr key={x.region}><td>{x.region}</td><td>{x.amounts.join(', ')}</td></tr>)}</tbody></table>
      <table className="eco-table"><thead><tr><th>pulse</th><th>region</th><th>latency</th><th>sustained</th><th>post-recovery period cv</th></tr></thead>
        <tbody>{(arr(r.rows) as Rows).filter((x) => x.region !== 'no recovery (below the band)').slice(0, 14).map((x, i) => { const p = rec(arr(x.per_seed)[0]); return <tr key={i}><td>{String(x.amount)}</td><td>{String(x.region)}</td><td>{String(p.latency ?? '-')}</td><td>{String(p.sustained_ticks ?? '-')}</td><td>{fmt(p.post_recovery_cycle_period_cv)}</td></tr>; })}</tbody></table>
    </>
  );
}

function Sss({ r }: { r: Json }) {
  const pts = arr(r.points) as Rows;
  const byScale = groupBy(pts, (p) => `scale ${String(p.scale)} · size ${String(p.size)}`);
  const speeds = arr(rec(r.axes).speed ?? rec(r.axes).speeds) as number[];
  const code = (p?: Record<string, unknown>) => (!p ? '·' : p.class === 'ACTIVE' ? (p.observation_sensitive ? 'A*' : 'A') : p.class === 'metastable' ? (p.recovery_capable ? 'M+' : 'M') : 'C');
  return (
    <>
      <h3>SSS phase regions</h3>
      <div className="eco-note">A = ACTIVE, C = COLLAPSED, M = metastable (seeds disagree or the state changes under a small perturbation), M+ = metastable and recovery-capable, * = observation-sensitive (a coarser observation misreads it). Columns are speed.</div>
      <table className="eco-table"><thead><tr><th>scale · size</th>{speeds.map((s) => <th key={s}>{s}</th>)}</tr></thead>
        <tbody>{Object.entries(byScale).map(([k, v]) => <tr key={k}><td>{k}</td>{speeds.map((s) => <td key={s}>{code(v.find((p) => p.speed === s))}</td>)}</tr>)}</tbody></table>
      <div className="eco-note">{Object.entries(rec(r.counts)).map(([k, v]) => `${k}: ${String(v)}`).join(' · ')} · recovery-capable points {String(r.recovery_capable_points)} · observation-sensitive points {String(r.observation_sensitive_points)}</div>
    </>
  );
}

function Address({ r }: { r: Json }) {
  return (
    <>
      <h3>Address Domain interventions</h3>
      <div className="eco-note">the fault is applied at tick 100; "restored" removes it at 150; "+ pulse" adds a resource pulse after the restoration. First seed of {String(arr(r.rows)[0] && rec(arr(r.rows)[0]).seeds)} shown.</div>
      <table className="eco-table"><thead><tr><th>case</th><th>fault only</th><th>restored</th><th>restored + pulse</th><th>cycles after restoration</th></tr></thead>
        <tbody>{(arr(r.rows) as Rows).map((x, i) => { const p = rec(arr(x.per_seed)[0]); return <tr key={i}><td>{String(x.case)}</td><td><Chip s={String(p.fault_only)} /></td><td><Chip s={String(p.restored)} /></td><td><Chip s={String(p.restored_and_pulse)} /></td><td>{String(p.cycles_restored)}</td></tr>; })}</tbody></table>
    </>
  );
}

function M2({ r }: { r: Json }) {
  const rows = arr(r.rows) as Rows;
  const scen = groupBy(rows, (x) => String(x.scenario));
  return (
    <>
      <h3>M2 connected to a follow-on operation</h3>
      <div className="eco-note">A1 senses M2 (the alteration A2's reconfiguration leaves) in addition to R. Conditions: none, direct, delayed (3 ticks), noisy (σ 0.05), at five weights; seeds {arr(r.seeds).join(', ')}. Persisting seeds / cycles; "=" marks no difference in outcome from no connection.</div>
      <table className="eco-table"><thead><tr><th>scenario</th>{['none', 'direct', 'delayed(3)', 'noisy(0.05)'].map((m) => <th key={m}>{m} (w 0.25 … 4)</th>)}</tr></thead>
        <tbody>{Object.entries(scen).map(([k, v]) => <tr key={k}><td>{k}</td>{['none', 'direct', 'delayed(3)', 'noisy(0.05)'].map((m) => <td key={m} className="mono">{v.filter((x) => String(x.m2).startsWith(m)).map((x) => `${String(x.persists_seeds)}${String(x.difference_vs_none).startsWith('different') ? '' : '='}`).join(' ')}</td>)}</tr>)}</tbody></table>
    </>
  );
}

function Phil({ r }: { r: Json }) {
  const rows = arr(r.rows) as Rows;
  const key = (x: Record<string, unknown>) => `${String(x.power)} · ${String(x.environment)} · ${String(x.channel)}`;
  const g = groupBy(rows, key);
  const modes = arr(r.modes) as string[];
  return (
    <>
      <h3>Philosophical operations (first stage)</h3>
      <div className="eco-note">{String(r.note)} Seeds that keep the operation (of {String(rec(rows[0]).seeds)}), per mode. Environment events: step / drift / shift-restore-shift of the renewal efficiency.</div>
      <table className="eco-table"><thead><tr><th>condition</th>{modes.map((m) => <th key={m}>{m}</th>)}</tr></thead>
        <tbody>{Object.entries(g).map(([k, v]) => <tr key={k}><td>{k}</td>{modes.map((m) => { const x = v.find((y) => y.mode === m); return <td key={m}>{x ? String(x.persists_seeds) : '·'}</td>; })}</tr>)}</tbody></table>
    </>
  );
}
