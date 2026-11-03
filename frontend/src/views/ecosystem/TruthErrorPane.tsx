import { useMemo } from 'react';
import { ADDRESS_STATES, MODALITIES, NODES, addressStatesAt, compareRuns, fieldsAt, modalityCounts, nodeReadings, timelineEvents, type NodeId, type Reading, type TERun } from './truthError';
import type { TEExperiment, TEOverrides } from './truthApi';

// TRUTH-ERROR DYNAMICS — a research tab of the XENO ECOSYSTEM view. It runs a SYNTHETIC virtual institution (backend/xzr/truth_error) and reads the run: nothing here classifies, scores or simulates, and every value is
// read from the engine's record. No real person, face, credit or eligibility is assessed; a head pose is a measurement with an error and is never an indicator of truthfulness, character or creditworthiness. The stages
// (measurement, classification, warrant, acceptance, score, access, resources, correction) are shown as separate records and are never reduced to one right/wrong variable.

export interface TruthCtx {
  base: TERun | null; branch: TERun | null; k: number; setK: (k: number) => void; t: number; setT: (t: number) => void; selected: NodeId | null; select: (id: NodeId | null) => void;
  draft: TEOverrides; setDraft: (d: TEOverrides) => void; busy: boolean; err: string | null; runBase: () => Promise<void>; runBranch: () => Promise<void>; clearBranch: () => void; focus3d: () => void;
  experiments: Record<string, TEExperiment> | null; expId: string; setExpId: (id: string) => void; loadArm: (expId: string, arm: string, as: 'base' | 'branch') => Promise<void>;
}

const CLASSIFIERS = ['signal_rule', 'pose_rule', 'random_rule', 'none'];
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
