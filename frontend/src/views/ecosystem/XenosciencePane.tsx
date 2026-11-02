import { useMemo, useState } from 'react';
import { FULL_OBSERVATION, type Intervention, type MeosRecord, type Observation, type RunOut, type SssClassOut } from './meosApi';
import { EXPERIMENTS, STATUS_TEXT } from './experiments';
import { COUPLINGS, ORIGIN_TEXT, compareBranches, couplingDef, couplingStates, type CouplingId, type Origin } from './couplings';
import { ENTITY_NAMES, type EntityName } from './layers';
import {
  compareRegimes, criticalIntervals, fiveS, humanDependencies, inventory, provenance, strongXenoscience,
  type Reading, type RegimeSide,
} from './xenoscience';

// XENOSCIENCE — the research readings of the current run. Every number is read from the record or from the engine's observation result (see xenoscience.ts); this pane never runs
// the engine and never edits a run. Observed, inferred and reference (evaluator-only) readings are kept in separate groups, and what the engine cannot establish is shown as such.

/** What is drawn in the coupling layer. These are display operations: none of them runs the engine or changes a record. */
export interface CouplingDisplay { couplings: boolean; isolate: boolean; exploded: boolean; ghost: boolean }
/** The baseline run kept while interventions are requested from the scene, and the request that made the branch. */
export interface Branch { base: { record: MeosRecord; ivs: Intervention[] }; request: { id: CouplingId; tick: number; duration: number | null } }

export interface XenoscienceCtx { rec: MeosRecord | null; out: RunOut | null; tick: number; setTick: (t: number) => void; obs: Observation; entity: EntityName | null; sssClass: SssClassOut | null; pinned: RegimeSide | null; setPinned: (p: RegimeSide | null) => void;
  coupling: CouplingId | null; selectCoupling: (id: CouplingId | null) => void; display: CouplingDisplay; setDisplay: (d: CouplingDisplay) => void;
  branch: Branch | null; requestCut: (id: CouplingId, at: number, duration: number | null) => Promise<void>; restoreBaseline: () => Promise<void>; clearBranch: () => void; busy: boolean; origin: Origin }

const GROUPS: Array<{ key: 'observed' | 'inferred' | 'reference'; title: string; note: string }> = [
  { key: 'observed', title: 'OBSERVED', note: 'recorded through the configured observation array' },
  { key: 'inferred', title: 'INFERRED', note: 'reconstructed by a declared analytical procedure' },
  { key: 'reference', title: 'REFERENCE (hidden from the observer)', note: "the evaluator's internal state; never an observation" },
];

const ReadingRow = ({ r }: { r: Reading }) => <tr title={r.why} className={r.availability === 'UNRESOLVED' ? 'eco-unresolved' : undefined}><td>{r.label}</td><td>{r.value}</td></tr>;

