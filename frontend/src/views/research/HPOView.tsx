import { useState } from 'react';
import { useExperiment } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Heterogeneous Philosophical Operations: read-only views of the HPO result files (backend/experiments/results/hpo).
// Nothing here runs an experiment; the experiments run locally (`xzr hpo run …`). Layout is lists and cards (no wide
// tables), so every section fits a phone screen.

const SECTIONS = [
  ['registry', 'Operational Registry'], ['configuration', 'Configuration'], ['active', 'Active Operations'],
  ['interactions', 'Cross-Operational Interactions'], ['itc', 'Ignition / Transformation / Cessation'],
  ['history', 'History Reentry'], ['recursive', 'Recursive Reconfiguration'], ['comparison', 'Experiment Comparison'],
  ['negative', 'Negative Results'], ['sources', 'Source Correspondence'], ['limits', 'Implementation Limits'],
] as const;
type Section = typeof SECTIONS[number][0];

const GREY: Record<string, string> = {
  DETECTED: '#ececf0', EQUIVALENT: '#a6a6ae', UNRESOLVED: '#7a7a82', IDENTICAL: '#56565e', 'NOT MEASURED': '#45454c',
};

function Chip({ s }: { s: string | undefined }) {
  const c = GREY[s ?? ''] ?? '#56565e';
  return <span className="status-chip mono" style={{ borderColor: c, color: c,
    borderStyle: s === 'UNRESOLVED' ? 'dashed' : 'solid' }}>{s ?? '—'}</span>;
}

const fmt = (x: any, d = 3) => (x === null || x === undefined ? '—' : typeof x === 'number'
  ? (Math.abs(x) >= 1000 ? x.toFixed(0) : Number(x.toPrecision(d)).toString()) : String(x));
const pct = (x: any) => (typeof x === 'number' ? `${x >= 0 ? '+' : ''}${(100 * x).toFixed(1)}%` : '—');

function NotYet({ name }: { name: string }) {
  return <p className="dim small">No result file <span className="mono">hpo/{name}.json</span> yet. It is produced
    locally by <span className="mono">xzr hpo run</span> (see docs/HPO.md); this site only reads it.</p>;
}

function ContrastList({ c, only }: { c: Record<string, any>; only?: string[] }) {
  const rows = Object.entries(c).filter(([m]) => !only || only.includes(m));
  return (
    <ul className="hpo-rows">
      {rows.map(([m, v]) => (
        <li key={m}>
          <span className="mono small hpo-metric">{m}</span>
          <Chip s={v.status} />
          <span className="mono small dim">{v.n ? `Δ ${fmt(v.mean)} (${pct(v.relative)}) · dz ${fmt(v.dz, 2)} · n ${v.n}` : 'undefined'}</span>
        </li>
      ))}
    </ul>
  );
}

