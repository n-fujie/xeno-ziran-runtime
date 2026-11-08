import { useMemo, useState } from 'react';
import { FULL_OBSERVATION, type Intervention, type MeosRecord, type Observation, type Observed, type RunOut, type SssClassOut } from './meosApi';
import { OBSERVATION_LIMITS, isFullObservation, seenCells } from './observation3d';
import { EXPERIMENTS, MODE_TEXT, SCENE_TEXT, seriesEvidence, type SeriesKind } from './experiments';
import { COUPLINGS, ORIGIN_TEXT, branchAspects, compareBranches, couplingDef, couplingStates, type CouplingId, type Origin } from './couplings';
import { ENTITY_NAMES, type EntityName } from './layers';
import {
  compareRegimes, criticalIntervals, entityObservations, fiveS, historyConsequence, historyReading, humanDependencies, inventory, operationalStates, provenance, shapeTrack, strongXenoscience, unresolvedItems,
  type Reading, type RegimeSide,
} from './xenoscience';

// XENOSCIENCE — the research readings of the current run. Every number is read from the record or from the engine's observation result (see xenoscience.ts); this pane never runs
// the engine and never edits a run. Observed, inferred and reference (evaluator-only) readings are kept in separate groups, and what the engine cannot establish is shown as such.

/** What is drawn in the coupling layer. These are display operations: none of them runs the engine or changes a record. */
export interface CouplingDisplay { couplings: boolean; isolate: boolean; exploded: boolean; ghost: boolean; observedCells: boolean }
/** The baseline run kept while interventions are requested from the scene, and the request that made the branch. */
export interface Branch { base: { record: MeosRecord; ivs: Intervention[]; observed: Observed | null }; request: { kind: 'cut'; id: CouplingId; tick: number; duration: number | null } | { kind: 'history-off'; tick: number } }

/** The experiment series this scene can load: each is executed by the engine on request, with its own interventions and state definition. */
export interface SeriesCtx {
  presets: string[]; loadPreset: (key: string) => Promise<void>;
  mfs: Array<{ id: string; label: string }>; loadMfs: (id: string) => Promise<void>;
  controllers: string[]; scenarios: string[]; loadControlled: (controller: string, scenario: string) => Promise<void>;
  /** the series loaded last, and the view's status line about it */
  loaded: { kind: SeriesKind; label: string } | null; replayLine: string | null;
}

export interface XenoscienceCtx { rec: MeosRecord | null; out: RunOut | null; tick: number; setTick: (t: number) => void; obs: Observation; entity: EntityName | null; sssClass: SssClassOut | null; pinned: RegimeSide | null; setPinned: (p: RegimeSide | null) => void;
  observeMode: 'region' | 'occluder' | null; setObserveMode: (m: 'region' | 'occluder' | null) => void; corner: [number, number] | null; setObs: (o: Observation) => void;
  coupling: CouplingId | null; selectCoupling: (id: CouplingId | null) => void; display: CouplingDisplay; setDisplay: (d: CouplingDisplay) => void;
  series: SeriesCtx; branch: Branch | null; playFrom: (t: number) => void; verifyReplay: () => Promise<void>; requestHistoryOff: (tick: number) => Promise<void>; requestCut: (id: CouplingId, at: number, duration: number | null) => Promise<void>; restoreBaseline: () => Promise<void>; clearBranch: () => void; busy: boolean; origin: Origin }

const GROUPS: Array<{ key: 'observed' | 'inferred' | 'reference'; title: string; note: string }> = [
  { key: 'observed', title: 'OBSERVED', note: 'recorded through the configured observation array' },
  { key: 'inferred', title: 'INFERRED', note: 'reconstructed by a declared analytical procedure' },
  { key: 'reference', title: 'REFERENCE (hidden from the observer)', note: "the evaluator's internal state; never an observation" },
];

const ReadingRow = ({ r }: { r: Reading }) => <tr title={r.why} className={r.availability === 'UNRESOLVED' ? 'eco-unresolved' : undefined}><td>{r.label}</td><td>{r.value}</td></tr>;