export default function XenosciencePane({ rec, out, tick, setTick, obs, entity, sssClass, pinned, setPinned, coupling, selectCoupling, display, setDisplay, branch, requestCut, restoreBaseline, clearBranch, busy, origin }: XenoscienceCtx) {
  const [who, setWho] = useState<EntityName>(entity ?? 'A1');
  const [dur, setDur] = useState<string>('50');
  const observed = out?.observed ?? null;
  const current: RegimeSide | null = rec && observed ? { obs, observed, resultDigest: rec.result_digest } : null;
  const fullObs = JSON.stringify(obs) === JSON.stringify(FULL_OBSERVATION);
  const missing = fullObs ? 'the run used full-resolution observation, for which no separate observation result is requested (set a coarser observation in EXPERIMENT)' : undefined;
  const inv = useMemo(() => (rec ? inventory(rec, tick, entity ?? who, observed, out?.paths ?? null, missing) : null), [rec, tick, entity, who, observed, out?.paths, missing]);
  const prov = useMemo(() => (rec ? provenance(rec) : null), [rec]);
  const intervals = useMemo(() => (rec ? criticalIntervals(rec, observed) : []), [rec, observed]);
  const human = useMemo(() => (rec ? humanDependencies(rec) : []), [rec]);
  const strong = useMemo(() => (rec ? strongXenoscience(rec) : null), [rec]);
  const five = useMemo(() => (rec ? fiveS(rec, sssClass) : []), [rec, sssClass]);
  const cmp = pinned && current ? compareRegimes(pinned, current) : null;
  const states = useMemo(() => (rec ? couplingStates(rec, tick) : null), [rec, tick]);
  const branchCmp = useMemo(() => (rec && branch ? compareBranches(branch.base.record, rec) : null), [rec, branch]);
  if (!rec || !inv || !prov || !strong) return <div className="eco-note">Run an experiment first: the Xenoscience readings are read from its record.</div>;
  const n = rec.frames.length;
  const shown = entity ?? who;

  return (
    <>
      <h3>Couplings in the 3D scene</h3>
      <div className="eco-note">Click a coupling in the scene, or choose one here. Each coupling is a component of the engine; its state is read from the record at the playhead tick. A cut is a request: the engine runs the baseline's interventions plus the cut, and the result replaces the record on screen.</div>
      <table className="eco-table" data-testid="xeno-couplings"><tbody>
        {COUPLINGS.map((c) => (
          <tr key={c.id} className={coupling === c.id ? 'sel' : undefined} onClick={() => selectCoupling(coupling === c.id ? null : c.id)} style={{ cursor: 'pointer' }}>
            <td>{c.label}</td><td><span className={`eco-chip coupling-${states?.[c.id] ?? 'unrecorded'}`}>{states?.[c.id] ?? 'unrecorded'}</span></td><td><small>{c.from} → {c.to}</small></td>
          </tr>
        ))}
      </tbody></table>
      {coupling && (
        <>
          <dl className="eco-kv" data-testid="xeno-coupling-detail">
            <dt>engine component</dt><dd>{coupling} (ISOLATE / RECONNECT)</dd>
            <dt>what the engine does with it</dt><dd>{couplingDef(coupling).role}</dd>
            <dt>when it is cut the engine reports</dt><dd>{couplingDef(coupling).whenCut}</dd>
            <dt>state at tick {tick}</dt><dd>{states?.[coupling] ?? 'unrecorded'}</dd>
          </dl>
          <div className="eco-row">
            <label>cut for <select value={dur} onChange={(e) => setDur(e.target.value)} aria-label="duration of the cut">{['10', '25', '50', '100', 'open'].map((d) => <option key={d} value={d}>{d === 'open' ? 'the rest of the run' : `${d} ticks`}</option>)}</select></label>
            <button disabled={busy} onClick={() => void requestCut(coupling, tick, dur === 'open' ? null : Number(dur))} title="ask the engine to run the interventions">REQUEST CUT AT TICK {tick}</button>
          </div>
        </>
      )}
      <div className="eco-row" role="group" aria-label="display operations">
        {([['couplings', 'coupling layer'], ['isolate', 'isolate selected'], ['exploded', 'exploded view'], ['ghost', 'baseline markers']] as const).map(([k, l]) => (
          <button key={k} className={display[k] ? 'on' : ''} aria-pressed={display[k]} onClick={() => setDisplay({ ...display, [k]: !display[k] })}>{l}</button>
        ))}
      </div>
      <div className="eco-note">Isolate, exploded view and baseline markers are display operations: they change what is drawn and run nothing. The heights of the couplings and the lift of the exploded view are schematic layout offsets, not physical dimensions; positions of the configurations are the recorded cells.</div>
      <div className="eco-note" data-testid="xeno-origin"><span className={`eco-chip origin-${origin}`}>{origin.replace(/_/g, ' ')}</span> {ORIGIN_TEXT[origin]}. Moving the playhead plays this record back and runs nothing; REPLAY (EXPERIMENT tab) re-executes its inputs in the engine and compares the result digest.</div>
      {branchCmp && branch && (
        <>
          <h3>Baseline and intervention branch</h3>
          <table className="eco-table" data-testid="xeno-branch"><tbody>
            <tr><th /><th>baseline</th><th>branch</th></tr>
            <tr><td>final status</td><td>{branchCmp.base.label}</td><td>{branchCmp.branch.label}</td></tr>
            <tr><td>first COLLAPSED</td><td>{branchCmp.base.firstCollapse ?? 'never'}</td><td>{branchCmp.branch.firstCollapse ?? 'never'}</td></tr>
            <tr><td>cycles</td><td>{branchCmp.base.cycles}</td><td>{branchCmp.branch.cycles}</td></tr>
            <tr><td>result digest</td><td><small>{branchCmp.base.resultDigest.slice(0, 12)}</small></td><td><small>{branchCmp.branch.resultDigest.slice(0, 12)}</small></td></tr>
          </tbody></table>
          <dl className="eco-kv">
            <dt>added interventions</dt><dd>{branchCmp.added.map((i) => `${i.op} ${i.target ?? ''} @${i.tick}`).join('; ') || 'none'}</dd>
            <dt>same configuration</dt><dd>{branchCmp.sameConfiguration ? 'yes' : 'NO: the two runs are configured differently'}</dd>
            <dt>records first differ at</dt><dd>{branchCmp.firstStateDivergence === null ? 'never (within the ticks both records cover)' : `tick ${branchCmp.firstStateDivergence}`}</dd>
            <dt>status first differs at</dt><dd>{branchCmp.firstStatusDivergence === null ? 'never' : `tick ${branchCmp.firstStatusDivergence}`}</dd>
          </dl>
          <div className="eco-row">
            <button disabled={branchCmp.firstStateDivergence === null} onClick={() => setTick(branchCmp.firstStateDivergence ?? 0)}>GO TO DIVERGENCE</button>
            <button disabled={busy} onClick={() => void restoreBaseline()}>RUN THE BASELINE AGAIN</button>
            <button onClick={clearBranch}>FORGET THE BASELINE</button>
          </div>
          <div className="eco-note">The comparison locates where two records the engine produced first differ. It does not attribute the later differences to the cut: that needs the engine's causal operations (REDUCTIONS). The baseline markers in the scene are the baseline run's recorded cells at the playhead tick.</div>
        </>
      )}

      <h3>Operational shape inspector</h3>
      <div className="eco-row">{ENTITY_NAMES.map((e) => <button key={e} className={shown === e ? 'on' : ''} disabled={!!entity} onClick={() => setWho(e)}>{e}</button>)}</div>
      <div className="eco-note">Readings for {shown} at tick {tick}. {entity ? 'The entity is the one selected on the stage.' : 'Select an entity on the stage, or choose one here.'} A hidden reference value is not an observation: it is listed apart and may not be available to an operational observer.</div>
      {GROUPS.map((g) => (
        <section key={g.key} className={`eco-epi eco-epi-${g.key}`} data-testid={`xeno-${g.key}`}>
          <h4><span className={`eco-chip epi-${g.key}`}>{g.title}</span> <small>{g.note}</small></h4>
          <table className="eco-table"><tbody>{inv[g.key].map((r) => <ReadingRow key={r.id} r={r} />)}</tbody></table>
        </section>
      ))}

      <h3>Observation regime comparison</h3>
      <div className="eco-row">
        <button disabled={!current} onClick={() => current && setPinned(current)} title="keep the current observation as side A">PIN CURRENT AS A</button>
        <button disabled={!pinned} onClick={() => setPinned(null)}>CLEAR</button>
      </div>
      {!pinned && <div className="eco-note">Pin the current observation, change the observation configuration (EXPERIMENT tab) or the intervention list, run again, and compare. The five kinds of change are reported separately.</div>}
      {pinned && !current && <div className="eco-note">The current run has no observation result: nothing to compare with the pinned side.</div>}
      {cmp && (
        <>
          <table className="eco-table" data-testid="xeno-regime"><tbody>{cmp.rows.map((r) => <tr key={r.kind}><td>{r.label}</td><td><span className={`eco-chip verdict-${r.verdict}`}>{r.verdict}</span></td><td>{r.detail}</td></tr>)}</tbody></table>
          <div className="eco-note">{cmp.note}</div>
        </>
      )}

      <h3>Intervention provenance</h3>
      <dl className="eco-kv" data-testid="xeno-provenance">
        <dt>engine / schema</dt><dd>{prov.engine} / {prov.schema}</dd>
        <dt>seed</dt><dd>{prov.seed}</dd>
        <dt>input digest (configuration and interventions)</dt><dd>{prov.initialConfigDigest}</dd>
        <dt>result digest</dt><dd>{prov.resultDigest}</dd>
        <dt>termination</dt><dd>{prov.termination}</dd>
      </dl>
      {prov.entries.length === 0 ? <div className="eco-note">No intervention was requested in this run.</div> : (
        <table className="eco-table"><tbody>
          <tr><th>tick</th><th>requested</th><th>engine</th><th>first status change after</th></tr>
          {prov.entries.map((e) => <tr key={e.index}><td>{e.requested.tick}</td><td>{e.requested.op}{e.requested.target ? ` ${e.requested.target}` : ''}</td><td>{e.engine === 'ACCEPTED' ? `accepted (event ${e.event})` : 'not in the engine log'}</td><td>{e.firstStatusChange ? `t=${e.firstStatusChange.tick} ${e.firstStatusChange.label}` : 'none'}</td></tr>)}
        </tbody></table>
      )}
      <div className="eco-note">{"Requests the engine rejects are refused before a run exists, so a rejected request leaves no record; the console reports it as an error. Every accepted request is a row of the engine's own intervention log."}</div>

      <h3>Critical intervals</h3>
      <div className="eco-note">Intervals are listed, not sequenced: they may overlap or occur in any order. A lost observation is not a cessation, and a preserved classification does not show that the earlier capabilities remain.</div>
      <table className="eco-table" data-testid="xeno-intervals"><tbody>
        {intervals.map((c) => (
          <tr key={c.id} title={c.basis}>
            <td>{c.label}</td>
            <td><span className={`eco-chip iv-${c.status}`}>{c.status.replace('_', ' ')}</span></td>
            <td>{c.spans.length ? <span className="eco-spans">{c.spans.slice(0, 4).map(([a, b]) => <button key={`${a}-${b}`} className="eco-span" onClick={() => setTick(Math.min(a, n - 1))}>{a === b ? `t=${a}` : `t=${a}–${b}`}</button>)}{c.spans.length > 4 ? ` +${c.spans.length - 4}` : ''}</span> : <small>{c.basis}</small>}</td>
          </tr>
        ))}
      </tbody></table>

      <h3>Five-S (conditional analysis)</h3>
      <table className="eco-table" data-testid="xeno-fives"><tbody>{five.map((r) => <tr key={r.dimension} title={r.note}><td>{r.dimension}</td><td><span className="eco-chip">{r.kind}</span></td><td>{r.current}</td></tr>)}</tbody></table>
      <div className="eco-note">Five-S is not a five-variable law: only scale, size and speed are controls, structure is an arrangement, and sensitivity is measured (REDUCTIONS → SSS, or RESEARCH → SSS classification).</div>

      <h3>Human mediation</h3>
      <table className="eco-table" data-testid="xeno-human"><tbody>{human.map((d) => <tr key={d.id} title={d.detail}><td>{d.label}</td><td><span className={`eco-chip dep-${d.state}`}>{d.state.replace(/_/g, ' ')}</span></td><td><small>{d.detail}</small></td></tr>)}</tbody></table>
      <div className="eco-note">The six kinds are not merged into a score. Removing an operator from the loop of a run does not remove the human infrastructure that built, powered and defined it.</div>

      <h3>Strong Xenoscience: four jointly necessary conditions</h3>
      <table className="eco-table" data-testid="xeno-strong"><tbody>{strong.conditions.map((c) => <tr key={c.id}><td>{c.id}. {c.label}</td><td><span className={`eco-chip st-${c.status}`}>{c.status.replace(/_/g, ' ')}</span></td><td><small>{c.basis}</small></td></tr>)}</tbody></table>
      <div className="eco-note"><b>{strong.joint.replace(/_/g, ' ')}.</b> {strong.note}</div>
      <h3>Experiments in this environment</h3>
      <table className="eco-table" data-testid="xeno-experiments"><tbody>
        {EXPERIMENTS.map((e) => <tr key={e.id} title={`${e.engine}. ${e.source}. ${e.note}`}><td>{e.title}</td><td><span className={`eco-chip exp-${e.status}`}>{STATUS_TEXT[e.status]}</span></td><td><small>{e.note}</small></td></tr>)}
      </tbody></table>
      <div className="eco-note">Only an experiment with an engine here can be intervened on. TO-C1 is listed as what it is: its original source has not been supplied, so none of its numbers is shown or reproduced.</div>
    </>
  );
}
