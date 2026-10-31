import { useMemo } from 'react';
import type { TeooBody, TeooChannel, TeooRecord } from './bodyApi';
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