function Verdict({ label, v }: { label: string; v: string }) {
  const strong = /SUPPORTED IN|DETECTED|CONTRIBUTES|validated \(/.test(v) && !/NOT|NO DETECTED|not validated/.test(v);
  return <div className="hpo-verdict"><span className="small dim">{label}</span>
    <span className={`mono small ${strong ? '' : 'dim'}`}>{v}</span></div>;
}

export default function HPOView() {
  const [sec, setSec] = useState<Section>('registry');
  const h2 = useExperiment('hpo-hpo002');
  const h1 = useExperiment('hpo-hpo001');
  const h3 = useExperiment('hpo-hpo003');
  const gen = useExperiment('hpo-general');
  const ver = useExperiment('hpo-verification');
  const sub = useExperiment('hpo-substantive');
  const d2: any = h2.data, d1: any = h1.data, d3: any = h3.data, dg: any = gen.data, dv: any = ver.data;
  const ds: any = sub.data;
  return (
    <div className="panel-view research hpo">
      <p className="small">Ziran System — <b>Heterogeneous Philosophical Operations</b> (HPO). Six operational series,
        engineering proxies named after their philosophical sources, run in one simulated world; they ignite under
        configuration-dependent conditions, act only through runtime intervention records, and change one another's
        conditions, rules, instruments, resources, history and partition. <span className="dim">Results describe this
        simulation under its stated configuration; they are not evidence for or against any philosophical doctrine.
        Read-only: experiments run locally.</span></p>
      <nav className="hpo-nav" aria-label="HPO sections">
        {SECTIONS.map(([id, label]) => (
          <button key={id} className={sec === id ? 'on' : ''} onClick={() => setSec(id)}
            aria-current={sec === id ? 'true' : undefined}>{label}</button>
        ))}
      </nav>
      {sec === 'registry' && <Registry d2={d2} />}
      {sec === 'configuration' && (d2 ? <Configuration d={d2} /> : <NotYet name="hpo002" />)}
      {sec === 'active' && (d2?.trace ? <Active t={d2.trace} /> : <NotYet name="hpo002" />)}
      {sec === 'interactions' && (d2 ? <><Interactions d={d2} />{ds && <SubInteractions s={ds} />}</> : <NotYet name="hpo002" />)}
      {sec === 'itc' && (d2 ? <><ITC d={d2} />{ds && <SubRemoval s={ds} />}</> : <NotYet name="hpo002" />)}
      {sec === 'history' && (d2 ? <><History d={d2} dg={dg} />{ds && <SubHistory s={ds} />}</> : <NotYet name="hpo002" />)}
      {sec === 'recursive' && (d3 ? <Recursive d={d3} /> : <NotYet name="hpo003" />)}
      {sec === 'comparison' && (d2 ? <Comparison d2={d2} d1={d1} dg={dg} /> : <NotYet name="hpo002" />)}
      {sec === 'negative' && <Negative d2={d2} d3={d3} dg={dg} dv={dv} />}
      {sec === 'sources' && <Sources d2={d2} />}
      {sec === 'limits' && <Limits d1={d1} dv={dv} />}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ sections
function Registry({ d2 }: { d2: any }) {
  const reg = d2?.registry;
  if (!reg) return <NotYet name="hpo002" />;
  return (<>
    <p className="small dim">{reg.source_note} Every entry is an <b>{reg.fidelity}</b>. Kinds created at run time
      (composites, reclassifications) appear under Active Operations, not here.</p>
    <div className="hpo-cards">
      {reg.entries.map((e: any) => (
        <div className="card" key={e.kind}>
          <div className="mono small dim">{e.kind}</div>
          <div className="big">{e.series}</div>
          <dl className="hpo-kv small">
            <dt>minimal shape</dt><dd>{e.minimal_shape}</dd>
            <dt>ignition</dt><dd>{e.ignition}</dd>
            <dt>rule</dt><dd>{e.rule}</dd>
            <dt>coupling</dt><dd>{e.coupling}</dd>
            <dt>split</dt><dd>{e.split}</dd>
            <dt>cessation</dt><dd>{e.cessation}</dd>
            <dt>re-ignition</dt><dd>{e.reignition}</dd>
            <dt>history</dt><dd>{e.history_reinsertion}</dd>
            <dt>real effects</dt><dd>{e.real_effects}</dd>
            <dt>observables</dt><dd>{e.observables.join(' · ')}</dd>
          </dl>
        </div>
      ))}
    </div>
    <h4>Extension candidates (not implemented)</h4>
    <p className="small dim">{reg.candidates.map((c: any) => c.series).join(' · ')}</p>
  </>);
}

function Configuration({ d }: { d: any }) {
  const cs = d.condition_settings as Record<string, any>;
  return (<>
    <p className="small">World n = {d.world.n}, regime <span className="mono">{d.world.regime}</span>; warm-up {d.warmup},
      horizon {d.horizon} steps; {d.seeds} paired seeds (generator {d.seed_ranges.generator.join('–')}, engine
      {' '}{d.seed_ranges.engine.join('–')}); {d.paired_comparisons.toLocaleString()} paired comparisons.
      Protocol <span className="mono">{d.provenance.protocol_sha256.slice(0, 12)}</span> (pinned
      {' '}<span className="mono">{d.provenance.pinned_protocol_sha256.slice(0, 12)}</span>).</p>
    <p className="small dim">Configuration conditions an HPO run holds (field.Settings): kinds, instruments (channels,
      resolution level, window, sampling period, noise, veil penetration), channel catalog, boundary (veil and gate
      scale), time (act delay), resources (pool per step, act costs), institution (forbidden requests, node and
      connection limits, maximum operations), external memory, history reinsertion, feedback, reachability horizon,
      interaction switches, evaluation order, scheduled configuration changes, stopping conditions.</p>
    <h4>Conditions</h4>
    <ul className="hpo-rows">
      {Object.entries(cs).map(([k, s]) => (
        <li key={k}><span className="mono small hpo-metric">{k}</span>
          <span className="small dim">{s === null ? 'no HPO (world only)'
            : [Object.entries(s.interaction ?? {}).filter(([, v]) => v).map(([x]) => x).join(', ') || 'all interactions off',
              s.history?.reinsert ? 'history reinsertion' : '', s.feedback === false ? 'no feedback' : '',
              (s.schedule ?? []).map((e: any) => `${e.type} ${e.channel ?? ''} @${e.at}`).join('; ')].filter(Boolean).join(' · ')}
            {k === 'C~' && ' · other endogenous stream (noise control)'}</span></li>
      ))}
    </ul>
  </>);
}

function Active({ t }: { t: any }) {
  const H = 240;
  const color: Record<string, string> = { ignite: '#ececf0', reignite: '#ececf0', cease: '#56565e', couple: '#a6a6ae',
    split: '#a6a6ae', reclassify: '#a6a6ae', revise: '#7a7a82', config: '#45454c' };
  return (<>
    <p className="small dim">One run (first seed, condition D): every operation that existed, with lineage. Composite
      kinds (∘) and splits are partition changes made at run time. {t.events_total.toLocaleString()} causal events.</p>
    <h4>Run-time kinds</h4>
    <p className="small mono">{t.runtime_kinds.map((k: any) => k.label + (k.composite ? ' (composite)' : '')).join(' · ')}</p>
    <h4>Operations</h4>
    <ul className="hpo-ops">
      {t.operations.map((o: any) => (
        <li key={o.oid}>
          <div className="small"><span className="mono">{o.oid}</span> <span className="dim">{o.label}</span>
            {' '}<span className="mono small dim">{o.status}</span>{o.lineage.length ? <span className="dim small"> ← {o.lineage.join(', ')}</span> : null}</div>
          <svg viewBox={`0 0 ${H} 10`} preserveAspectRatio="none" className="hpo-tl" role="img"
            aria-label={`timeline of ${o.oid}`}>
            <line x1="0" x2={H} y1="5" y2="5" stroke="#1c1c21" />
            <line x1={Math.max(0, o.created_at)} x2={H} y1="5" y2="5" stroke="#2a2a31" strokeWidth="3" />
            {o.timeline.map((e: any, i: number) => (
              <rect key={i} x={Math.max(0, Math.min(H - 1, e.t))} y="1" width="1.6" height="8" fill={color[e.type] ?? '#7a7a82'}>
                <title>{`${e.type} @ ${e.t}`}</title></rect>
            ))}
          </svg>
        </li>
      ))}
    </ul>
    <p className="small dim">marks: white = ignite / re-ignite · dark = cease · grey = couple / split / reclassify /
      revise · faint = configuration change.</p>
  </>);
}

function Interactions({ d }: { d: any }) {
  const t = d.trace;
  return (<>
    <p className="small dim">Interaction rules are explicit data (field.RULES): each can be ablated (switch
      <span className="mono"> transform</span>). Transformations are recorded with the target's state before and after
      and the act that caused them.</p>
    <h4>Rules</h4>
    <ul className="hpo-rows">
      {d.rules.map((r: any, i: number) => (
        <li key={i}><span className="mono small">{r[0]} —{r[1]}/{r[2]}→ {r[3]}</span>
          <span className="mono small dim">{r[4].join(' ')}</span></li>
      ))}
    </ul>
    {t && (<>
      <h4>Causal links between operations (one run)</h4>
      <ul className="hpo-rows">
        {Object.entries(t.summary.cross_link_types).map(([k, n]: [string, any]) => (
          <li key={k}><span className="mono small hpo-metric">{k}</span><span className="mono small">{n}</span></li>
        ))}
      </ul>
      <p className="small dim">longest causal path: depth {t.summary.max_depth}, {t.summary.max_sources_on_a_path} sources on
        one path.</p>
      <h4>Deepest causal chain</h4>
      <ol className="small mono hpo-chain">{t.deepest_chain.map((e: any) => (
        <li key={e.id}>t{e.t - d.warmup} · {e.type} · {e.source} → {e.target}</li>))}</ol>
      <h4>Transformations (before → after)</h4>
      <ul className="hpo-rows">
        {t.transform_examples.map((e: any, i: number) => (
          <li key={i}><span className="mono small">t{e.t} {e.source} → {e.target} ({e.rule})</span>
            <span className="mono small dim">{diff(e.before, e.after)}</span></li>
        ))}
      </ul>
    </>)}
  </>);
}

function diff(a: any, b: any, path = ''): string {
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
    return a === b ? '' : `${path}: ${fmt(a)} → ${fmt(b)}`;
  }
  return Object.keys({ ...a, ...b }).map((k) => diff(a?.[k], b?.[k], path ? `${path}.${k}` : k)).filter(Boolean).join('; ');
}

const ITC_METRICS = ['ignitions', 'fired_samples', 'first_ignition_mean', 'transformations', 'filtered', 'conflicts',
  'couplings', 'splits', 'reclassifications', 'revisions', 'cessations', 'reignitions', 'reignite_latency',
  'correction_latency', 'retransform_latency', 'unobservable_samples', 'reach_from_regions', 'applied_records'];

function ITC({ d }: { d: any }) {
  const conds = ['A', 'B', 'C', 'D'];
  return (<>
    <p className="small dim">Means per run ({d.seeds} seeds). Bars are relative to the largest of the four conditions.</p>
    <div className="hpo-cards">
      {ITC_METRICS.map((m) => {
        const vals = conds.map((c) => d.means[c]?.[m]);
        const max = Math.max(...vals.map((v) => (typeof v === 'number' ? Math.abs(v) : 0)), 1e-12);
        return (
          <div className="card" key={m}>
            <div className="mono small">{m}</div>
            {conds.map((c, i) => (
              <div key={c} className="hpo-bar"><span className="mono small dim">{c}</span>
                <span className="bar" style={{ width: `${typeof vals[i] === 'number' ? 100 * Math.abs(vals[i]) / max : 0}%` }} />
                <span className="mono small">{fmt(vals[i])}</span></div>
            ))}
          </div>
        );
      })}
    </div>
    <h4>Per kind in C (mean per run)</h4>
    <ul className="hpo-rows">
      {(d.registry?.entries ?? []).map((e: any) => (
        <li key={e.kind}><span className="mono small hpo-metric">{e.kind}</span>
          <span className="mono small dim">ignite {fmt(d.means.C[`ignitions:${e.kind}`])} · cease {fmt(d.means.C[`cessations:${e.kind}`])} ·
            re-ignite {fmt(d.means.C[`reignitions:${e.kind}`])}</span></li>
      ))}
    </ul>
    <h4>Cessation (E:k vs C) and re-ignition (F:k vs E:k)</h4>
    <ul className="hpo-rows">
      {Object.entries(d.verdicts.H3_cessation).map(([k, v]: [string, any]) => (
        <li key={k}><span className="mono small hpo-metric">{k}</span>
          <span className="small">{v.verdict}{v.downstream_detected.length ? `: ${v.downstream_detected.join(', ')}` : ''}</span>
          <span className="small dim">re-ignition: {d.verdicts.H4_reignition[k].verdict} (F {fmt(d.verdicts.H4_reignition[k].reignitions_F)}
            {' '}vs E {fmt(d.verdicts.H4_reignition[k].reignitions_E)})</span></li>
      ))}
    </ul>
  </>);
}

function History({ d, dg }: { d: any; dg: any }) {
  const v = d.verdicts.H2_historical_reinsertion;
  return (<>
    <Verdict label="H2 historical reinsertion (D vs C)" v={v.verdict} />
    <p className="small dim">Reinsertion re-enters archived data (memory), archived veils (observation conditions) and
      earlier ignition parameters into later configurations. Mean reinsertions per run in D: {fmt(v.reinsertions_mean)}.
      Detected downstream: {v.downstream_detected.join(', ') || 'none'}.</p>
    <h4>D vs C</h4>
    <ContrastList c={d.contrasts['D vs C']} />
    {dg && (<>
      <h4>Generalization (H2 downstream per setting)</h4>
      <ul className="hpo-rows">{Object.entries(dg.results).map(([k, r]: [string, any]) => (
        <li key={k}><span className="mono small hpo-metric">{k}</span>
          <span className="small dim">{r.H2_downstream.join(', ') || 'none detected'}</span></li>))}</ul>
    </>)}
  </>);
}

function Recursive({ d }: { d: any }) {
  const executed = Object.values(d.changed_paths as Record<string, number>).reduce((a, b) => a + b, 0);
  const validated = d.proposals.filter((p: any) => String(p.status).startsWith('validated')).length;
  return (<>
    <h4>Proposed · accepted · executed · validated</h4>
    <ul className="hpo-rows">
      <li><span className="small hpo-metric">configuration changes proposed</span><span className="mono small">{executed + d.rejected_changes}</span></li>
      <li><span className="small hpo-metric">accepted by the sandbox</span><span className="mono small">{executed}</span><span className="small dim">rejected {d.rejected_changes}</span></li>
      <li><span className="small hpo-metric">executed in the run</span><span className="mono small">{executed}</span><span className="small dim">every accepted change was applied live</span></li>
      <li><span className="small hpo-metric">new variables proposed / adopted / validated</span><span className="mono small">{d.proposals.length} / {d.changed_paths.variables ?? 0} runs / {validated}</span></li>
    </ul>
    <p className="small dim">All of this is reconfiguration of a simulated experiment's settings; no physical or institutional
      effect is involved or verified.</p>
    <p className="small dim">Between epochs of {d.epoch} steps the Ziran controller changes the experiment's own settings
      from what the last epoch produced (records and causal history only), inside a whitelisted sandbox
      ({d.sandbox.length} paths; no code is loaded or changed). Base condition {d.base_condition}; {d.seeds} seeds;
      control: the same number of random valid changes. Trace reproducible: <b>{String(d.reproducible_trace)}</b>.
      Rejected changes: {d.rejected_changes}.</p>
    <h4>What was reconfigured (all seeds)</h4>
    <ul className="hpo-rows">{Object.entries(d.changed_paths).map(([k, n]: [string, any]) => (
      <li key={k}><span className="mono small hpo-metric">{k}</span><span className="mono small">{n}</span></li>))}</ul>
    <h4>Proposed observation variables</h4>
    <ul className="hpo-rows">{d.proposals.map((p: any) => (
      <li key={p.name}><span className="mono small hpo-metric">{p.name}</span><span className="small">{p.status}</span>
        <span className="small dim">{p.rationale} (proposed in {p.seeds_proposed} seeds)</span></li>))}</ul>
    {Object.entries(d.validation).map(([k, v]: [string, any]) => (
      <div key={k}><h4>Validation of {k} ({v.seeds} held-out seeds)</h4>
        <p className="small dim">{v.criterion}</p><ContrastList c={v.contrast} /></div>))}
    {(['recursive vs static', 'random vs static', 'recursive vs random'] as const).map((k) => (
      <details key={k}><summary className="small">{k}</summary>
        <ContrastList c={d.contrasts[k]} only={Object.keys(d.contrasts[k]).filter((m) => d.contrasts[k][m].status === 'DETECTED'
          || ['unobservable_samples', 'cessations', 'suppressed', 'picturing_error', 'ignitions', 'reconfigurations'].includes(m))} />
      </details>))}
    <h4>Example trace (first seed)</h4>
    <ul className="hpo-rows">{d.trace_example.slice(0, 20).map((c: any, i: number) => (
      <li key={i}><span className="mono small">epoch {c.epoch} · {c.path}{c.op && c.op !== 'set' ? ` (${c.op})` : ''}</span>
        <span className="mono small dim">{JSON.stringify(c.value)} — {c.why}</span></li>))}</ul>
  </>);
}

function Comparison({ d2, d1, dg }: { d2: any; d1: any; dg: any }) {
  const options = [...Object.keys(d2.contrasts).map((k) => `HPO-002 · ${k}`),
    ...(d1 ? Object.keys(d1.results).map((k) => `HPO-001 · ${k} · truth leak`) : [])];
  const [sel, setSel] = useState(options[1] ?? options[0]);
  const [detOnly, setDetOnly] = useState(false);
  let c: Record<string, any> = {};
  if (sel.startsWith('HPO-002')) c = d2.contrasts[sel.slice('HPO-002 · '.length)];
  else if (d1) c = d1.results[sel.split(' · ')[1]]['truth_leak (oracle vs instrument)'];
  const only = detOnly ? Object.keys(c).filter((m) => c[m].status === 'DETECTED') : undefined;
  const v = d2.verdicts;
  return (<>
    <Verdict label="H1 mutual transformation (C vs B)" v={v.H1_mutual_transformation.verdict} />
    <p className="small dim">world: {v.H1_mutual_transformation.world_downstream_detected.join(', ') || 'none'} · operations:
      {' '}{v.H1_mutual_transformation.operation_downstream_detected.join(', ') || 'none'}</p>
    <Verdict label="false-positive control (C~ vs C)" v={`${v.control_noise.detected} of ${v.control_noise.metrics} detected — ${v.control_noise.valid ? 'valid' : 'INVALID'}`} />
    <div className="hpo-select small">
      <label>contrast <select value={sel} onChange={(e) => setSel(e.target.value)}>
        {options.map((o) => <option key={o}>{o}</option>)}</select></label>
      <label><input type="checkbox" checked={detOnly} onChange={(e) => setDetOnly(e.target.checked)} /> detected only</label>
    </div>
    <ContrastList c={c} only={only} />
    {sel.startsWith('HPO-001') && d1 && (
      <p className="small dim">{d1.not_a_ranking} Pilot: {d1.pilot_assets['HPO_001_Pilot.zip']}.</p>)}
    {dg && (<>
      <h4>Generalization (unused settings, {dg.seeds_per_setting} seeds each)</h4>
      <ul className="hpo-rows">{Object.entries(dg.results).map(([k, r]: [string, any]) => (
        <li key={k}><span className="mono small hpo-metric">{k}</span>
          <span className="small dim">H1 world: {r.H1_world.join(', ') || 'none'} · H1 operations: {r.H1_operation.join(', ') || 'none'}
            {' '}· noise detected {pct(r.noise_detected_share)}</span></li>))}</ul>
    </>)}
  </>);
}

function Negative({ d2, d3, dg, dv }: { d2: any; d3: any; dg: any; dv: any }) {
  const items: string[] = [];
  if (d2) {
    const v = d2.verdicts;
    if (v.H1_mutual_transformation.verdict !== 'SUPPORTED IN THIS PROXY') items.push(`H1 mutual transformation: ${v.H1_mutual_transformation.verdict}`);
    if (v.H2_historical_reinsertion.verdict !== 'SUPPORTED IN THIS PROXY') items.push(`H2 historical reinsertion: ${v.H2_historical_reinsertion.verdict}`);
    for (const [k, x] of Object.entries(v.H3_cessation) as [string, any][]) if (x.verdict !== 'CONSEQUENCES DETECTED') items.push(`H3 cessation of ${k}: ${x.verdict}`);
    for (const [k, x] of Object.entries(v.H4_reignition) as [string, any][]) if (!x.verdict.startsWith('RE-IGNITION')) items.push(`H4 re-ignition of ${k}: ${x.verdict}`);
    for (const [k, x] of Object.entries(v.H5_ablation) as [string, any][]) if (x.verdict !== 'CONTRIBUTES') items.push(`H5 ablation of ${k}: ${x.verdict}`);
    if (!v.control_noise.valid) items.push('False-positive control failed: HPO-002 statuses are not interpretable');
  }
  if (d3) for (const p of d3.proposals) if (!String(p.status).startsWith('validated')) items.push(`HPO-003 proposal ${p.name}: ${p.status}`);
  if (dg) for (const [k, r] of Object.entries(dg.results) as [string, any][]) {
    if (!r.H1_world.length && !r.H1_operation.length) items.push(`Generalization ${k}: no H1 downstream effect detected`);
    if (!r.H2_downstream.length) items.push(`Generalization ${k}: no H2 downstream effect detected`);
  }
  if (dv?.negative) items.push(...dv.negative);
  return (<>
    <p className="small dim">Negative, partial and untested outcomes, listed from the result files (never removed when
      a later result is positive).</p>
    {items.length ? <ul className="small hpo-neg">{items.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="small dim">none recorded yet</p>}
  </>);
}

function Sources({ d2 }: { d2: any }) {
  const reg = d2?.registry;
  if (!reg) return <NotYet name="hpo002" />;
  return (<>
    <p className="small">{reg.source_note}</p>
    {reg.entries.map((e: any) => (
      <div className="card hpo-source" key={e.kind}>
        <div className="big">{e.series} <span className="mono small dim">({e.kind})</span></div>
        <ul className="small">{e.sources.map((s: any) => <li key={s.work}>{s.work}, {s.year} — <span className="mono">{s.status}</span></li>)}</ul>
        <dl className="hpo-kv small">
          <dt>central claim (paraphrase)</dt><dd>{e.central_claim}</dd>
          <dt>implemented as</dt><dd>{e.minimal_shape}</dd>
          <dt>approximation</dt><dd>{e.approximation}</dd>
          <dt>failure condition</dt><dd>{e.failure}</dd>
          <dt>revision condition</dt><dd>{e.revision}</dd>
        </dl>
      </div>
    ))}
  </>);
}

function Limits({ d1, dv }: { d1: any; dv: any }) {
  return (<>
    <ul className="small hpo-neg">
      <li>Every series is an engineering proxy named after its source; none is a formalisation of the philosophy, and
        no result is evidence about a doctrine. Primary texts were not consulted for this implementation.</li>
      <li>Interaction rules (field.RULES), thresholds and rule parameters are design choices of this implementation,
        calibrated on development seeds; other choices can give other results.</li>
      <li>One simulated runtime, one world generator, n = 800 (1,200 in one generalization setting), 240 steps per run.</li>
      <li>Effects are simulation-internal causal effects. The runs have no physical, institutional or networked
        effect outside the simulation.</li>
      <li>Not observed ≠ absent: unobservable values carry their reason and are never read as zero.</li>
      <li>Recursive reconfiguration changes settings inside a whitelisted sandbox; it does not modify code. Proposed
        variables are distinct from validated ones.</li>
      <li>Number of trials is not philosophical validity: the paired comparisons bound statistical error for these
        proxies only.</li>
      {d1 && <li>HPO-001: {d1.pilot_assets['HPO_001_Pilot.zip']}.</li>}
      <li>This site is read-only; it runs no experiment.</li>
    </ul>
    {dv && (<>
      <h4>Verification</h4>
      <ul className="hpo-rows">{(dv.checks ?? []).map((c: any) => (
        <li key={c.check}><span className="small hpo-metric">{c.check}</span>
          <span className="mono small">{c.ok === null ? 'outcome' : c.ok ? 'pass' : 'FAIL'}</span><span className="small dim">{c.detail}</span></li>))}</ul>
    </>)}
  </>);
}

// ------------------------------------------------------------------------------------------------ post-hoc (substantive.json)
function PostHocNote({ s }: { s: any }) {
  return <p className="small dim">Post-hoc descriptive analysis ({s.seeds} confirmatory seeds re-run deterministically;
    not pre-registered, no hypothesis tested). Re-run reproduces the confirmatory trace: {String(s.reproduces_confirmatory_trace)}.</p>;
}

function SubInteractions({ s }: { s: any }) {
  const c = s.results.C;
  return (<>
    <h4>Which series changed which conditions (C, per run)</h4><PostHocNote s={s} />
    <ul className="hpo-rows">{Object.entries(c.Q2_causing_series).slice(0, 12).map(([k, v]: [string, any]) => (
      <li key={k}><span className="mono small hpo-metric">{k}</span><span className="mono small">{fmt(v)}</span></li>))}</ul>
    <h4>Changed ignition conditions and rules (C)</h4>
    <ul className="hpo-rows">{Object.entries(c.Q1_changed_ignition_conditions).slice(0, 12).map(([k, v]: [string, any]) => (
      <li key={k}><span className="mono small hpo-metric">{k}</span>
        <span className="mono small dim">{v.runs}/{s.seeds} runs · {fmt(v.per_run)} per run · mean change {pct(v.mean_relative_change)}</span></li>))}</ul>
    <p className="small dim">Parameters still changed at the end of the run: C {pct(c.Q4_parameters_persisting_changed)} vs B
      {' '}{pct(s.results.B.Q4_parameters_persisting_changed)} (B: own feedback only).</p>
    <h4>Kinds that ignited only with / only without mutual transformation (C vs B, share of seeds)</h4>
    <ul className="hpo-rows">{Object.entries(s.results.Q3_C_vs_B).map(([k, v]: [string, any]) => (
      <li key={k}><span className="mono small hpo-metric">{k}</span>
        <span className="mono small dim">enabled {pct(v.enabled_share)} · disabled {pct(v.disabled_share)}</span></li>))}</ul>
    <h4>Composite kinds formed (C, runs out of {s.seeds})</h4>
    <p className="mono small">{Object.entries(c.Q7_configuration.composite_kinds_seen_in_runs).map(([k, v]) => `${k} ${v}`).join(' · ')}</p>
  </>);
}

function SubRemoval({ s }: { s: any }) {
  return (<>
    <h4>After removing a series' condition (E:k vs C)</h4><PostHocNote s={s} />
    <ul className="hpo-rows">{Object.entries(s.results.Q5_removal).map(([k, v]: [string, any]) => (
      <li key={k}><span className="mono small hpo-metric">{k}</span>
        <span className="mono small dim">its transformations after step 80: {fmt(v.transforms_by_k_after_step_80_C)} → {fmt(v.transforms_by_k_after_step_80_E)} ·
          ignited in {pct(v.ignited_share_E)} of E runs · others' drift {fmt(v.drift_C)} → {fmt(v.drift_E)}</span></li>))}</ul>
  </>);
}

function SubHistory({ s }: { s: any }) {
  return (<>
    <h4>What re-entered (D, per run)</h4><PostHocNote s={s} />
    <ul className="hpo-rows">{Object.entries(s.results.D.Q6_reinsertions).map(([k, v]: [string, any]) => (
      <li key={k}><span className="small hpo-metric">{k}</span>
        <span className="mono small dim">{fmt(v.per_run)} per run · {v.share_causing_a_later_event === null ? '—' : pct(v.share_causing_a_later_event)} caused a later event</span></li>))}</ul>
    <p className="small dim">Re-entries are executed and causally linked in the run, yet no downstream difference between D and C was
      detected (H2 not supported).</p>
  </>);
}
