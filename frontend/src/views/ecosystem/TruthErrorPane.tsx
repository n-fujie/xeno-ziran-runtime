import { useMemo } from 'react';
import { ADDRESS_STATES, APPEAL_STAGES, COMPLEMENT_METRIC_IDS, MODALITIES, NODES, PATHS, RELATIONS, addressStatesAt, compareRelation, compareRuns, comparePaths, endogenyAt, eventTable, fieldsAt, modalityCounts, nodeReadings, timelineEvents, type NodeId, type Reading, type RelationId, type TERun } from './truthError';
import type { TEExperiment, TEOverrides } from './truthApi';

// TRUTH-ERROR DYNAMICS — a research tab of the XENO ECOSYSTEM view. It runs a SYNTHETIC virtual institution (backend/xzr/truth_error) and reads the run: nothing here classifies, scores or simulates, and every value is
// read from the engine's record. No real person, face, credit or eligibility is assessed; a head pose is a measurement with an error and is never an indicator of truthfulness, character or creditworthiness. The stages
// (measurement, classification, warrant, acceptance, score, access, resources, correction) are shown as separate records and are never reduced to one right/wrong variable.

export interface TruthCtx {
  base: TERun | null; branch: TERun | null; k: number; setK: (k: number) => void; t: number; setT: (t: number) => void; selected: NodeId | null; select: (id: NodeId | null) => void; relation: RelationId | null; setRelation: (id: RelationId | null) => void;
  draft: TEOverrides; setDraft: (d: TEOverrides) => void; busy: boolean; err: string | null; runBase: () => Promise<void>; runBranch: () => Promise<void>; clearBranch: () => void; focus3d: () => void;
  experiments: Record<string, TEExperiment> | null; expId: string; setExpId: (id: string) => void; experiments2: Record<string, TEExperiment> | null; exp2Id: string; setExp2Id: (id: string) => void; loadArm: (expId: string, arm: string, as: 'base' | 'branch') => Promise<void>;
}

const CLASSIFIERS = ['signal_rule', 'pose_rule', 'random_rule', 'none'];
const PRIMARY_METRICS = ['access_rate_late_fav', 'denial_rate_late_fav', 'lost_opportunities_per_fav', 'recovery_time', 'recovery_censored_share', 'persistent_constraint', 'propagation_b_denied_fav'] as const;
const n3 = (x: number | null | undefined): string => (x === null || x === undefined ? '-' : x.toFixed(3));
const STATUS_TEXT: Record<string, string> = { SAME: 'same', EARLIER: 'earlier in the branch', LATER: 'later in the branch', ONLY_IN_BRANCH: 'only in the branch', ONLY_IN_BASELINE: 'only in the baseline', NEITHER: 'in neither' };
const chip = (e: string) => <span className={`eco-chip tee-${e}`}>{e}</span>;
const ReadingTable = ({ rows, testid }: { rows: Reading[]; testid?: string }) => <table className="eco-table" data-testid={testid}><tbody>{rows.map((r, i) => <tr key={i}><td>{r.label}</td><td>{chip(r.epistemic)}</td><td>{r.value}</td></tr>)}</tbody></table>;

