import { useMemo, useState } from 'react';
import { FULL_OBSERVATION, type MeosRecord, type Observation, type RunOut, type SssClassOut } from './meosApi';
import { ENTITY_NAMES, type EntityName } from './layers';
import {
  compareRegimes, criticalIntervals, fiveS, humanDependencies, inventory, provenance, strongXenoscience,
  type Reading, type RegimeSide,
} from './xenoscience';

// XENOSCIENCE — the research readings of the current run. Every number is read from the record or from the engine's observation result (see xenoscience.ts); this pane never runs
// the engine and never edits a run. Observed, inferred and reference (evaluator-only) readings are kept in separate groups, and what the engine cannot establish is shown as such.

export interface XenoscienceCtx { rec: MeosRecord | null; out: RunOut | null; tick: number; setTick: (t: number) => void; obs: Observation; entity: EntityName | null; sssClass: SssClassOut | null; pinned: RegimeSide | null; setPinned: (p: RegimeSide | null) => void }

const GROUPS: Array<{ key: 'observed' | 'inferred' | 'reference'; title: string; note: string }> = [
  { key: 'observed', title: 'OBSERVED', note: 'recorded through the configured observation array' },
  { key: 'inferred', title: 'INFERRED', note: 'reconstructed by a declared analytical procedure' },
  { key: 'reference', title: 'REFERENCE (hidden from the observer)', note: "the evaluator's internal state; never an observation" },
];

const ReadingRow = ({ r }: { r: Reading }) => <tr title={r.why} className={r.availability === 'UNRESOLVED' ? 'eco-unresolved' : undefined}><td>{r.label}</td><td>{r.value}</td></tr>;

export default function XenosciencePane({ rec, out, tick, setTick, obs, entity, sssClass, pinned, setPinned }: XenoscienceCtx) {
  const [who, setWho] = useState<EntityName>(entity ?? 'A1');
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
  if (!rec || !inv || !prov || !strong) return <div className="eco-note">Run an experiment first: the Xenoscience readings are read from its record.</div>;
  const n = rec.frames.length;
  const shown = entity ?? who;

  return (
    <>
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
        <dt>initial configuration digest</dt><dd>{prov.initialConfigDigest}</dd>
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
    </>
  );
}
