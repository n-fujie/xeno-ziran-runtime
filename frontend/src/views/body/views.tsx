import { useMemo, useState } from 'react';
import type { LedgerBundle, LegalBundle, MhegBundle, TeooBody, TeooChannel, TeooRecord } from './bodyApi';
import { channelOf, integratedRows, LEVELS, recordOf, segments, statusRuns, STATUS_COLOR, validRange, type ObsState, type Session } from './session';

// BODY / TOTAL OBSERVATION — Views B to H. Each is a function of the session bundle (and of the shared time t); none computes a result: they show what the backend produced, with each item's class,
// record id and limit. Nothing is merged across evidence levels.
const W = 760, H = 250, X0 = 52, X1 = W - 12, Y0 = 14, Y1 = H - 44;
const Note = ({ children }: { children: React.ReactNode }) => <div className="teoo-note small">{children}</div>;
const Chip = ({ s }: { s: string }) => <span className="teoo-chip" style={{ borderColor: STATUS_COLOR[s] ?? '#888' }}><i style={{ background: STATUS_COLOR[s] ?? '#888' }} />{s}</span>;
const ids = (xs: string[]) => <span className="mono small">{xs.join(', ')}</span>;

export function Plot({ ch, est, gap }: { ch: TeooChannel; est?: { times: number[]; values: number[]; sd: number[] } | null; gap?: [number, number] | null }) {
  const [lo0, hi0] = validRange(ch), vs = est ? [...est.values.map((v, i) => v - est.sd[i]), ...est.values.map((v, i) => v + est.sd[i]), lo0, hi0] : [lo0, hi0];
  const lo = Math.min(...vs), hi = Math.max(...vs) > lo ? Math.max(...vs) : lo + 1, t0 = ch.times[0], t1 = ch.times[ch.times.length - 1] || t0 + 1;
  const x = (t: number) => X0 + ((t - t0) / (t1 - t0 || 1)) * (X1 - X0), y = (v: number) => Y1 - ((v - lo) / (hi - lo)) * (Y1 - Y0);
  const segs = useMemo(() => segments(ch, x, y), [ch]); // eslint-disable-line react-hooks/exhaustive-deps
  const runs = statusRuns(ch);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${ch.variable} over device time; gaps are shown as gaps`} data-testid="teoo-plot" className="teoo-plot">
      <rect x={X0} y={Y0} width={X1 - X0} height={Y1 - Y0} fill="none" stroke="#45454c" />
      {gap && <rect x={x(gap[0])} y={Y0} width={Math.max(1, x(gap[1]) - x(gap[0]))} height={Y1 - Y0} fill="#ff8a70" opacity={0.12} data-testid="teoo-gap" />}
      {est && <polygon data-testid="teoo-band" points={[...est.times.map((t, i) => `${x(t)},${y(est.values[i] + est.sd[i])}`), ...est.times.map((t, i) => `${x(t)},${y(est.values[i] - est.sd[i])}`).reverse()].join(' ')} fill="#c9a227" opacity={0.2} />}
      {est && <polyline data-testid="teoo-estimate" points={est.times.map((t, i) => `${x(t)},${y(est.values[i])}`).join(' ')} fill="none" stroke="#c9a227" strokeDasharray="5 3" />}
      {segs.map((p, i) => <polyline key={i} data-testid="teoo-segment" points={p} fill="none" stroke="#e8e8ec" strokeWidth={1.2} />)}
      {runs.map((r, i) => <rect key={i} data-testid="teoo-run" data-status={r.status} x={x(ch.times[r.from])} y={Y1 + 8} width={Math.max(1, x(ch.times[Math.min(r.to + 1, ch.times.length - 1)]) - x(ch.times[r.from]))} height={14} fill={STATUS_COLOR[r.status] ?? '#999'}><title>{r.status}</title></rect>)}
      <text x={X0} y={H - 8} fill="#9a9aa2" fontSize="10">{ch.variable} [{ch.unit}] · device time (s) · ribbon: status of each sample · a gap is not a zero</text>
    </svg>
  );
}

// ------------------------------------------------------------------------------------------------ B: temporal operational shape
export function ViewB({ s, variable, onVariable }: { s: Session; variable: string; onVariable: (v: string) => void }) {
  const rec = s.records[0], ch = channelOf(rec, variable)!, est = recordOf(s, s.reconstruction.record_id)!;
  const e = variable === s.reconstruction.variable ? (est.payload as unknown as { reconstruction: { value: { times: number[]; values: number[]; sd: number[] } } }).reconstruction.value : null;
  const counts = Object.entries(ch.counts);
  return (
    <div data-testid="teoo-view-b">
      <div className="teoo-controls"><label>variable <select value={variable} onChange={(ev) => onVariable(ev.target.value)} data-testid="teoo-var">{rec.payload.channels!.map((c) => <option key={c.variable}>{c.variable}</option>)}</select></label>
        <span className="small dim">record <span className="mono">{rec.record_id}</span> · {rec.provenance} {rec.kind}</span></div>
      <Plot ch={ch} est={e} gap={e ? s.reconstruction.lost.interval_s : null} />
      <div className="small">{counts.map(([k, v]) => <span key={k} style={{ marginRight: 10 }}><Chip s={k} /> {v}</span>)}</div>
      <Note>White line: observed samples (MEASURED_VALID only). Dashed gold with a band: a reconstruction of the dropout and its uncertainty, from record <span className="mono">{s.reconstruction.record_id}</span> (RECONSTRUCTED_ESTIMATE: not an observation). The ribbon names why each stretch has or lacks a value. {s.time_base}.</Note>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ C: relational observation
export function ViewC({ s, t }: { s: Session; t: number }) {
  const body: TeooBody = s.bodies['1'], v = body.versions[body.versions.length - 1], st = nearest(s, t);
  const comps = v.components, pos: Record<string, [number, number]> = {};
  comps.forEach((c) => { const l = c.attrs.concept_layout!; pos[c.id] = [30 + l.x * 4.2, 14 + l.y * 1.75]; });
  const sensors = (s.observation.history.filter((c) => c.version === st.version)[0] ?? s.observation.history[0]).sensors;
  const refOf = (tid: string) => v.targets.find((x) => x.id === tid)?.ref;
  return (
    <div data-testid="teoo-view-c">
      <svg viewBox="0 0 560 380" role="img" aria-label="declared body relations, observation relations and hypothesised relations" className="teoo-plot">
        {v.relations.map((r) => <line key={r.id} data-kind="declared" x1={pos[r.source][0]} y1={pos[r.source][1]} x2={pos[r.target][0]} y2={pos[r.target][1]} stroke="#55555e" strokeWidth={1.6} />)}
        {comps.map((c) => <circle key={c.id} data-kind="component" cx={pos[c.id][0]} cy={pos[c.id][1]} r={5} fill="#2b2b31" stroke="#9a9aa2"><title>{c.id}</title></circle>)}
        {sensors.map((sn, i) => <g key={sn.id} data-kind="sensor"><rect x={400} y={20 + i * 34} width={26} height={16} fill="#1c2840" stroke="#9bb0d0" /><text x={432} y={32 + i * 34} fill="#9bb0d0" fontSize="11">{sn.id} ({sn.channels.join(',')})</text></g>)}
        {Object.entries(st.targets).map(([tid, a]) => { const ref = refOf(tid); if (!ref || !pos[ref]) return null; const sn = sensors.findIndex((x) => x.id === a.sensor); const valid = a.status === 'MEASURED_VALID';
          return sn < 0 ? null : <line key={tid} data-kind="observation" data-status={a.status} x1={413} y1={28 + sn * 34} x2={pos[ref][0]} y2={pos[ref][1]} stroke={STATUS_COLOR[a.status] ?? '#999'} strokeWidth={valid ? 1.4 : 1} strokeDasharray={valid ? undefined : '3 3'} opacity={valid ? 0.9 : 0.7} />; })}
        {s.relation_field.relations.filter((r) => !r.observed).map((r, i) => <g key={r.id} data-kind="hypothesised"><circle cx={470} cy={190 + i * 38} r={9} fill="none" stroke="#c9a227" strokeDasharray="2 3" /><text x={486} y={194 + i * 38} fill="#c9a227" fontSize="11">{r.id} ({r.dimension}){r.judgment_changing === null ? ' ?' : ''}</text><line x1={461} y1={190 + i * 38} x2={pos.trunk[0]} y2={pos.trunk[1]} stroke="#c9a227" strokeDasharray="1 4" opacity={0.6} /></g>)}
      </svg>
      <ul className="small teoo-legend2"><li><b>solid grey</b>: declared body relation</li><li><b>solid / dashed colour</b>: observation relation from a sensor at t = {st.t} s (dashed: the target is not validly observed; colour = status)</li><li><b>dotted gold</b>: a relation outside the observed field, declared for the task ("?": whether it could change the judgment is unknown)</li></ul>
      <Note>{s.relation_field.reading}. {s.relation_field.epistemically_open ? 'The field is epistemically open: no general claim from this local observation.' : 'No declared relation is open.'}</Note>
    </div>
  );
}

const nearest = (s: Session, t: number): ObsState => s.observation.states.reduce((a, b) => (Math.abs(b.t - t) < Math.abs(a.t - t) ? b : a));

// ------------------------------------------------------------------------------------------------ D: observation limits
export function ViewD({ s, t }: { s: Session; t: number }) {
  const st = nearest(s, t), cfg = s.observation.history.find((c) => c.version === st.version)!;
  return (
    <div data-testid="teoo-view-d">
      <div className="small">t = <b>{st.t} s</b> · configuration <b>v{st.version}</b> in force · {st.observed} of {st.declared_targets} declared targets observed <span className="dim">({st.note})</span></div>
      <table className="small teoo-table" data-testid="teoo-limits"><thead><tr><th>target</th><th>status</th><th>causes</th><th>sensor</th><th>detail</th></tr></thead>
        <tbody>{Object.entries(st.targets).map(([tid, a]) => <tr key={tid} data-target={tid}><td className="mono">{tid}</td><td><Chip s={a.status} /></td><td>{a.causes.join(' + ') || (a.cause_known ? 'none' : 'unknown')}</td><td>{a.sensor ?? '-'}</td><td>{a.detail.join('; ') || (a.undetermined.length ? `undetermined: ${a.undetermined.join(', ')}` : '')}</td></tr>)}</tbody></table>
      <h4>Sensors of this configuration</h4>
      <table className="small teoo-table"><thead><tr><th>sensor</th><th>channels</th><th>resolution</th><th>sampling period (s)</th><th>window (s)</th><th>detection limit</th><th>penetration</th><th>reach</th></tr></thead>
        <tbody>{cfg.sensors.map((x) => <tr key={x.id}><td>{x.id}</td><td>{x.channels.join(',')}</td><td>{x.resolution}</td><td>{x.sampling_period_s}</td><td>{x.window_s}</td><td>{x.detection_limit}</td><td>{x.penetration}</td><td>{x.reach ? x.reach.join(', ') : 'all'}</td></tr>)}</tbody></table>
      <h4>Revisions of the apparatus</h4>
      <ul className="small" data-testid="teoo-revisions">{s.observation.revisions.map((e) => <li key={e.seq}><b>{e.status}</b> {e.type} at {e.at} s — {e.reason} · gained {e.gained.map((g) => g.target).join(', ') || 'nothing'} · lost {e.lost.map((g) => g.target).join(', ') || 'nothing'}{e.after_version ? ` · v${e.before_version} → v${e.after_version}` : ' · no version made (a proposal)'}</li>)}</ul>
      <Note>{st.claim_note} No revision here shows that the apparatus revised itself: every event records who initiated it ({[...new Set(s.observation.revisions.map((e) => e.initiated_by))].join(', ')}) and that autonomous revision is not demonstrated.</Note>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ E: intervention
export function ViewE({ s }: { s: Session }) {
  const iv = s.intervention, d = iv.observed_difference, b1 = s.bodies['1'].versions[0], after = s.bodies[String(s.body_versions.after)], b2 = after.versions[after.versions.length - 1];
  const added = b2.components.filter((c) => !b1.components.some((x) => x.id === c.id)).map((c) => c.id);
  const col = (title: string, rec: TeooRecord | undefined, extra: string) => <div className="teoo-col"><h4>{title}</h4><div className="mono small">{rec?.record_id}</div><div className="small">{rec?.provenance} · {rec?.kind}</div><div className="small dim">{extra}</div></div>;
  return (
    <div data-testid="teoo-view-e">
      <div className="teoo-cols" data-testid="teoo-three">{col('OBSERVATION (before)', recordOf(s, iv.pre), `${d.n_pre} valid samples · mean ${d.mean_pre?.toFixed(2)}`)}{col('INTERVENTION', recordOf(s, iv.record_id), `a brace fitted at knee_l: body v${s.body_versions.before} → v${s.body_versions.after}`)}
        {col('OBSERVATION (after)', recordOf(s, iv.post), `${d.n_post} valid samples · mean ${d.mean_post?.toFixed(2)}`)}{col('COUNTERFACTUAL_MODEL', recordOf(s, iv.counterfactual), 'what a declared model says; not an observation')}</div>
      <table className="small teoo-table"><thead><tr><th></th><th>before</th><th>after</th></tr></thead><tbody>
        <tr><td>body configuration</td><td>v{s.body_versions.before}: {b1.components.length} components</td><td>v{s.body_versions.after}: {b2.components.length} components (added: {added.join(', ')})</td></tr>
        <tr><td>observation configuration</td><td colSpan={2}>unchanged by the intervention{d.observation_configuration_changed ? ' (it did change: the two records are not the same observation)' : ''}</td></tr></tbody></table>
      <div className="small" data-testid="teoo-observed-difference">Observed difference of <span className="mono">{d.variable}</span>: <b>{d.observed_difference?.toFixed(3)}</b> — <b>{d.reading}</b>.</div>
      <div className="small" data-testid="teoo-identification">Causal status: <b>{iv.identification.status}</b>. {iv.identification.statement}. Why not more: {iv.identification.why_not_causal.join('; ') || 'nothing missing'}.</div>
      <h4>The counterfactual model</h4>
      <div className="small">Scope: {iv.model.scope}. Assumptions: {iv.model.assumptions.join('; ')}. Identification: {iv.model.identification.join('; ')}.</div>
      <Note>An observed change is never recorded here as a causal effect. The counterfactual is the output of a declared model on a unit, not a measurement and not a result.</Note>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ F: reconstruction
export function ViewF({ s }: { s: Session }) {
  const est = recordOf(s, s.reconstruction.record_id)!, inp = recordOf(s, s.reconstruction.input_record_id)!, ch = channelOf(inp, s.reconstruction.variable)!;
  const rec = (est.payload as unknown as { reconstruction: { method: string; assumptions: string[]; value: { times: number[]; values: number[]; sd: number[] }; uncertainty: { sd: string }; interpolation: Array<{ method: string; from_t: number; to_t: number; note: string }>; time: { uncertainty_s: number | null; inputs_synchronised: boolean | null } } }).reconstruction;
  return (
    <div data-testid="teoo-view-f">
      <Plot ch={ch} est={rec.value} gap={s.reconstruction.lost.interval_s} />
      <table className="small teoo-table"><tbody>
        <tr><td>input</td><td className="mono">{inp.record_id}</td><td>{inp.provenance} {inp.kind}</td></tr>
        <tr><td>result</td><td className="mono">{est.record_id}</td><td>{est.provenance} {est.kind}; lineage {est.lineage_classes.join(' + ')}</td></tr>
        <tr><td>method</td><td colSpan={2}>{rec.method}</td></tr>
        <tr><td>assumptions</td><td colSpan={2}>{rec.assumptions.join('; ')}</td></tr>
        <tr><td>interpolation</td><td colSpan={2}>{rec.interpolation.map((i) => `${i.method} over ${i.from_t}–${i.to_t} s: ${i.note}`).join('; ')}</td></tr>
        <tr><td>uncertainty</td><td colSpan={2}>{rec.uncertainty.sd}; time uncertainty {rec.time.uncertainty_s === null ? 'unknown (the inputs are not synchronised), not zero' : rec.time.uncertainty_s}</td></tr></tbody></table>
      <div className="small" data-testid="teoo-lost"><b>Lost information:</b> {s.reconstruction.lost.statement} ({s.reconstruction.lost.n_samples} samples, {s.reconstruction.lost.interval_s[0]}–{s.reconstruction.lost.interval_s[1]} s).</div>
      <Note>A reconstruction is a computation from records, not an observation; it is never MEASURED, and the uncertainty shown is an assumption of the method.</Note>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ G: experimental evidence
export function ViewG({ s }: { s: Session }) {
  const p = s.protocol.protocol, run = s.protocol.run;
  return (
    <div data-testid="teoo-view-g">
      <table className="small teoo-table"><tbody>
        <tr><td>experiment</td><td className="mono">{p.experiment_id} v{p.version}</td><td>frozen before the first data; a changed condition is a new version (v{s.protocol.amended.version}: {s.protocol.amended.change_reason})</td></tr>
        <tr><td>hypotheses</td><td colSpan={2}>{p.hypotheses.map((h) => `${h.id}: ${h.statement}`).join(' | ')}</td></tr>
        <tr><td>conditions</td><td colSpan={2}>{p.conditions.join(', ')} (control: {p.control_condition}) · seeds {p.seeds.join(', ')} · {p.trials_per_condition} trials per condition and seed · stopping: {JSON.stringify(p.stopping_rule)}</td></tr>
        <tr><td>multiplicity</td><td colSpan={2}>{p.multiplicity}</td></tr>
        <tr><td>failure conditions</td><td colSpan={2}>{p.failure_conditions.join('; ')}</td></tr>
        <tr><td>reproduction</td><td colSpan={2}>generator {p.reproduction.generator}: <b data-testid="teoo-reproduced">{s.protocol.reproduction.identical ? 'reproduced identically' : 'NOT reproduced'}</b> (trials digest <span className="mono">{s.protocol.reproduction.trials_digest.slice(0, 12)}…</span>); the registry verifies: {String(s.protocol.registry_ok)}</td></tr></tbody></table>
      <h4>Analyses</h4>
      <table className="small teoo-table" data-testid="teoo-analyses"><thead><tr><th>analysis</th><th>class</th><th>effect</th><th>p</th><th>p (Holm)</th><th>inferential</th><th>lag-1 r</th><th>n</th></tr></thead>
        <tbody>{Object.entries(run.results).map(([id, r]) => <tr key={id}><td>{id}</td><td><b>{s.protocol.analysis_classes[id]}</b></td><td>{r.effect.toFixed(3)}</td><td>{r.p.toFixed(4)}</td><td>{run.adjusted[id].p_holm.toFixed(4)}</td><td>{String(r.inferential)}</td><td>{r.lag1_autocorrelation?.toFixed(2)}</td><td>{r.n_a} / {r.n_b}</td></tr>)}</tbody></table>
      <div className="small">{run.n_trials} trials · {run.generator_note}. First trials: {s.protocol.trials_head.slice(0, 4).map((x) => `seed ${x.seed} #${x.trial} ${x.condition} ${x.value.toFixed(2)}`).join(' · ')} …</div>
      <Note>Evidence class of every number here: SYNTHETIC (an artificial generator): this shows how an experiment is registered, run, analysed and replayed, and nothing about any body. A real-world experiment has not been carried out.</Note>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ H: total observation (integrated, levels kept)
export function ViewH({ s, t }: { s: Session; t: number }) {
  const rows = integratedRows(s, t), counts = LEVELS.map((l) => ({ ...l, n: rows.filter((r) => r.level === l.id).length }));
  return (
    <div data-testid="teoo-view-h">
      <ul className="small teoo-levels" data-testid="teoo-levels">{counts.map((l) => <li key={l.id} data-level={l.id}><b>{l.id}. {l.name}</b> <span className="dim">{l.note}</span> · {l.n}</li>)}</ul>
      <table className="small teoo-table" data-testid="teoo-integrated"><thead><tr><th>level</th><th>item</th><th>class</th><th>record</th><th>note</th></tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} data-level={r.level}><td><span className={`teoo-lv lv${r.level}`}>{r.level}</span> {LEVELS[r.level - 1].name}</td><td>{r.item}</td><td>{r.cls}</td><td className="mono">{r.record}</td><td>{r.note}</td></tr>)}</tbody></table>
      <Note>Views A–G in one table at t = {t} s. Every row keeps its level, its class and its record; an observation, an estimate, an intervention, a counterfactual and an unobserved difference are never added together. {s.observation.states[0].claim_note}</Note>
      <div className="small dim">{ids(Object.keys(s.record_index))}</div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ I: AI legal governance