/** The pose of one subject over time: the reference (solid) and the sensor's measurement (dashed, with a gap where nothing was obtained), one panel per axis. Axes in degrees. */
function PoseTrace({ run, k }: { run: TERun; k: number }) {
  const rs = run.records[k], W = 280, H = 44, ranges = [40, 25, 15];
  return (
    <div data-testid="te-pose-trace">
      {['yaw', 'pitch', 'roll'].map((ax, a) => {
        const x = (i: number) => (i / Math.max(1, rs.length - 1)) * W, y = (v: number) => H / 2 - (v / ranges[a]) * (H / 2 - 3);
        const ref = rs.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r.pose_reference[a]).toFixed(1)}`).join('');
        let meas = '', pen = false;
        rs.forEach((r, i) => { const v = r.pose_measured[a]; if (v === null) { pen = false; return; } meas += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; });
        return <svg key={ax} viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`${ax}: reference and measured`} style={{ display: 'block' }}><line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="currentColor" strokeOpacity="0.2" /><path d={ref} fill="none" stroke="currentColor" strokeWidth="1.4" /><path d={meas} fill="none" stroke="#e0a030" strokeWidth="1.2" strokeDasharray="3 2" /><text x="2" y="9" fontSize="8" fill="currentColor">{ax} (±{ranges[a]}°)</text></svg>;
      })}
    </div>
  );
}

export default function TruthErrorPane(c: TruthCtx) {
  const { base, branch, k, t } = c;
  const cmp = useMemo(() => (base && branch ? compareRuns(base, branch) : null), [base, branch]);
  const fields = useMemo(() => (base ? fieldsAt(base, k, t) : null), [base, k, t]);
  const events = useMemo(() => (base ? timelineEvents(base, k) : []), [base, k]);
  const branchEvents = useMemo(() => (branch ? timelineEvents(branch, k) : []), [branch, k]);
  const addr = useMemo(() => (base ? addressStatesAt(base, t) : null), [base, t]);
  const rec = base ? base.records[k][Math.min(t, base.records[k].length - 1)] : null;
  const bRec = branch ? branch.records[k][Math.min(t, branch.records[k].length - 1)] : null;
  const exp = c.experiments?.[c.expId] ?? null;
  const set = (patch: TEOverrides) => c.setDraft({ ...c.draft, ...patch });
  const sensor = (patch: Partial<NonNullable<TEOverrides['pose_sensor']>>) => c.setDraft({ ...c.draft, pose_sensor: { ...c.draft.pose_sensor, ...patch } });
  const periods = base?.config.periods ?? 40;
  const paths = useMemo(() => (base ? comparePaths(base, branch, k) : []), [base, branch, k]);
  const exp2 = c.experiments2?.[c.exp2Id] ?? null;
  const proc = base?.process ?? null, bproc = branch?.process ?? null;
  const endo = useMemo(() => (base ? endogenyAt(base, branch, k, t) : null), [base, branch, k, t]);

  return (
    <>
      <h3>Truth-error dynamics (synthetic)</h3>
      <div className="eco-note" data-testid="te-scope">SYNTHETIC subjects and institutions only. No real person, face, credit, employment or housing is assessed, and this must not be used for that. A head pose (yaw, pitch, roll) is a measurement with an error: it is not an indicator of truthfulness, sincerity, character, ability to repay or creditworthiness, and the head-pose classifier here is invalid by construction. {REFERENCE_TEXT}</div>
      {c.err && <div className="eco-err">{c.err}</div>}

      <h3>Runs</h3>
      <div className="eco-row" data-testid="te-controls">
        <label>classifier <select value={c.draft.classifier ?? 'signal_rule'} onChange={(e) => set({ classifier: e.target.value })}>{CLASSIFIERS.map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>threshold <input type="number" step="0.05" value={c.draft.tau_a ?? 0} onChange={(e) => set({ tau_a: Number(e.target.value) })} style={{ width: 64 }} /></label>
        <label>score <select value={c.draft.use_score === false ? 'off' : 'on'} onChange={(e) => set({ use_score: e.target.value === 'on' })}><option>on</option><option>off</option></select></label>
        <label>correction at <select value={String(c.draft.correct_at ?? 'none')} onChange={(e) => set({ correct_at: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '10', '18', '26', '34'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>transfer at <select value={String(c.draft.transfer_at ?? 'none')} onChange={(e) => set({ transfer_at: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '12', '20'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>propagate correction <select value={c.draft.propagate_correction ? 'yes' : 'no'} onChange={(e) => set({ propagate_correction: e.target.value === 'yes' })}><option>no</option><option>yes</option></select></label>
        <label>binding constraint after <select value={String(c.draft.lock_after ?? 'none')} onChange={(e) => set({ lock_after: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '3', '4', '6'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>resources change the state (beta) <select value={String(c.draft.beta ?? 0)} onChange={(e) => set({ beta: Number(e.target.value) })}>{['0', '0.03', '0.06', '0.12'].map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <div className="eco-row" data-testid="te-sensor-controls" role="group" aria-label="pose sensor conditions">
        <label>view angle <select value={String(c.draft.pose_sensor?.view_angle ?? 0)} onChange={(e) => sensor({ view_angle: Number(e.target.value) })}>{['0', '20', '40', '60'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>noise <select value={String(c.draft.pose_sensor?.noise_sigma ?? 1.5)} onChange={(e) => sensor({ noise_sigma: Number(e.target.value) })}>{['1.5', '4', '8'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>occlusion <select value={String(c.draft.pose_sensor?.occlusion_prob ?? 0)} onChange={(e) => sensor({ occlusion_prob: Number(e.target.value) })}>{['0', '0.15', '0.3'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>calibration bias (yaw) <select value={String(c.draft.pose_sensor?.bias?.[0] ?? 0)} onChange={(e) => sensor({ bias: [Number(e.target.value), 0, 0] })}>{['0', '5', '10'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>inject a failure at <select value={String(c.draft.pose_sensor?.fail_at ?? 'none')} onChange={(e) => sensor({ fail_at: e.target.value === 'none' ? null : Number(e.target.value), fail_mode: 'stuck' })}>{['none', '15', '30'].map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <div className="eco-row" data-testid="te-process-controls" role="group" aria-label="correction process and appeal">
        <label>audit every <select value={String(c.draft.audit_every ?? 'none')} onChange={(e) => set({ audit_every: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '1', '2', '4'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>request delay <select value={String(c.draft.request_delay ?? 0)} onChange={(e) => set({ request_delay: Number(e.target.value) })}>{['0', '1', '3'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>approval delay <select value={String(c.draft.approval_delay ?? 0)} onChange={(e) => set({ approval_delay: Number(e.target.value) })}>{['0', '2', '8', '16'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>release <select value={c.draft.release_mode ?? 'by_score'} onChange={(e) => set({ release_mode: e.target.value })}>{['by_score', 'after_approval', 'never'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>release delay <select value={String(c.draft.release_delay ?? 0)} onChange={(e) => set({ release_delay: Number(e.target.value) })}>{['0', '4', '8', '16'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>appeal <select value={c.draft.appeal ? (c.draft.appeal_access === 'score_gated' ? 'gated by the score' : 'open') : 'none'} onChange={(e) => set({ appeal: e.target.value !== 'none', appeal_access: e.target.value === 'gated by the score' ? 'score_gated' : 'open', appeal_min_score: 0 })}>{['none', 'open', 'gated by the score'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>opportunity window <select value={String(c.draft.opportunity_window ?? 'none')} onChange={(e) => set({ opportunity_window: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '2', '6', '12'].map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <div className="eco-note">The correction process is the audit, the request, the approval, the score update and the release, each at its own time; the correction time (approval delay) and the release time (release delay) are set apart. The appeal gated by the score is a hypothetical control for studying institutional design danger: it is not a procedure for judging any real person.</div>
      <div className="eco-row" data-testid="te-guarantee-controls" role="group" aria-label="hypothetical guarantee and support conditions">
        <label>resource floor <select value={String(c.draft.resource_floor ?? 0)} onChange={(e) => set({ resource_floor: Number(e.target.value) })}>{['0', '0.15', '0.3'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>cap on a run of denials <select value={String(c.draft.denial_cap ?? 'none')} onChange={(e) => set({ denial_cap: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '3', '6'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>access kept pending a correction <select value={c.draft.interim_access ? 'yes' : 'no'} onChange={(e) => set({ interim_access: e.target.value === 'yes' })}><option>no</option><option>yes</option></select></label>
        <label>recovery support after a release <select value={String(c.draft.release_support ?? 0)} onChange={(e) => set({ release_support: Number(e.target.value) })}>{['0', '0.15', '0.3'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>support to <select value={c.draft.support_rule ?? 'none'} onChange={(e) => set({ support_rule: e.target.value })}>{['none', 'denied', 'low_score', 'on_request'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>chance of applying <select value={String(c.draft.support_apply_prob ?? 0.5)} onChange={(e) => set({ support_apply_prob: Number(e.target.value) })}>{['0.2', '0.5', '1'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>resources needed to apply <select value={String(c.draft.apply_min_resources ?? 0)} onChange={(e) => set({ apply_min_resources: Number(e.target.value) })}>{['0', '0.1', '0.3'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>support amount <select value={String(c.draft.support_amount ?? 0.1)} onChange={(e) => set({ support_amount: Number(e.target.value) })}>{['0.06', '0.1', '0.12'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>support capacity <select value={String(c.draft.support_capacity ?? 'none')} onChange={(e) => set({ support_capacity: e.target.value === 'none' ? null : Number(e.target.value) })}>{['none', '0.1', '0.25'].map((x) => <option key={x}>{x}</option>)}</select></label>
        <label>classifier accuracy (signal noise) <select value={String(c.draft.signal_sensor?.noise_sigma ?? 0.8)} onChange={(e) => c.setDraft({ ...c.draft, signal_sensor: { ...c.draft.signal_sensor, noise_sigma: Number(e.target.value) } })}>{['0.05', '0.4', '0.8', '1.6'].map((x) => <option key={x}>{x}</option>)}</select></label>
      </div>
      <div className="eco-note">These guarantee and support conditions are HYPOTHETICAL research conditions of the synthetic institution. The manuscripts' guarantees (Minimum Guarantees V3.0, G2, G13, G14, G15) are functions without numeric levels, so no number here is theirs; none is a procedure for judging any real person. Whether a condition helps is the question: it is read against the baseline, with its cost.</div>
      <div className="eco-row">
        <button disabled={c.busy} onClick={() => void c.runBase()}>RUN BASELINE</button>
        <button disabled={c.busy || !base} onClick={() => void c.runBranch()} title="the baseline with the settings above applied">RUN BRANCH (SETTINGS ABOVE)</button>
        <button disabled={!branch} onClick={c.clearBranch}>FORGET THE BRANCH</button>
        <button disabled={!base} onClick={c.focus3d} title="move the camera to the chain in the scene">SHOW THE CHAIN IN THE SCENE</button>
      </div>
      {!base && <div className="eco-note">Run a baseline first: the fields below are read from its record. The baseline is the default institution with a binding constraint after 4 denied periods, a correction at period 18 and a transfer at period 12 (illustrative values).</div>}

      {base && rec && fields && (
        <>
          <div className="eco-row" data-testid="te-select">
            <label>sample subject <select value={k} onChange={(e) => c.setK(Number(e.target.value))}>{base.records.map((_, i) => <option key={i} value={i}>{i + 1}</option>)}</select></label>
            <label>period <input type="range" min={0} max={periods - 1} value={t} onChange={(e) => c.setT(Number(e.target.value))} aria-label="period" /> <span>{t}</span></label>
          </div>
          <div className="eco-note">Subject {k + 1} of {base.records.length} kept in full, at period {t}. Run {base.result_digest.slice(0, 10)}{branch ? `; branch ${branch.result_digest.slice(0, 10)}` : ''}.</div>

          <h3>Relations (select one: it is drawn in the scene)</h3>
          <div className="eco-row" data-testid="te-relation-select" role="group" aria-label="relation">
            {RELATIONS.map((r) => <button key={r.id} className={c.relation === r.id ? 'sel' : undefined} aria-pressed={c.relation === r.id} onClick={() => c.setRelation(c.relation === r.id ? null : r.id)}>{r.label}</button>)}
          </div>
          {c.relation && (() => {
            const rr = compareRelation(base, branch, k, t, c.relation), cell = (x: Reading[]) => x.map((y, i) => <div key={i}>{chip(y.epistemic)} {y.label}: {y.value}</div>);
            const chk = (x: typeof rr.base) => (x.check.holds === null ? 'no identity to check here' : x.check.holds ? 'holds' : 'DOES NOT HOLD');
            return (
              <table className="eco-table" data-testid="te-relation"><tbody>
                <tr><th /><th>baseline</th>{rr.branch && <th>branch</th>}</tr>
                <tr><td>from</td><td>{cell(rr.base.from)}</td>{rr.branch && <td>{cell(rr.branch.from)}</td>}</tr>
                <tr><td>the model's rule</td><td colSpan={rr.branch ? 2 : 1}><small>{rr.base.rule}</small></td></tr>
                <tr><td>to</td><td>{cell(rr.base.to)}</td>{rr.branch && <td>{cell(rr.branch.to)}</td>}</tr>
                <tr><td>checked against the record</td><td>{rr.base.check.name}: <b>{chk(rr.base)}</b> <small>({rr.base.check.detail})</small></td>{rr.branch && <td><b>{chk(rr.branch)}</b> <small>({rr.branch.check.detail})</small></td>}</tr>
              </tbody></table>
            );
          })()}
          <div className="eco-note">The line in the scene is green where the engine's own record satisfies the model's transition rule at this period, red where it does not, white where the relation is not an identity (a drawn error) or cannot be checked. A line is a relation of the model's variables; it does not show that one thing causes another: that is read from the interventions in the saved experiments (EXP-TE07 to TE18), with the reference states (REFERENCE), the observed, the inferred and the unresolved kept apart by the chips.</div>

          <h3>The chain</h3>
          <table className="eco-table" data-testid="te-chain"><tbody>
            {NODES.map((n) => <tr key={n.id} className={c.selected === n.id ? 'sel' : undefined} onClick={() => c.select(c.selected === n.id ? null : n.id)} style={{ cursor: 'pointer' }}><td>{n.label}</td><td><small>{n.reads}</small></td></tr>)}
          </tbody></table>
          <div className="eco-note">Click a node here or its object in the scene. The chain is not a line: a warrant branches from the signal, a correction acts on the score, a second institution takes a copy of it, and what access changes returns to the subject.</div>
          {c.selected && (
            <div data-testid="te-node">
              <h4>{NODES.find((n) => n.id === c.selected)!.label}: baseline</h4>
              <ReadingTable rows={nodeReadings(c.selected, rec, base.config)} />
              {branch && bRec && <><h4>the same node in the branch</h4><ReadingTable rows={nodeReadings(c.selected, bRec, branch.config)} /></>}
            </div>
          )}

          <h3>Observation field</h3><ReadingTable rows={fields.observation} testid="te-f-observation" />
          <PoseTrace run={base} k={k} />
          <h3>Classification field</h3><ReadingTable rows={fields.classification} testid="te-f-classification" />
          <h3>Institutional scoring field</h3><ReadingTable rows={fields.scoring} testid="te-f-scoring" />
          <h3>Operational consequences</h3><ReadingTable rows={fields.consequences} testid="te-f-consequences" />
          <h3>Historical re-entry</h3><ReadingTable rows={fields.reentry} testid="te-f-reentry" />

          {proc && (
            <>
              <h3>The nine times of the correction process</h3>
              <table className="eco-table" data-testid="te-process"><tbody>
                <tr><th>event</th><th>kind</th><th>subject {k + 1}: baseline</th>{branch && <th>branch</th>}<th>subjects that have it</th><th>mean period</th></tr>
                {eventTable(base).map((e) => <tr key={e.id}><td>{e.id.replace(/_/g, ' ')}<br /><small>{e.label}</small></td><td>{chip(e.epistemic)}</td><td>{proc.events[e.id].times[k] ?? 'not within the periods'}</td>{branch && <td>{bproc ? (bproc.events[e.id].times[k] ?? 'not within the periods') : '-'}</td>}<td>{e.n} of {e.of}</td><td>{e.mean === null ? '-' : e.mean.toFixed(1)}</td></tr>)}
              </tbody></table>
              <div className="eco-note">Nine times kept apart, none derived from another. The error is detected, requested, approved and the score updated at times the process sets; the release of a binding constraint is a separate time and may never come, and access restored afterwards is a further one. A misclassification is known to the evaluator only (REFERENCE).</div>

              <h3>Four paths of subject {k + 1}</h3>
              <table className="eco-table" data-testid="te-paths"><tbody>
                <tr><th>path / step</th><th>variable of the model</th><th>baseline (period)</th>{branch && <><th>branch (period)</th><th>branch − baseline</th></>}</tr>
                {PATHS.map((p) => (
                  <>
                    <tr key={p.id}><th colSpan={branch ? 5 : 3}>{p.label}</th></tr>
                    {paths.filter((r) => r.path === p.id).map((r) => <tr key={r.path + r.step} className={base && t >= (r.base ?? Infinity) ? 'sel' : undefined}><td>{r.label}</td><td><small>{r.variable}</small></td><td>{r.base ?? '-'}</td>{branch && <><td>{r.branch ?? '-'}</td><td>{r.delta === null ? STATUS_TEXT[r.status] : r.delta === 0 ? 'same' : `${r.delta > 0 ? '+' : ''}${r.delta} (${STATUS_TEXT[r.status]})`}</td></>}</tr>)}
                  </>
                ))}
              </tbody></table>
              <div className="eco-note">The same subject (same seed) in the baseline and in the branch. A step is the period at which a variable or event the engine recorded first holds; the lines in the scene light the same steps. These are not causal arrows: the later steps are what the model's transitions produce from the earlier ones in that run, and a step that holds in only one run is shown as that, not as a delay.</div>

              <h3>Fixed metrics</h3>
              <table className="eco-table" data-testid="te-metrics"><tbody>
                <tr><th>metric</th><th>baseline</th>{branch && <th>branch</th>}<th>denominator; period; unit</th></tr>
                {PRIMARY_METRICS.map((m) => <tr key={m}><td>{m.replace(/_/g, ' ')}</td><td>{n3(proc.metrics[m])}</td>{branch && <td>{n3(bproc?.metrics[m])}</td>}<td><small>{proc.metric_definitions[m]?.denominator}; {proc.metric_definitions[m]?.period}; {proc.metric_definitions[m]?.unit}</small></td></tr>)}
              </tbody></table>
              <div className="eco-note">The virtual population is the same 120 synthetic subjects in every arm; "favourable at the start" means the reference state z0 &gt; 0. A single run is one seed: no general statement follows from these numbers, the saved experiments below repeat them over 20 seeds and again over 20 others.</div>

              {proc.complement && (
                <>
                  <h3>Complementary metrics: the subjects who were not favourable at the start</h3>
                  <table className="eco-table" data-testid="te-complement"><tbody>
                    <tr><th>metric</th><th>baseline</th>{branch && <th>branch</th>}<th>denominator; period; unit</th></tr>
                    {COMPLEMENT_METRIC_IDS.map((m) => <tr key={m}><td>{m.replace(/_/g, ' ')}</td><td>{n3(proc.complement?.[m])}</td>{branch && <td>{n3(bproc?.complement?.[m])}</td>}<td><small>{proc.complement_definitions?.[m]?.denominator}; {proc.complement_definitions?.[m]?.period}; {proc.complement_definitions?.[m]?.unit}</small></td></tr>)}
                  </tbody></table>
                  <div className="eco-note">The fixed metrics above look only at the subjects favourable at the start and so cannot show what the institution does to the others, among them the subjects it denies correctly. These are added beside them, not instead. A change of the real state moves only through the resource feedback beta (set in the configuration); one run is one unit, so a difference is read over seeds in the saved experiment EXP-TE16, not from one run.</div>
                </>
              )}

              {endo && proc.labels && (
                <>
                  <h3>The institution's action returning to the evaluated target</h3>
                  <div className="eco-row" data-testid="te-endo-badges">
                    <span className={`eco-chip ${endo.classifier.fixed === false ? 'verdict-CHANGED' : 'verdict-UNCHANGED'}`}>{endo.classifier.fixed === null ? 'FIXED CLASSIFIER: no branch' : endo.classifier.fixed ? 'FIXED CLASSIFIER' : 'CLASSIFIER OR OBSERVATION CHANGED'}</span>
                    <span className="eco-chip">CHANGED TARGET</span><span className="eco-chip">LABEL SHIFT</span><span className="eco-chip">DISTRIBUTIONAL CONSEQUENCES</span><span className="eco-chip tee-UNRESOLVED">UNRESOLVED</span>
                  </div>
                  <div className="eco-note" data-testid="te-endo-verdict"><b>{endo.verdict}</b>. {endo.classifier.detail}.</div>
                  <table className="eco-table" data-testid="te-endo"><tbody>
                    <tr><th>BEFORE the period's intervention (subject {k + 1}, period {t})</th><th>AFTER it</th></tr>
                    <tr><td>{endo.before.map((y, i) => <div key={i}>{chip(y.epistemic)} {y.label}: {y.value}</div>)}</td><td>{endo.after.map((y, i) => <div key={i}>{chip(y.epistemic)} {y.label}: {y.value}</div>)}</td></tr>
                    <tr><th>CHANGED TARGET</th><th>LABEL SHIFT</th></tr>
                    <tr><td>{endo.target.map((y, i) => <div key={i}>{chip(y.epistemic)} {y.label}: {y.value}</div>)}</td><td>{endo.labelShift.map((y, i) => <div key={i}>{chip(y.epistemic)} {y.label}: {y.value}</div>)}</td></tr>
                  </tbody></table>
                  <table className="eco-table" data-testid="te-endo-accuracy"><tbody>
                    <tr><th>one set of classifications, four labels</th><th>baseline</th>{branch && <th>branch</th>}</tr>
                    {endo.accuracy.map((r) => <tr key={r.label}><td>{r.label}</td><td>{r.base}</td>{branch && <td>{r.branch}</td>}</tr>)}
                  </tbody></table>
                  <table className="eco-table" data-testid="te-endo-distribution"><tbody>
                    <tr><th>group</th><th>metric</th><th>baseline</th>{branch && <th>branch</th>}</tr>
                    {endo.distribution.map((r, i) => <tr key={i}><td>{r.group}</td><td>{r.metric}</td><td>{r.base}</td>{branch && <td>{r.branch}</td>}</tr>)}
                  </tbody></table>
                  <ul className="eco-log" data-testid="te-endo-unresolved">{endo.unresolved.map((u, i) => <li key={i}><span className="eco-chip tee-UNRESOLVED">UNRESOLVED</span> {u}</li>)}</ul>
                  <div className="eco-note">The INITIAL label is the state before any institutional action; the CURRENT label is the model's own (the state at the start of the period, after the earlier effects); the NEXT label is the state after the period's own decision; the COUNTERFACTUAL label is the state with no institutional effect on the state. The bar and the marker in the scene beside the subject are these records: the bar's height is |state - counterfactual state|, the marker is lit when the labels differ. A rising accuracy is not read as an improvement of the target; a correct classification is not read as a justified action.</div>
                </>
              )}

              <h3>Recoverability of the lost opportunities</h3>
              <table className="eco-table" data-testid="te-recover"><tbody>
                <tr><th /><th>baseline</th>{branch && <th>branch</th>}</tr>
                <tr><td>declared window</td><td>{proc.recoverability.declared_window === null ? 'none (irreversible by setting)' : `${proc.recoverability.declared_window} periods`}</td>{branch && <td>{bproc ? (bproc.recoverability.declared_window === null ? 'none (irreversible by setting)' : `${bproc.recoverability.declared_window} periods`) : '-'}</td>}</tr>
                {(['recoverable', 'expired', 'unresolved'] as const).map((q) => <tr key={q}><td>lost periods {q}</td><td>{proc.recoverability.favourable_at_start.periods[q]}</td>{branch && <td>{bproc?.recoverability.favourable_at_start.periods[q] ?? '-'}</td>}</tr>)}
                {(['recoverable', 'partially_recoverable', 'unrecoverable', 'unresolved'] as const).map((q) => <tr key={q}><td>episodes {q.replace('_', ' ')}</td><td>{proc.recoverability.favourable_at_start.episodes[q]}</td>{branch && <td>{bproc?.recoverability.favourable_at_start.episodes[q] ?? '-'}</td>}</tr>)}
              </tbody></table>
              <div className="eco-note">A lost opportunity is recoverable if access returns within the declared window of the denial, expired if the window closed first, unresolved if the periods ended first. Irreversibility is a setting (no window), not an assumption of the model: whether lost opportunities in fact return is read from the windows.</div>

              <h3>Appeal</h3>
              <table className="eco-table" data-testid="te-appeal"><tbody>
                <tr><th /><th>baseline</th>{branch && <th>branch</th>}</tr>
                <tr><td>procedure</td><td>{proc.appeal.exists ? `exists (${proc.appeal.access === 'score_gated' ? 'gated by the score' : 'open'})` : 'none'}</td>{branch && <td>{bproc ? (bproc.appeal.exists ? `exists (${bproc.appeal.access === 'score_gated' ? 'gated by the score' : 'open'})` : 'none') : '-'}</td>}</tr>
                {APPEAL_STAGES.map((st) => <tr key={st}><td>{st.replace(/_/g, ' ')}</td><td>{proc.appeal.stages[st]} of {base.config.n}</td>{branch && <td>{bproc ? `${bproc.appeal.stages[st]} of ${branch.config.n}` : '-'}</td>}</tr>)}
                <tr><td>blocked from filing by the score</td><td>{proc.appeal.blocked_subjects}</td>{branch && <td>{bproc?.appeal.blocked_subjects ?? '-'}</td>}</tr>
                <tr><td>re-judged: corrected / upheld</td><td>{proc.appeal.rejudged_corrected} / {proc.appeal.rejudged_upheld}</td>{branch && <td>{bproc ? `${bproc.appeal.rejudged_corrected} / ${bproc.appeal.rejudged_upheld}` : '-'}</td>}</tr>
                <tr><td>access at the end after a favourable re-judgement (a favourable subject, no constraint left)</td><td>{proc.appeal.relief_effective}</td>{branch && <td>{bproc?.appeal.relief_effective ?? '-'}</td>}</tr>
              </tbody></table>
              <div className="eco-note">That an appeal exists, that it is filed and that it gives relief are three different counts. The last row counts subjects who end with access after a re-judgement in their favour: it is an association, not an effect of the appeal (the same subject may have regained access anyway); the effect is read from the run without the appeal, in the saved experiment EXP-TE12.</div>
            </>
          )}

          <h3>Truth-error timeline of subject {k + 1}</h3>
          <ul className="eco-log" data-testid="te-timeline">{events.map((e, i) => <li key={i}><button className="eco-span" onClick={() => c.setT(e.t)}>t={e.t}</button> <b>{e.kind.replace(/_/g, ' ')}</b>: {e.label}</li>)}{!events.length && <li>no event for this subject</li>}</ul>
          {branch && <><h4>the branch</h4><ul className="eco-log" data-testid="te-timeline-branch">{branchEvents.map((e, i) => <li key={i}><button className="eco-span" onClick={() => c.setT(e.t)}>t={e.t}</button> <b>{e.kind.replace(/_/g, ' ')}</b>: {e.label}</li>)}{!branchEvents.length && <li>no event for this subject</li>}</ul></>}

          <h3>The score in the Address Domain</h3>
          <table className="eco-table" data-testid="te-address"><tbody>{addr!.map((a) => <tr key={a.id}><td>{a.label}</td><td>{ADDRESS_STATES.find(([id]) => id === a.id) ? a.value.toFixed(a.id === 'score_exists' || a.id === 'access_altered' ? 2 : 0) : ''}</td></tr>)}</tbody></table>
          <div className="eco-note">Six states kept apart. A score can exist without being read; it can be read without being transferred or changing access; extinguishing the score does not extinguish a binding constraint, and the opportunities lost by earlier denials do not return when either ends.</div>

          <h3>Five kinds of "cannot" (subject {k + 1}, periods up to {t})</h3>
          <table className="eco-table" data-testid="te-modalities"><tbody>
            <tr><th>kind</th><th>baseline</th>{branch && <th>branch</th>}<th>defined as</th></tr>
            {MODALITIES.map(([id, label, def]) => <tr key={id}><td>{label}</td><td>{modalityCounts(base, k, t)[id]}</td>{branch && <td>{modalityCounts(branch, k, t)[id]}</td>}<td><small>{def}</small></td></tr>)}
          </tbody></table>
          <div className="eco-note">Periods of each kind, kept apart: they are not exclusive and none is another. These are this model's definitions; a correspondence with any philosophical account of prohibition, impossibility or truth is not established here.</div>

          {cmp && (
            <>
              <h3>Baseline and branch</h3>
              <div className="eco-note" data-testid="te-changed"><b>What was changed:</b> {cmp.changed.length ? cmp.changed.join('; ') : 'nothing (the same configuration)'}</div>
              <table className="eco-table" data-testid="te-compare"><tbody>
                <tr><th>aspect</th><th>baseline</th><th>branch</th><th /></tr>
                {cmp.rows.map((r) => <tr key={r.id}><td>{r.label}</td><td>{r.base}</td><td>{r.branch}</td><td><span className={`eco-chip verdict-${r.verdict === 'DIFFERENT' ? 'CHANGED' : 'UNCHANGED'}`}>{r.verdict.replace('_', ' ')}</span></td></tr>)}
              </tbody></table>
              <div className="eco-note">{cmp.note}</div>
            </>
          )}
        </>
      )}

      <h3>Phase 2: correction, release, recoverability, appeals (saved results)</h3>
      {!c.experiments2 && <div className="eco-note">The phase-2 results are not available on this server (run backend/scripts/truth_error_experiments.py).</div>}
      {c.experiments2 && (
        <>
          <div className="eco-row"><label>experiment <select aria-label="phase 2 experiment" value={c.exp2Id} onChange={(e) => c.setExp2Id(e.target.value)}>{Object.values(c.experiments2).map((e) => <option key={e.id} value={e.id}>{e.id}: {e.title}</option>)}</select></label></div>
          {exp2 && (
            <div data-testid="te2-experiment">
              <div className="eco-note"><b>Question:</b> {exp2.question} <b>Control:</b> {exp2.control}. <b>Seeds:</b> {exp2.seeds[0]}-{exp2.seeds.at(-1)}, replicated on {exp2.replication?.seeds[0]}-{exp2.replication?.seeds.at(-1)}. <b>Protocol:</b> {String(exp2.protocol.changed)}; protocol {exp2.protocol_digest.slice(0, 10)}.</div>
              {exp2.contrasts && (
                <table className="eco-table" data-testid="te2-contrasts"><tbody>
                  <tr><th>contrast</th><th>outcome</th><th>mean ± se (seeds 1-20)</th><th>seeds 21-40</th><th>reading</th></tr>
                  {exp2.contrasts.map((x, i) => <tr key={i}><td>{x.label}</td><td>{x.outcome.replace(/_/g, ' ')}</td><td>{n3(x.paired.mean)} ± {n3(x.paired.se)}</td><td>{n3(x.paired_seeds_21_40?.mean)} ± {n3(x.paired_seeds_21_40?.se)}</td><td><span className={`eco-chip verdict-${x.class === 'replicated' ? 'CHANGED' : 'UNCHANGED'}`}>{x.class}</span></td></tr>)}
                </tbody></table>
              )}
              <table className="eco-table" data-testid="te2-arms"><tbody>
                <tr><th>arm</th>{exp2.primary_outcomes.map((o) => <th key={o}>{o.replace(/_/g, ' ')}</th>)}<th /></tr>
                {exp2.arms.map((a) => (
                  <tr key={a.arm}><td>{a.arm}</td>{exp2.primary_outcomes.map((o) => { const m = a.mean[o]?.mean, d = a.paired_vs_control?.[o]; return <td key={o}>{n3(m)}{d?.detected ? ' *' : ''}</td>; })}
                    <td><button disabled={c.busy} onClick={() => void c.loadArm(exp2.id, a.arm, a.arm === exp2.control ? 'base' : 'branch')}>{a.arm === exp2.control ? 'AS BASELINE' : 'AS BRANCH'}</button></td></tr>
                ))}
              </tbody></table>
              {exp2.replication && <div className="eco-note" data-testid="te2-replication"><b>Replication of the paired differences from the control:</b> {Object.entries(exp2.replication.counts).map(([key, v]) => `${key}: ${v}`).join('; ')}. Replicated means detected (beyond two standard errors) in both seed lists with the same sign; set-dependent means in one only.</div>}
              {exp2.questions && exp2.questions.length > 0 && <ul className="eco-log" data-testid="te2-questions">{exp2.questions.map((q) => <li key={q.id}><b>{q.id}</b> {q.question} <small>changed: {q.variable_changed}; held: {q.held}</small></li>)}</ul>}
              <div className="eco-note" data-testid="te2-negatives"><b>Not detected (kept):</b> {exp2.negative_results.length ? exp2.negative_results.slice(0, 5).join('; ') : 'none of the primary outcomes'}{exp2.negative_results.length > 5 ? ` … (+${exp2.negative_results.length - 5})` : ''}</div>
              <div className="eco-note">{exp2.limits}</div>
            </div>
          )}
        </>
      )}

      <h3>Pre-registered experiments (saved results)</h3>
      {!c.experiments && <div className="eco-note">The saved results are not available on this server (run backend/scripts/truth_error_experiments.py).</div>}
      {c.experiments && (
        <>
          <div className="eco-row"><label>experiment <select aria-label="experiment" value={c.expId} onChange={(e) => c.setExpId(e.target.value)}>{Object.values(c.experiments).map((e) => <option key={e.id} value={e.id}>{e.id}: {e.title}</option>)}</select></label></div>
          {exp && (
            <div data-testid="te-experiment">
              <div className="eco-note"><b>Question:</b> {exp.question} <b>Control:</b> {exp.control}. <b>Seeds:</b> {exp.seeds.length} ({exp.seeds[0]}-{exp.seeds.at(-1)}); <b>observation range:</b> {exp.periods} periods, {exp.n_subjects} subjects. <b>Protocol:</b> {String(exp.protocol.changed)} changed; {String(exp.protocol.unchanged)} unchanged; protocol {exp.protocol_digest.slice(0, 10)}.</div>
              <table className="eco-table"><tbody>
                <tr><th>arm (what it changes)</th>{exp.primary_outcomes.map((o) => <th key={o}>{o.replace(/_/g, ' ')}</th>)}<th /></tr>
                {exp.arms.map((a) => (
                  <tr key={a.arm}><td>{a.arm}<br /><small>{Object.keys(a.changed_vs_control).join(', ') || 'the control'}</small></td>
                    {exp.primary_outcomes.map((o) => { const m = a.mean[o]?.mean, d = a.paired_vs_control?.[o]; return <td key={o}>{m === null || m === undefined ? '-' : m.toFixed(2)}{d?.detected ? ' *' : ''}</td>; })}
                    <td><button disabled={c.busy} onClick={() => void c.loadArm(exp.id, a.arm, a.arm === exp.control ? 'base' : 'branch')}>{a.arm === exp.control ? 'AS BASELINE' : 'AS BRANCH'}</button></td></tr>
                ))}
              </tbody></table>
              <div className="eco-note">* a paired difference from the control beyond two standard errors over the seeds; descriptive, no correction for the number of comparisons. Loading an arm runs the engine with that arm's full configuration (seed 1 of the experiment): the baseline and the branch above then compare as the experiment does.</div>
              <div className="eco-note" data-testid="te-negatives"><b>Not detected (kept):</b> {exp.negative_results.length ? exp.negative_results.slice(0, 6).join('; ') : 'none of the primary outcomes'}{exp.negative_results.length > 6 ? ` … (+${exp.negative_results.length - 6})` : ''}</div>
              <div className="eco-note" data-testid="te-failures"><b>Failure conditions:</b> {Object.entries(exp.failure_conditions).map(([k2, v]) => `${k2}: ${v ? 'MET (the experiment is invalid)' : 'not met'}`).join('; ')}. {exp.limits}</div>
            </div>
          )}
        </>
      )}
    </>
  );
}

const REFERENCE_TEXT = 'Values held by the evaluator only (the reference state and the verification label) are marked REFERENCE and are read by no institution in the model.';