export default function XenosciencePane({ rec, out, tick, setTick, obs, entity, sssClass, pinned, setPinned, observeMode, setObserveMode, corner, setObs, series, coupling, selectCoupling, display, setDisplay, branch, playFrom, verifyReplay, requestHistoryOff, requestCut, restoreBaseline, clearBranch, busy, origin }: XenoscienceCtx) {
  const [who, setWho] = useState<EntityName>(entity ?? 'A1');
  const [dur, setDur] = useState<string>('50');
  const [preset, setPreset] = useState('recovery-demo'), [mfsId, setMfsId] = useState(''), [ctl, setCtl] = useState('adaptive'), [scn, setScn] = useState('coupling weakened (gain 0.5)');
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
  const aspects = useMemo(() => (rec && branch ? branchAspects(branch.base.record, rec, branch.base.observed, observed) : []), [rec, branch, observed]);
  const opStates = useMemo(() => (rec ? operationalStates(rec, observed, tick) : null), [rec, observed, tick]);
  const entityObs = useMemo(() => (rec ? entityObservations(rec, obs, tick, observed) : []), [rec, obs, tick, observed]);
  const track = useMemo(() => (rec ? shapeTrack(rec, observed, branchCmp?.firstStateDivergence ?? null) : null), [rec, observed, branchCmp]);
  const unresolved = useMemo(() => (rec ? unresolvedItems(rec, observed) : []), [rec, observed]);
  const history = useMemo(() => (rec ? historyReading(rec, tick) : null), [rec, tick]);
  const consequence = useMemo(() => (rec && branch && branch.request.kind === 'history-off' ? historyConsequence(branch.base.record, rec) : null), [rec, branch]);
  if (!rec || !inv || !prov || !strong || !track || !history || !opStates) return <div className="eco-note">Run an experiment first: the Xenoscience readings are read from its record.</div>;
  const n = rec.frames.length;
  const shown = entity ?? who;

  return (
    <>
      <h3>Experiment series in this scene</h3>
      <div className="eco-note">Each series is run by the engine when loaded and keeps its own interventions and state definition. Loading one replaces the record on screen and forgets the baseline of a branch.</div>
      <table className="eco-table" data-testid="xeno-series"><tbody>
        <tr><td>preset <small>scheduled interventions on the default arrangement</small></td>
          <td><select aria-label="preset" value={preset} onChange={(e) => setPreset(e.target.value)}>{series.presets.map((k) => <option key={k} value={k}>{k}</option>)}</select></td>
          <td><button disabled={busy} onClick={() => void series.loadPreset(preset)}>LOAD (LIVE ENGINE)</button></td></tr>
        <tr><td>saved MFS <small>a stored arrangement with only its retained components, no intervention</small></td>
          <td>{series.mfs.length ? <select aria-label="saved MFS" value={mfsId || series.mfs[0].id} onChange={(e) => setMfsId(e.target.value)}>{series.mfs.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}</select> : <small>not saved on this server</small>}</td>
          <td><button disabled={busy || !series.mfs.length} onClick={() => void series.loadMfs(mfsId || series.mfs[0].id)}>LOAD (LIVE ENGINE)</button></td></tr>
        <tr><td>controlled run <small>a stress at tick 100; a controller moves between saved MFS</small></td>
          <td><select aria-label="controller" value={ctl} onChange={(e) => setCtl(e.target.value)}>{series.controllers.map((k) => <option key={k} value={k}>{k}</option>)}</select> <select aria-label="scenario" value={scn} onChange={(e) => setScn(e.target.value)}>{series.scenarios.map((k) => <option key={k} value={k}>{k}</option>)}</select></td>
          <td><button disabled={busy || !series.mfs.length} onClick={() => void series.loadControlled(ctl, scn)}>LOAD (LIVE ENGINE)</button></td></tr>
      </tbody></table>
      {series.loaded && (() => { const ev = seriesEvidence(series.loaded.kind, series.replayLine); return <div className="eco-note" data-testid="xeno-series-evidence"><span className={`eco-chip exp-${ev.mode}`}>{MODE_TEXT[ev.mode].toUpperCase()}</span> loaded: {series.loaded.label}. {ev.text}. Being drawn in this scene is not what makes an experiment live or verified: the line above says what the engine did.</div>; })()}

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
      <div className="eco-row" role="group" aria-label="history playback">
        <button onClick={() => playFrom(0)} title="move the playhead to tick 0 and play the record back: nothing is run">PLAY THE RECORD FROM TICK 0</button>
        <button disabled={busy} onClick={() => void verifyReplay()} title="the engine re-executes the record's inputs and compares the result digest">VERIFY BY ENGINE REPLAY</button>
      </div>
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
          <table className="eco-table" data-testid="xeno-aspects"><tbody>
            <tr><th>aspect</th><th>baseline</th><th>branch</th><th /></tr>
            {aspects.map((a) => <tr key={a.id} title={`${a.detail}. Reads: ${a.reads.join(', ')}`}><td>{a.label}</td><td><small>{a.base}</small></td><td><small>{a.branch}</small></td><td><span className={`eco-chip verdict-${a.verdict === 'DIFFERENT' ? 'CHANGED' : a.verdict === 'NO_DIFFERENCE' ? 'UNCHANGED' : 'UNRESOLVED'}`}>{a.verdict.replace(/_/g, ' ')}</span></td></tr>)}
          </tbody></table>
          <div className="eco-row">
            <button disabled={branchCmp.firstStateDivergence === null} onClick={() => setTick(branchCmp.firstStateDivergence ?? 0)}>GO TO DIVERGENCE</button>
            <button disabled={busy} onClick={() => void restoreBaseline()}>RUN THE BASELINE AGAIN</button>
            <button onClick={clearBranch}>FORGET THE BASELINE</button>
          </div>
          <div className="eco-note">The comparison locates where two records the engine produced first differ. It does not attribute the later differences to the cut: that needs the engine's causal operations (REDUCTIONS). The baseline markers in the scene are the baseline run's recorded cells at the playhead tick.</div>
        </>
      )}

      <h3>Observation, set from the scene</h3>
      <div className="eco-note">Changing the observation re-runs the engine for the observation result; the run observed is not changed (its result digest stays the same). The cells drawn in the scene are the ones the observation sees, by the engine's own rule; picking two cells sets the region or the occluder.</div>
      <div className="eco-row" data-testid="xeno-observe-controls">
        <label>interval <select value={obs.sampling_interval} onChange={(e) => setObs({ ...obs, sampling_interval: Number(e.target.value) })}>{OBSERVATION_LIMITS.interval.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
        <label>resolution (stride) <select value={obs.spatial_stride} onChange={(e) => setObs({ ...obs, spatial_stride: Number(e.target.value) })}>{OBSERVATION_LIMITS.stride.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
        <label>aggregation <select value={obs.aggregation} onChange={(e) => setObs({ ...obs, aggregation: Number(e.target.value) })}>{OBSERVATION_LIMITS.aggregation.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
        <label>window <select value={obs.window} onChange={(e) => setObs({ ...obs, window: Number(e.target.value) })}>{OBSERVATION_LIMITS.window.map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
        <label>threshold <select value={obs.threshold ?? 0} onChange={(e) => setObs({ ...obs, threshold: Number(e.target.value) || null })}>{OBSERVATION_LIMITS.threshold.map((v) => <option key={v} value={v}>{v === 0 ? 'none' : v}</option>)}</select></label>
      </div>
      <div className="eco-row" role="group" aria-label="observation boundary">
        <button className={observeMode === 'region' ? 'on' : ''} aria-pressed={observeMode === 'region'} onClick={() => setObserveMode(observeMode === 'region' ? null : 'region')}>SET REGION: PICK TWO CELLS</button>
        <button className={observeMode === 'occluder' ? 'on' : ''} aria-pressed={observeMode === 'occluder'} onClick={() => setObserveMode(observeMode === 'occluder' ? null : 'occluder')}>SET OCCLUDER: PICK TWO CELLS</button>
        <button disabled={!obs.region} onClick={() => setObs({ ...obs, region: null })}>CLEAR REGION</button>
        <button disabled={!obs.occluder} onClick={() => setObs({ ...obs, occluder: null })}>CLEAR OCCLUDER</button>
        <button disabled={isFullObservation(obs)} onClick={() => setObs(FULL_OBSERVATION)}>FULL RESOLUTION</button>
        <button className={display.observedCells ? 'on' : ''} aria-pressed={display.observedCells} onClick={() => setDisplay({ ...display, observedCells: !display.observedCells })}>observed cells</button>
      </div>
      {observeMode && <div className="eco-note" data-testid="xeno-pick-hint"><b>{corner ? `Pick the opposite corner of the ${observeMode}: first corner is cell (${corner[0]}, ${corner[1]}).` : `Pick the first corner of the ${observeMode}: click a cell of the arena floor in the scene.`}</b></div>}
      <dl className="eco-kv" data-testid="xeno-observe-summary">
        <dt>cells seen</dt><dd>{seenCells(obs, rec.config.grid).filter(Boolean).length} of {rec.config.grid * rec.config.grid}{obs.region ? `; region ${obs.region.join(', ')}` : ''}{obs.occluder ? `; occluder ${obs.occluder.join(', ')}` : ''}</dd>
        <dt>engine's observation of this run</dt><dd>{observed ? `${observed.observed_cycles} of ${observed.true_cycles} cycles observed; observed ${observed.observed_state}, operational ${observed.operational_state}; ${observed.observability.status}` : 'full resolution: no separate observation result is requested'}</dd>
        <dt>the run itself</dt><dd>result digest {rec.result_digest.slice(0, 12)}: it covers the run's outputs (frames, events, cycles, status log, final status, termination, fields), not the observation; {pinned ? (pinned.resultDigest === rec.result_digest ? 'equal to the pinned side A: the same run' : 'DIFFERENT from the pinned side A: not the same run') : 'pin a regime to compare it with another'}</dd>
      </dl>
      <table className="eco-table" data-testid="xeno-entity-observation"><tbody>
        <tr><th>entity</th><th>reference (evaluator)</th><th>observation</th></tr>
        {entityObs.map((e) => <tr key={e.entity} title={e.reading}><td>{e.entity}</td><td><small>{e.reference.present ? `cell (${e.reference.cell[0]}, ${e.reference.cell[1]}), ${e.reference.active ? 'firing' : 'not firing'}` : 'absent'}</small></td><td><small>{e.observation.cellSeen ? 'cell seen' : 'cell NOT seen'}; {e.observation.tickSampled ? 'sampled tick' : 'tick not sampled'}{e.observation.observedStatus ? `; observed ${e.observation.observedStatus}` : ''}</small></td></tr>)}
      </tbody></table>
      <div className="eco-note">{entityObs.map((e) => e.reading).join(' · ')}</div>

      <h3>Track of the operational shape</h3>
      <div className="eco-track" data-testid="xeno-track">
        <div className="eco-trackrow"><small>operational (the run itself)</small>
          <div className="eco-strip" role="img" aria-label="operational status per tick">{track.operational.map((g) => <i key={g.from} className={g.label} style={{ flex: g.to - g.from + 1 }} title={`t=${g.from}-${g.to} ${g.label}`} onClick={() => setTick(g.from)} />)}</div></div>
        {track.observed && <div className="eco-trackrow"><small>observed (the configured observation)</small>
          <div className="eco-strip" role="img" aria-label="observed status per tick">{track.observed.map((g) => <i key={g.from} className={g.label} style={{ flex: g.to - g.from + 1 }} title={`t=${g.from}-${g.to} observed ${g.label}`} onClick={() => setTick(g.from)} />)}</div></div>}
        <div className="eco-trackmarks" aria-hidden="true">{track.marks.map((m, i) => <button key={i} className={`mark ${m.kind}`} style={{ left: `${(m.tick / Math.max(1, track.length - 1)) * 100}%` }} title={`t=${m.tick} ${m.label}`} onClick={() => setTick(m.tick)} />)}<i className="head" style={{ left: `${(tick / Math.max(1, track.length - 1)) * 100}%` }} /></div>
        <ul className="eco-log" data-testid="xeno-track-marks">{track.marks.map((m, i) => <li key={i}><button className="eco-span" onClick={() => setTick(m.tick)}>t={m.tick}</button> {m.kind}: {m.label}</li>)}</ul>
      </div>
      <div className="eco-note">The rows are read from the record: the status log (operational) and, when an observation result exists, the observed status per tick. Where they differ the observation is limited; that is not a change of the target. Every mark is an entry of the engine's own logs.</div>

      <h3>States of the operation, with their basis</h3>
      <table className="eco-table" data-testid="xeno-states"><tbody>
        <tr><th>state</th><th>at tick {tick}</th><th>time range in the record</th></tr>
        {opStates.states.map((x) => (
          <tr key={x.id}><td>{x.label}</td><td><span className={`eco-chip ${x.holdsAt ? 'iv-DERIVED' : 'iv-NOT_OCCURRED'}`}>{x.holdsAt ? 'rule holds' : 'does not hold'}</span></td>
            <td>{x.spans.length ? x.spans.slice(0, 3).map(([a, b]) => <button key={`${a}-${b}`} className="eco-span" onClick={() => setTick(a)}>{a === b ? `t=${a}` : `t=${a}–${b}`}</button>) : <small>never in this record</small>}{x.spans.length > 3 ? ` +${x.spans.length - 3}` : ''}
              <details><summary>basis</summary><small><b>rule:</b> {x.rule}. <b>reads:</b> {x.reads.join(', ')}. <b>engine values:</b> {x.engineValues.join('; ') || 'none'}. <b>observation:</b> {x.observationCondition}.</small></details></td></tr>
        ))}
      </tbody></table>
      <div className="eco-note" data-testid="xeno-judgement">ontological judgement: {opStates.ontologicalJudgement.replace('_', ' ')}. {opStates.note}</div>

      <h3>History: retention, addressability, re-entry, consequence</h3>
      <table className="eco-table" data-testid="xeno-history"><tbody>
        <tr><td>retention (trace held at tick {tick})</td><td><span className="eco-chip epi-reference">REFERENCE</span></td><td>A1 {history.retention.A1.toFixed(3)} · A2 {history.retention.A2.toFixed(3)}; re-entry channel {history.retention.enabled === null ? 'not recorded' : history.retention.enabled ? 'on' : 'OFF'}</td></tr>
        <tr><td>addressability</td><td><span className="eco-chip st-INSUFFICIENT_EVIDENCE">NOT MODELLED</span></td><td><small>{history.addressability.reason}</small></td></tr>
        <tr><td>re-entry (up to tick {tick})</td><td><span className="eco-chip epi-reference">REFERENCE</span></td><td>{history.reentry.cycles} of {history.reentry.ofCycles} cycles contain a history re-entry; threshold lowered by {history.reentry.A1.toFixed(3)} (A1), {history.reentry.A2.toFixed(3)} (A2)</td></tr>
        <tr><td>effective consequence</td><td><span className={`eco-chip ${consequence ? `verdict-${consequence.verdict === 'DIFFERS' ? 'CHANGED' : 'UNCHANGED'}` : 'verdict-UNRESOLVED'}`}>{consequence ? consequence.verdict.replace(/_/g, ' ') : 'UNRESOLVED'}</span></td>
          <td>{consequence ? <small>{consequence.note}. Baseline {consequence.base.label}, {consequence.base.cycles} cycles ({consequence.base.reentryCyclesInFinalWindow} with a re-entry in the final window); without history {consequence.withoutHistory.label}, {consequence.withoutHistory.cycles} cycles ({consequence.withoutHistory.reentryCyclesInFinalWindow}); status first differs at {consequence.firstStatusDivergence ?? 'never'}.</small> : <small>one record cannot show it: it needs a run of the same configuration with the history disabled</small>}</td></tr>
      </tbody></table>
      <div className="eco-row"><button disabled={busy} onClick={() => void requestHistoryOff(tick)} title="ask the engine to run the baseline's interventions plus DISABLE_HISTORY at this tick">TEST CONSEQUENCE: DISABLE HISTORY AT TICK {tick}</button></div>
      <div className="eco-note">A record that replays is not a re-entry, and a retained trace is not one either: re-entry is read where a cycle contains it, and its consequence only from the second run, for this configuration and seed.</div>

      <h3>Operational shape inspector</h3>
      <div className="eco-row">{ENTITY_NAMES.map((e) => <button key={e} className={shown === e ? 'on' : ''} disabled={!!entity} onClick={() => setWho(e)}>{e}</button>)}</div>
      <div className="eco-note">Readings for {shown} at tick {tick}. {entity ? 'The entity is the one selected on the stage.' : 'Select an entity on the stage, or choose one here.'} A hidden reference value is not an observation: it is listed apart and may not be available to an operational observer.</div>
      {GROUPS.map((g) => (
        <section key={g.key} className={`eco-epi eco-epi-${g.key}`} data-testid={`xeno-${g.key}`}>
          <h4><span className={`eco-chip epi-${g.key}`}>{g.title}</span> <small>{g.note}</small></h4>
          <table className="eco-table"><tbody>{inv[g.key].map((r) => <ReadingRow key={r.id} r={r} />)}</tbody></table>
        </section>
      ))}

      <section className="eco-epi eco-epi-unresolved" data-testid="xeno-unresolved">
        <h4><span className="eco-chip epi-unresolved">UNRESOLVED</span> <small>not settled by the current observation and experiment; never dropped</small></h4>
        <table className="eco-table"><tbody>{unresolved.map((u) => <tr key={u.id} className="eco-unresolved" title={u.reason}><td>{u.label}</td><td><small>{u.reason}</small></td></tr>)}</tbody></table>
      </section>

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
        <tr><th>experiment</th><th>mode</th><th>drawn</th></tr>
        {EXPERIMENTS.map((e) => <tr key={e.id} title={`${e.engine}. ${e.source}. State: ${e.own.state}. Interventions: ${e.own.interventions}. Observation: ${e.own.observation}. Span: ${e.own.span}. ${e.note}`}><td>{e.title}<br /><small>{e.note}</small></td><td><span className={`eco-chip exp-${e.mode}`}>{MODE_TEXT[e.mode]}</span></td><td><small>{SCENE_TEXT[e.scene]}</small></td></tr>)}
      </tbody></table>
      <div className="eco-note">Only an experiment with an engine here can be intervened on. TO-C1 is listed as what it is: its original source has not been supplied, so none of its numbers is shown or reproduced.</div>
    </>
  );
}