export const GSTATE_COLOR: Record<string, string> = { SECURED: '#78e696', PARTIAL: '#c9a227', ABSENT: '#ff8a70', INDETERMINATE: '#9bb0d0', INAPPLICABLE: '#8a8a92', SATISFIED: '#78e696', PARTIALLY_SATISFIED: '#c9a227', VIOLATED: '#ff8a70', INSUFFICIENT_EVIDENCE: '#9bb0d0', NOT_APPLICABLE: '#8a8a92', NOT_EVALUATED: '#a58fd6' };
export const countStates = (a: Array<{ state: string }>): Record<string, number> => a.reduce<Record<string, number>>((m, x) => { m[x.state] = (m[x.state] ?? 0) + 1; return m; }, {});
const GChip = ({ s, hard }: { s: string; hard?: boolean }) => <span className="teoo-chip" style={{ borderColor: GSTATE_COLOR[s] ?? '#888' }} data-state={s}><i style={{ background: GSTATE_COLOR[s] ?? '#888' }} />{s}{hard ? ' · hard failure' : ''}</span>;
const pct = (x: number | null | undefined) => (x === null || x === undefined ? '-' : x.toFixed(3));

const DSTATE_COLOR: Record<string, string> = { SATISFIED: '#78e696', PARTIALLY_SATISFIED: '#c9a227', VIOLATED: '#ff8a70', INSUFFICIENT_EVIDENCE: '#9bb0d0', NOT_APPLICABLE: '#8a8a92', NOT_EVALUATED: '#a58fd6' };

function DutyTable({ mh, an, proj }: { mh: MhegBundle; an: string; proj: MhegBundle['projections'][string] }) {
  return (
    <>
      <table className="small teoo-table" data-testid="teoo-duties" data-institution={an}><thead><tr><th>#</th><th>duty</th><th>maps to (as reported)</th><th>state (its worst mapped finding)</th><th>driven by</th></tr></thead>
        <tbody>{mh.duties.map((d) => { const p = proj.duties[d.id]; return (
          <tr key={d.id} data-duty={d.id} data-state={p.state}><td>{d.id}</td>
            <td>{d.name} <span className="dim">· {d.label_ja}</span><details><summary className="dim">function · evaluation target · evidence · what cannot be verified</summary>
              <div><b>Function (this implementation's summary; {d.definition_status}):</b> {d.function}</div><div><b>Input (evaluated in the synthetic institution):</b> {d.input}</div><div><b>Evidence needed:</b> {d.required_evidence}</div><div><b>Authority subject:</b> {d.authority_subject}</div><div><b>Violation:</b> {d.violation_condition}</div><div><b>Indeterminate:</b> {d.indeterminate_condition}</div><div><b>Cannot be verified here:</b> {d.cannot_verify}</div>
              <div className="dim">{d.identity_with_guarantees}. {d.source}.</div></details></td>
            <td>{d.crosswalk_as_reported} <span className="dim">({d.mapping_kind})</span></td><td><DChip s={p.state} /></td><td className="small">{p.drivers.length ? p.drivers.join(', ') : '—'}</td></tr>); })}</tbody></table>
      <Note>A duty is shown as its worst mapped finding, never as an average or a total, and one failure is not offset by another. The twelve duties are a registry of their own; the guarantees do not replace them, and the correspondence says nothing about identity of definition.</Note>
    </>
  );
}

const DChip = ({ s }: { s: string }) => <span className="teoo-chip" style={{ borderColor: DSTATE_COLOR[s] ?? '#888' }} data-state={s}><i style={{ background: DSTATE_COLOR[s] ?? '#888' }} />{s}</span>;

function Crosswalk({ mh, proj }: { mh: MhegBundle; proj: MhegBundle['projections'][string] }) {
  const cw = mh.crosswalk;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="small teoo-table" data-testid="teoo-crosswalk"><thead><tr><th>duty</th>{cw.findings.map((f) => <th key={f}>{f}</th>)}</tr></thead>
        <tbody>{cw.duties.map((d) => <tr key={d} data-duty={d}><td>{d}</td>{cw.findings.map((f, j) => <td key={f} data-mapped={cw.matrix[d][j]} title={cw.matrix[d][j] ? `${d} maps ${f}: ${proj.findings[f].state}` : ''} style={{ textAlign: 'center' }}>{cw.matrix[d][j] ? <span style={{ color: DSTATE_COLOR[proj.findings[f].state] ?? '#888' }}>●</span> : <span className="dim">·</span>}</td>)}</tr>)}
          <tr data-testid="teoo-crosswalk-count"><td className="dim">duties naming it</td>{cw.findings.map((f) => <td key={f} style={{ textAlign: 'center' }} data-count={cw.duties_per_finding[f]}>{cw.duties_per_finding[f]}</td>)}</tr></tbody></table>
      <Note>{cw.note}. Findings named by exactly one duty: {cw.named_by_one_duty.join(', ')}; broad duties: {cw.broad_duties.join(', ')}. The crosswalk is as reported from the later correspondence table; it was not available to this implementation.</Note>
    </div>
  );
}

const Chip2 = ({ s: v }: { s: string }) => <span className="teoo-chip" style={{ borderColor: GSTATE_COLOR[v] ?? (v === 'ACCESS' ? '#c9a227' : v === 'METADATA' ? '#9bb0d0' : v === 'UNKNOWN' ? '#a58fd6' : v === 'CURRENT' ? '#78e696' : v.startsWith('STALE') ? '#ff8a70' : v === 'HISTORICAL' ? '#8a8a92' : v.startsWith('CLOSED') ? '#c9a227' : v === 'QUARANTINED' || v === 'REJECTED' ? '#ff8a70' : '#9bb0d0') }} data-state={v}>{v}</span>;

function LedgerReceipts({ lb }: { lb: LedgerBundle }) {
  const c = lb.demo.case, st = lb.demo.steps;
  return (
    <>
      <h4>I-E · Receipt and proceedings: receipt first, evidence second (a persistent, append-only SQLite ledger on a SYNTHETIC case)</h4>
      <div className="teoo-banner" role="note" data-testid="teoo-ledger-note">{lb.limits}. A receipt, a hash or a closure here creates no judicial or administrative authority (I12). {lb.note}.</div>
      <table className="small teoo-table" data-testid="teoo-receipts"><thead><tr><th>seq</th><th>case</th><th>claim</th><th>state</th><th>reason</th></tr></thead>
        <tbody>{c.receipts.map((r) => <tr key={r.receipt_seq} data-receipt={r.receipt_seq} data-state={r.state}><td>{r.receipt_seq}</td><td>{r.case_id}</td><td>{r.claim_id ?? '— none —'}</td><td><Chip2 s={r.state} /></td><td>{r.reason}</td></tr>)}</tbody></table>
      <div className="small" data-testid="teoo-receipt-counts">65 valid submissions to one case: <b>{lb.demo.counts_65.ACTIVE} ACTIVE</b>, <b>{lb.demo.counts_65.QUEUED} QUEUED</b>, none lost; the historical in-memory condition (64) is a condition of an experiment, not a rule of this ledger. Input above 65,536 bytes is refused and is not a receipt (nothing is implied about its durability).</div>
      <table className="small teoo-table" data-testid="teoo-proceedings"><thead><tr><th>proceeding</th><th>guarantee</th><th>kind</th><th>about</th><th>state</th></tr></thead>
        <tbody>{c.proceedings.map((p) => <tr key={p.id} data-proceeding={p.id}><td>{p.id}</td><td>{p.guarantee}</td><td>{p.kind}</td><td>{p.ref ?? '—'}</td><td><Chip2 s={p.state} /></td></tr>)}</tbody></table>
      <div className="small" data-testid="teoo-r9">The R9 separation: G1 evidence <Chip2 s={lb.demo.case_g1.E} /> · applicability <Chip2 s={lb.demo.case_g1.A} /> · proceedings {lb.demo.case_g1.W.join(', ') || 'none'} · effective state <Chip2 s={lb.demo.case_g1.effective} /> — an improper exception request does not erase the evidence, and G1 and G2 cannot be nullified by a general exception.</div>
      <details className="small" data-testid="teoo-steps"><summary>the path step by step ({st.length} steps)</summary><ol>{st.map((x) => <li key={x.step}>{x.what}: <span className="mono">{JSON.stringify(x.result)}</span></li>)}</ol></details>
      <ul className="small" data-testid="teoo-invariants">{Object.entries(lb.invariants).map(([k, v]) => <li key={k}><b>{k}</b> {v}</li>)}</ul>
    </>
  );
}

function LedgerEvidenceView({ lb }: { lb: LedgerBundle }) {
  const c = lb.demo.case;
  return (
    <>
      <h4>I-F · Evidence and revision: scope of a revision, immutable measurements and their status events</h4>
      <table className="small teoo-table" data-testid="teoo-evidence-events"><thead><tr><th>evidence</th><th>guarantee</th><th>version</th><th>scope</th><th>container</th><th>state</th><th>source</th></tr></thead>
        <tbody>{c.evidence.map((e) => <tr key={e.id} data-evidence={e.id} data-scope={e.scope}><td>{e.id}</td><td>{e.guarantee}</td><td>v{e.version}</td><td><Chip2 s={e.scope} /></td><td>{e.valid ? 'valid' : 'INVALID'}</td><td><Chip2 s={e.e_state} /></td><td>{e.source}</td></tr>)}</tbody></table>
      <Note>ACCESS: invalidates observations that depend on access and requires reobservation. METADATA: in the constructed model, the earlier access observation stays valid (unexecuted plans still become stale). UNKNOWN: invalidated conservatively. These scopes are set by the experimenter in the synthetic experiments; that the software could judge legal relevance by itself is not shown, and a real metadata change must not be taken as legally irrelevant.</Note>
      <table className="small teoo-table" data-testid="teoo-measurements"><thead><tr><th>measurement</th><th>evidence</th><th>execution</th><th>revision</th><th>mode</th><th>model / sensor</th><th>q</th><th>status history (events, never overwritten)</th></tr></thead>
        <tbody>{c.measurements.map((m) => <tr key={m.id} data-measurement={m.id} data-status={m.status}><td>{m.measure_id}<div className="dim">{m.model_obs_id}</div></td><td>{m.evidence_event_id}</td><td>{m.execution_id ?? '—'}</td><td>{m.world_revision}</td><td>{m.mode}</td><td>{String(m.model)} / {String(m.sensor)}{m.mismatch ? ' · DISAGREE' : ''}</td><td>{m.q === null ? 'not observed' : String(m.q)}</td>
          <td>{m.status_history.map((h, i) => <span key={i} style={{ marginRight: 6 }}><Chip2 s={h.status} /><span className="dim"> t{h.tick}</span></span>)}</td></tr>)}</tbody></table>
      <div className="small" data-testid="teoo-events-kept">rows kept: {Object.entries(lb.demo.events_kept).map(([k, v]) => `${k} ${v}`).join(' · ')}</div>
    </>
  );
}

function ModelSensor({ lb }: { lb: LedgerBundle }) {
  const w = lb.world;
  return (
    <>
      <h4>I-G · Model against synthetic sensor: {w.states} states x {w.conditions.length} conditions = {w.comparisons} comparisons (this implementation's own world)</h4>
      <table className="small teoo-table" data-testid="teoo-world"><thead><tr><th>condition</th><th>model access</th><th>sensor access</th><th>disagreements</th><th>cause seen: EXPANDED</th><th>cause seen: ACCESS_ONLY</th></tr></thead>
        <tbody>{w.conditions.map((k) => <tr key={k} data-condition={k}><td>{k}</td><td>{w.per_condition[k].model_access}</td><td>{w.per_condition[k].sensor_access}</td><td>{w.per_condition[k].disagreements}</td><td>{w.per_condition[k].cause_identified_expanded}</td><td>{w.per_condition[k].cause_identified_access_only}</td></tr>)}</tbody></table>
      <Note>A disagreement is not a found cause: where the hidden condition q (stipulated by the experimenter, not discovered by the device) is not the reason, even EXPANDED leaves it unexplained. An ordinary Boolean model with the same information agrees with the world on <b data-testid="teoo-boolean-agree">{w.boolean_model_agrees} / {w.comparisons}</b> (model) and {w.boolean_sensor_agrees} / {w.comparisons} (sensor): no predictive advantage of the ledger or of its vocabulary is shown. {w.note}.</Note>
    </>
  );
}

function Restoration({ lb }: { lb: LedgerBundle }) {
  const r = lb.demo.case.restoration, cl = lb.demo.case.closures;
  return (
    <>
      <h4>I-H · Intervention and restoration: six independent records, and administrative closure kept apart from legal determination and restoration</h4>
      <table className="small teoo-table" data-testid="teoo-restoration"><thead><tr><th>record</th><th>present</th><th>n</th></tr></thead>
        <tbody>{r.stages.map((x) => <tr key={x.stage} data-stage-record={x.stage} data-present={x.present}><td>{x.stage.replace(/_/g, ' ')}</td><td>{x.present ? 'yes' : 'NO'}</td><td>{x.n}{x.current !== undefined ? ` (${x.current} current)` : ''}</td></tr>)}</tbody></table>
      <div className="small" data-testid="teoo-closures">{cl.length ? cl.map((c) => <span key={c.id} style={{ marginRight: 12 }}><Chip2 s={c.kind} /> <span className="mono">{c.flag}</span></span>) : 'no closure'} · legal determination by this software: <b>none</b> · material restoration verified: <b>{String(r.material_restoration_verified)}</b> · positive law verified: <b>{String(r.positive_law_verified)}</b> · access changed in the synthetic world: {String(r.access_changed_in_the_synthetic_world)}</div>
      <Note>Administrative closure (the internal review work is over), evidential resolution, a legal determination by a competent authority and material restoration are four different things; none stands for another, and a model match is not legal verification.</Note>
    </>
  );
}

function ExperimentsPanel({ lb }: { lb: LedgerBundle }) {
  return (
    <>
      <h4>I-I · Experimental evidence: R5-R16 and the new LAW experiments</h4>
      <table className="small teoo-table" data-testid="teoo-r-table"><thead><tr><th>R</th><th>what</th><th>implemented</th><th>where</th><th>experiment</th><th>status</th></tr></thead>
        <tbody>{lb.r_table.map((x) => <tr key={x.r} data-r={x.r} data-status={x.status}><td>{x.r}</td><td>{x.what}</td><td>{x.implemented}{x.note ? ` — ${x.note}` : ''}</td><td className="mono">{x.where}</td><td>{x.experiment}</td><td>{x.status}</td></tr>)}</tbody></table>
      <table className="small teoo-table" data-testid="teoo-law-results"><thead><tr><th>experiment</th><th>analysis</th><th>question</th><th>result</th></tr></thead>
        <tbody>{lb.results.flatMap((e) => Object.entries(e.analyses).map(([a, v]) => <tr key={a} data-analysis={a} data-ok={String(v.supported ?? v.criterion_met)}><td>{e.id} <span className="dim">({e.class})</span></td><td>{a}{v.confirmatory ? '' : ' · exploratory'}</td><td>{v.hypothesis}</td>
          <td>{v.supported !== null ? (v.supported ? `supported (p_Holm ${v.p_holm?.toExponential(1)})` : 'NOT supported') : v.criterion_met ? 'criterion met' : 'criterion NOT met'}</td></tr>))}</tbody></table>
      <ul className="small" data-testid="teoo-law-negative">{lb.negative_and_unmet.map((n) => <li key={n.experiment + n.analysis}><b>{n.experiment} {n.analysis}</b> — {n.hypothesis}</li>)}</ul>
    </>
  );
}

export function ViewI({ b }: { b: LegalBundle }) {
  const names = Object.keys(b.assessments), chains = Object.keys(b.chains);
  const [an, setAn] = useState(names[0]), [cn, setCn] = useState(chains[0]), [mn, setMn] = useState(Object.keys(b.mheg.chains)[0]);
  const mh = b.mheg, proj = mh.projections[an], mchain = mh.chains[mn], a = b.assessments[an], meta = b.audits[an], chain = b.chains[cn], counts = countStates(a);
  const notSecured = a.filter((x) => x.state === 'ABSENT' || x.state === 'PARTIAL' || x.state === 'INDETERMINATE');
  const tax = meta.outcome_taxonomy;
  return (
    <div data-testid="teoo-view-i">
      <div className="teoo-banner" role="note" data-testid="teoo-catalogue-notice">Source: <span className="mono">{b.catalogue.source}</span>. Guarantee titles below are the source titles, {b.catalogue.verified_against_original ? 'verified against the original files' : 'NOT verified against the original'}
        {b.catalogue.editions_identical_for_guarantees ? ' (identical in V3.0, the 100_POINT_EDITION and R2)' : ''}; {b.text_available ? 'the source wording is shown from the attached private store' : 'the source wording (definitions, audit questions) is held privately and is not part of this build'}; the <b>operational definitions</b> (how a synthetic institution yields evidence for a finding) and the recommendation rule are this implementation's, not the source's. {b.catalogue.note}</div>
      <div className="teoo-controls"><label>institution <select value={an} onChange={(e) => setAn(e.target.value)} data-testid="teoo-legal-assessment">{names.map((n) => <option key={n}>{n}</option>)}</select></label>
        <span className="small" data-testid="teoo-state-counts">{b.states.map((s) => <span key={s} style={{ marginRight: 10 }}><GChip s={s} /> {counts[s] ?? 0}</span>)} <span className="dim">(counted, never added into a score)</span></span></div>
      <h4>I-A · Legal subjecthood: fifteen guarantees, one finding each</h4>
      <table className="small teoo-table" data-testid="teoo-guarantees"><thead><tr><th>#</th><th>guarantee (source title)</th><th>finding</th><th>evidence</th><th>reason</th></tr></thead>
        <tbody>{a.map((x) => (
          <tr key={x.number} data-guarantee={x.number} data-state={x.state}><td>{x.number}</td>
            <td>{x.title}<details><summary className="dim">source definition · operational definition · audit questions{x.sub_findings.length ? ' · sub-findings' : ''}</summary>
              <div data-testid={`teoo-def-${x.number}`}><b>Source (V3.0 §6.2, body item {x.source_position}):</b> {x.definition ?? `wording held privately (${x.audit_question_count} audit questions in V3.0 A.4)`}</div>
              <div><b>Operational definition in the synthetic institution (this implementation's):</b> {x.operational_definition}</div>
              <ul>{x.audit_questions.map((q) => <li key={q}>{q}</li>)}</ul>
              {x.sub_findings.map((s) => <div key={s.id} data-subfinding={s.id}><b>{s.id}</b> <GChip s={s.state} hard={s.hard_failure} /> {b.sub_finding_definitions[s.id]} <span className="dim">— {s.reason}</span></div>)}</details></td>
            <td><GChip s={x.state} hard={x.hard_failure} /></td><td className="small">{x.sub_findings.length ? x.sub_findings.map((s) => `${s.id} T${s.evidence_tier ?? '?'}`).join(' · ') : (x.evidence_missing.length ? 'missing' : 'logs / records')}</td>
            <td>{x.reason}{x.adverse_inference_available ? ' (the institution controls this evidence: adverse inference available)' : ''}</td></tr>))}</tbody></table>
      <div className="small" data-testid="teoo-u"><b>U — the Low-Score Subject Guarantee Principle</b> (a transversal rule, reported separately; not a sixteenth guarantee): <GChip s={meta.U.state} hard={meta.U.hard_failure} /> {meta.U.reason}{meta.U.untested.length ? ` (untested: ${meta.U.untested.join(', ')})` : ''}</div>
      <h4>I-A · Legal subjecthood: outcome taxonomy (V3.0 §8.6) and the advisory recommendation</h4>
      <ul className="small" data-testid="teoo-taxonomy">{['constitutive_failure', 'procedural_failure', 'remedial_failure', 'systemic_failure', 'indeterminate_findings'].map((k) => <li key={k}><b>{k.replace(/_/g, ' ')}:</b> {(tax[k] as string[]).join(', ') || 'none'}</li>)}</ul>
      <div className="small" data-testid="teoo-recommendation">Candidate for the competent human decision maker: <b>{meta.recommendation.candidate}</b> — advisory only; decided by {meta.recommendation.decided_by}; rule: {meta.recommendation.rule_source}. {meta.no_total}</div>
      <h4>I-B · MHEG twelve duties (the earlier operational formulation; a registry of its own, not replaced by the guarantees)</h4>
      <DutyTable mh={mh} an={an} proj={proj} />
      <h4>I-B · Functional crosswalk: twelve duties to the fifteen guarantees (functional, not one-to-one; colours are the selected institution's findings)</h4>
      <Crosswalk mh={mh} proj={proj} />
      <h4>I-C · Governance principles: the fifteen AI-legal-logic principles (a separate historical series)</h4>
      <div className="teoo-banner" role="note" data-testid="teoo-governance">Status: <b>{mh.governance_principles.status}</b> — {mh.governance_principles.rule}. Reported source: {mh.governance_principles.reported_source}. To check when the source is available: {mh.governance_principles.to_check_when_available.join('; ')}.</div>
      <table className="small teoo-table" data-testid="teoo-principles"><thead><tr><th>#</th><th>principle</th><th>version</th><th>name status</th></tr></thead>
        <tbody>{mh.governance_principles.items.map((p) => <tr key={p.id} data-principle={p.id} data-known={p.name_status !== 'UNVERIFIED'}><td>{p.id}</td><td>{p.name ?? <span className="dim">unverified: not shown</span>}{p.scope ? <div className="dim">{p.scope}</div> : null}</td><td>{p.version ?? '—'}</td><td>{p.name_status}</td></tr>)}</tbody></table>
      {mh.governance_principles.proximity.map((x) => <div key={x.principle + x.guarantee} className="small" data-testid="teoo-proximity">{x.principle} and {x.guarantee}: {x.relation}; verified: {String(x.verified)}.</div>)}
      <h4>I-D · Legal transformation: the chain of nine stages</h4>
      <div className="teoo-controls"><label>institution <select value={mn} onChange={(e) => setMn(e.target.value)} data-testid="teoo-transform-select">{Object.keys(mh.chains).map((n) => <option key={n}>{n}</option>)}</select></label>
        <span className="small" data-testid="teoo-transform-verdict">{mchain.effective_to_the_end ? 'every stage operates' : `first violated stage: ${mchain.first_violated_stage ?? 'none (some stage is not satisfied)'}`}{mchain.information_lost_in_translation.length ? ` · information lost in translation: ${mchain.information_lost_in_translation.join(', ')}` : ''}</span></div>
      <table className="small teoo-table" data-testid="teoo-transform"><thead><tr><th>stage</th><th>operating condition</th><th>authority</th><th>state</th><th>observability</th><th>time span</th><th>resources</th><th>recovery path</th></tr></thead>
        <tbody>{mchain.stages.map((s) => <tr key={s.id} data-stage={s.id} data-state={s.state}><td>{s.label}<div className="dim">{Object.keys(s.findings).join(', ')}</div></td><td>{s.operating_condition}</td><td>{s.authority_relation}</td><td><GChip s={s.state} /></td><td>{s.observability}</td><td>{s.time_span}</td><td>{s.resource_condition}</td><td>{s.recovery_path.join('; ') || '—'}</td></tr>)}</tbody></table>
      <Note>{mchain.rule}. {mchain.stage_assignment}.</Note>
      <h4>I-D · Legal transformation: the typed chain of R2 (§15, §24)</h4>
      <div className="teoo-controls"><label>decision <select value={cn} onChange={(e) => setCn(e.target.value)} data-testid="teoo-legal-chain">{chains.map((n) => <option key={n}>{n}</option>)}</select></label>
        <span className="small" data-testid="teoo-chain-verdict">legally valid decision: <b>{chain.assessment.valid_legal_decision ? 'yes' : 'no'}</b>{chain.assessment.first_invalid_stage ? ` · first invalid stage: ${chain.assessment.first_invalid_stage}` : ''}</span></div>
      <table className="small teoo-table" data-testid="teoo-chain"><thead><tr><th>stage</th><th>layer</th><th>legal basis</th><th>jurisdiction / version</th><th>responsible</th><th>authority</th><th>route to contest</th><th>valid</th><th>why not</th></tr></thead>
        <tbody>{chain.chain.map((s, i) => <tr key={s.stage} data-valid={chain.assessment.stages[i].valid}><td>{s.stage.replace(/_/g, ' ')}</td><td>{s.layer}</td><td>{s.legal_basis ?? '— none —'}</td><td>{s.jurisdiction ?? '—'} / {s.rule_version ?? '—'}</td><td>{s.responsible}{s.by_ai ? ' (AI)' : ''}</td><td>{s.authority ?? '—'}</td><td>{s.contest_path ?? '—'}</td>
          <td>{chain.assessment.stages[i].valid ? 'yes' : 'NO'}</td><td>{chain.assessment.stages[i].why_not.join('; ')}</td></tr>)}</tbody></table>
      <h4>I-D · Legal transformation: Translation Register (the evidence for G6 and G7)</h4>
      <table className="small teoo-table" data-testid="teoo-register"><thead><tr><th>configuration</th><th>variable</th><th>legal source</th><th>proxy for</th><th>threshold</th><th>translation loss disclosed</th></tr></thead>
        <tbody>{Object.entries(b.register).flatMap(([k, rows]) => rows.map((r) => <tr key={k + r.variable}><td>{k}</td><td>{r.variable}</td><td>{r.legal_source ?? '— none identified —'}</td><td>{r.proxy_for ?? '—'}</td><td>{r.threshold ?? '—'}</td><td>{r.translation_loss_disclosed ? 'yes' : 'NO'}</td></tr>))}</tbody></table>
      <h4>I-D · Legal transformation: Ontological Score Inheritance test (100_POINT_EDITION A.6.1)</h4>
      <ul className="small" data-testid="teoo-inheritance">{Object.entries(b.inheritance).map(([k, v]) => <li key={k}><b>{k}:</b> {v.finding}{v.endogenous_share !== undefined ? ` · treatment-produced share of the score ${pct(v.endogenous_share)}` : ''}{v.reason ? ` — ${v.reason}` : ''}</li>)}</ul>
      <LedgerReceipts lb={b.ledger} />
      <LedgerEvidenceView lb={b.ledger} />
      <ModelSensor lb={b.ledger} />
      <h4>I-H · Intervention and restoration: interventions on the synthetic institution (same world, same seed)</h4>
      <table className="small teoo-table" data-testid="teoo-interventions"><thead><tr><th>intervention</th><th>qualified people excluded</th><th>persistence of exclusion</th><th>true-positive gap</th><th>group gap</th><th>downstream access</th><th>wrongful denials overturned</th><th>burden: subject / institution</th></tr></thead>
        <tbody>{Object.entries(b.interventions).map(([k, v]) => <tr key={k}><td>{k}</td><td>{pct(v.exclusion_qualified)}</td><td>{pct(v.exclusion_persistence)}</td><td>{pct(v.tpr_gap)}</td><td>{pct(v.group_exclusion_gap)}</td><td>{pct(v.downstream_access_qualified)}</td><td>{pct(v.overturn_rate_of_wrongful)}</td><td>{pct(v.burden_subject)} / {pct(v.burden_institution)}</td></tr>)}</tbody></table>
      <Note>Read across the rows: fairness optimisation narrows the true-positive gap and leaves exclusion in place; deleting the score lets the proxy take its place; only a review that is independent and has authority overturns wrongful denials.</Note>
      <h4>I-H · Intervention and restoration: remedy paths and the last stages of the chain</h4>
      <ul className="small" data-testid="teoo-remedies">{notSecured.length === 0 ? <li>every applicable finding is SECURED in this institution</li> : notSecured.map((x) => <li key={x.number}><b>{x.number}. {x.title}</b> — {x.remedy_path}</li>)}</ul>
      <div className="small" data-testid="teoo-contest-restore">{['contestation', 'revision', 'material_restoration'].map((id) => { const st = mchain.stages.find((x) => x.id === id); return st ? <span key={id} style={{ marginRight: 14 }}>{st.label}: <GChip s={st.state} /></span> : null; })} <span className="dim">(chain of {mn.slice(0, 40)}…)</span></div>
      <Restoration lb={b.ledger} />
      <ExperimentsPanel lb={b.ledger} />
      <h4>I-I · Experimental evidence: unverified conditions and what this view cannot observe</h4>
      <ul className="small" data-testid="teoo-unverified">{mh.unverified.map((u) => <li key={u}>{u}</li>)}</ul>
      <details className="small" data-testid="teoo-fidelity"><summary>what this implementation checks of each finding, what it does not, and what no software can verify</summary>
        <table className="small teoo-table"><thead><tr><th>finding</th><th>checked</th><th>not implemented</th><th>normative, not verifiable here</th></tr></thead>
          <tbody>{Object.entries(mh.fidelity).map(([f, v]) => <tr key={f}><td>{f}</td><td>{v.implemented}</td><td>{v.not_implemented}</td><td>{v.normative_unverifiable}</td></tr>)}</tbody></table>
        <div>itemised components: {Object.entries(mh.components).map(([f, c]) => `${f} (${c.length})`).join(' · ')}</div></details>
      <div className="small" data-testid="teoo-legal-observation">Findings observed in the partial audit: {b.observation.observed_findings.length} of 19 (G1–G11, G12A, G12B, G13, G14, G15A–D); not observed: <span className="mono">{b.observation.not_observed_findings.join(', ')}</span>. {b.observation.note}.</div>
      <Note>{b.software_limit}</Note>
      <Note>{b.scope}</Note>
    </div>
  );
}
