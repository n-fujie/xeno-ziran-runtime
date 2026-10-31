import { useState } from 'react';
import type { RepairBlock, RepairLibraryOut, StressRow } from './meosApi';
import { failureOf, recoveryStrip, windowText, type RecoveryClass } from './repair';

// RESEARCH, sixth stage — world-state repair. Pick a stress and either a repair controller or explicit repair actions, run it, and read the result: the three horizons, the costs (raw, never weighted), the failure class, the controller's decisions, the reachable-recovery map and the
// minimum interventions of the saved experiments. Everything shown is a run of the engine or a saved experiment result; internal reconfiguration (class A) and world-state repair (class B) are kept apart in every row.

const CLASS_COLOR: Record<RecoveryClass, string> = { internal: '#2f8fd0', world: '#8a5fd0', combined: '#d0a02f', none: '#3a3d44' };
export interface RepairInitial { stress?: string; controller?: string; actions?: Array<{ action: string; magnitude: number; duration: number; t: number }> }
type Row = { action: string; magnitude: number; duration: number; t: number };

export default function RepairPanel({ lib, repair, initial, busy, onRun }: { lib: RepairLibraryOut | null; repair: RepairBlock | null; initial: RepairInitial; busy: boolean; onRun: (body: { stress: string; controller?: string | null; actions?: Row[] }) => void }) {
  const [stress, setStress] = useState(initial.stress ?? 'history lost'), [mode, setMode] = useState<'controller' | 'actions'>(initial.actions?.length ? 'actions' : 'controller'), [ctl, setCtl] = useState(initial.controller ?? 'rule_based');
  const [rows, setRows] = useState<Row[]>(initial.actions?.length ? initial.actions : [{ action: 'resource.pulse', magnitude: 1, duration: 0, t: 113 }]);
  if (!lib) return <fieldset className="eco-group"><legend>world-state repair (sixth stage)</legend><div className="eco-note">The repair library is not available on this server.</div></fieldset>;
  const fu = lib.followup ?? null, builtLater = new Set((fu?.actions ?? []).map((a) => a.id));
  const runnable = [...lib.actions.filter((a) => a.status !== 'not implemented' && a.class !== 'C'), ...(fu?.actions ?? [])], notImpl = lib.actions.filter((a) => a.status === 'not implemented' && !builtLater.has(a.id));
  const final = lib.final?.stress_table ?? [];
  const row = (i: number, patch: Partial<Row>) => setRows(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const spec = (id: string) => runnable.find((a) => a.id === id);
  const fail = repair ? failureOf(repair) : null;
  const ids = Object.keys(lib.stresses), cross = lib.cross;
  return (
    <fieldset className="eco-group" data-testid="eco-repair-panel" style={{ minWidth: 0 }}><legend>world-state repair (sixth stage)</legend>
      <div className="eco-note"><b>Three different things.</b> Internal reconfiguration (a component switched on or off) is class A; world-state repair (the coupling, the resource, the renewal, the Address) is class B; observation repair changes only what is observed and is shown in the observation table of the document. They are never counted as one.</div>
      <div className="eco-row"><label>stress <select value={stress} onChange={(e) => setStress(e.target.value)}>{[...ids, 'no stress'].map((s) => <option key={s} value={s}>{lib.stresses[s]?.label ?? s}</option>)}</select></label>
        <label>mode <select value={mode} onChange={(e) => setMode(e.target.value as 'controller' | 'actions')}><option value="controller">repair controller</option><option value="actions">explicit actions</option></select></label>
        {mode === 'controller' && <label>controller <select value={ctl} onChange={(e) => setCtl(e.target.value)}>{lib.controllers.map((c) => <option key={c}>{c}</option>)}</select></label>}</div>
      {mode === 'actions' && rows.map((r, i) => { const sp = spec(r.action); return (
        <div className="eco-row" key={i}><label>action <select value={r.action} onChange={(e) => { const s = spec(e.target.value); row(i, { action: e.target.value, magnitude: s?.magnitudes[0] ?? 0, duration: s?.durations[0] ?? 0 }); }}>{runnable.map((a) => <option key={a.id} value={a.id} title={a.label}>{`${a.id} [${a.class}${a.status === 'proxy' ? ', proxy' : ''}]`}</option>)}</select></label>
          {sp && sp.magnitudes.length > 0 && <label title={sp.magnitude_meaning}>magnitude <select value={r.magnitude} onChange={(e) => row(i, { magnitude: Number(e.target.value) })}>{sp.magnitudes.map((m) => <option key={m}>{m}</option>)}</select></label>}
          {sp && sp.durations.length > 1 && <label>duration <select value={r.duration} onChange={(e) => row(i, { duration: Number(e.target.value) })}>{sp.durations.map((d) => <option key={d}>{d}</option>)}</select></label>}
          <label>tick <input type="number" min={101} max={300} value={r.t} onChange={(e) => row(i, { t: Number(e.target.value) })} style={{ width: 62 }} /></label>
          {rows.length > 1 && <button onClick={() => setRows(rows.filter((_, k) => k !== i))}>remove</button>}
          {sp && <span className="dim">{sp.label}; declared cost: {Object.entries(sp.declared_cost).map(([k, v]) => `${k}: ${v}`).join(', ') || 'none'}; latency {sp.latency || '-'}; side effect: {sp.side_effect || '-'}; {sp.reversibility || ''}</span>}</div>); })}
      {mode === 'actions' && rows.length < 4 && <button onClick={() => setRows([...rows, { action: 'resource.pulse', magnitude: 1, duration: 0, t: R_T }])}>add a second action (a combined repair)</button>}
      <div className="eco-row"><button disabled={busy} data-testid="eco-repair-run" onClick={() => onRun({ stress, ...(mode === 'controller' ? { controller: ctl } : { actions: rows }) })}>RUN</button>
        <span className="dim">decision tick {lib.decision_tick}; the stress arrives at {lib.stress_tick}; horizons short {lib.horizons.short}, medium {lib.horizons.medium}, long {lib.horizons.long}; a recovery is ACTIVE on the last {lib.recovery_window} ticks, with no secondary collapse and the resource field not exhausted</span></div>

      {repair && (
        <div data-testid="eco-repair-result"><table className="eco-table"><thead><tr><th>horizon</th><th>outcome</th><th>success</th><th>latency</th><th>secondary collapse</th><th>resource exhausted</th></tr></thead>
          <tbody>{(['short', 'medium', 'long'] as const).map((k) => { const h = repair.evaluation.horizons[k]; return <tr key={k}><td>{`${k} (${lib.horizons[k]})`}</td><td>{h.outcome}</td><td><b>{h.success ? 'yes' : 'no'}</b></td><td>{h.latency ?? '-'}</td><td>{h.secondary_collapse ? 'yes' : 'no'}</td><td>{h.resource_exhausted ? 'yes' : 'no'}</td></tr>; })}</tbody></table>
          <dl className="eco-kv"><dt>stress</dt><dd>{`${repair.label} at tick ${repair.onset}`}</dd><dt>raw costs</dt><dd>{Object.entries(repair.evaluation.costs.raw).map(([k, v]) => `${k} ${v}`).join(' · ')}</dd><dt>normalised (by the undamaged run)</dt><dd>{Object.entries(repair.evaluation.costs.normalised).map(([k, v]) => `${k} ${v}`).join(' · ')}</dd>
            <dt>failure class</dt><dd>{fail ? `${fail.id}: ${fail.text}` : 'none: the run recovered'}</dd><dt>controller</dt><dd>{repair.controller.attempts} attempt(s); {repair.controller.log.length} decision(s)</dd></dl>
          {repair.controller.log.length > 0 && <table className="eco-table" data-testid="eco-repair-decisions"><thead><tr><th>tick</th><th>detected</th><th>available</th><th>rejected</th><th>selected</th><th>est. cost</th><th>expected</th><th>actual</th></tr></thead>
            <tbody>{repair.controller.log.map((e, i) => { const x = e as { tick: number; detected: string[]; available: string[]; rejected: unknown[]; selected: string | null; estimated_cost: number | null; expected_recovery: number | null; actual: { recovered_so_far: boolean } | null };
              return <tr key={i}><td>{x.tick}</td><td>{x.detected.join(', ')}</td><td>{x.available.length}</td><td>{x.rejected.length}</td><td>{x.selected ?? 'none available'}</td><td>{x.estimated_cost ?? '-'}</td><td>{x.expected_recovery ?? '-'}</td><td>{x.actual ? (x.actual.recovered_so_far ? 'recovered' : 'not recovered') : '-'}</td></tr>; })}</tbody></table>}</div>)}

      <details open><summary className="dim">reachable recovery · by stress and tick (tested action space)</summary>
        {final.length ? <div data-testid="eco-recovery-map">{final.map((r: StressRow) => (
          <div key={r.stress} style={{ margin: '6px 0' }}><div className="dim">{`${r.label}: ${r.classification_at_any_tested_tick}${r.irreversibility === 'OPEN_THROUGH_TESTED_LIMIT' ? ` · OPEN_THROUGH_TESTED_LIMIT: still effective at tick ${r.tested_range_end}, the end of the tested range; irreversible tick null` : r.latest_successful_repair_tick !== null ? ` · latest successful repair tick ${r.latest_successful_repair_tick} · earliest irreversible ${r.irreversible_tick}` : ' · no tested action recovers it at any tested tick'}`}</div>
            <div style={{ display: 'flex', height: 12 }} title="ticks 101-420, one cell per tick">{recoveryStrip(r).map((c) => <i key={c.tick} title={`tick ${c.tick}: ${c.classes.join(' + ')}`} style={{ flex: 1, background: CLASS_COLOR[c.classes[0]], opacity: c.classes[0] === 'none' ? 0.35 : 1 }} />)}</div></div>))}
          <div className="eco-legend">{(Object.keys(CLASS_COLOR) as RecoveryClass[]).map((k) => <span key={k}><i style={{ background: CLASS_COLOR[k] }} />{k === 'none' ? 'no tested action recovers' : `recovered by ${k === 'internal' ? 'internal reconfiguration' : k === 'world' ? 'a world-state repair' : 'a combined repair'}`}</span>)}</div>
          <div className="eco-note">A coloured cell is a tick at which a tested setting recovered the run, sustained to every applicable horizon, on all exploration and all validation seeds. The strip is a region of the action space that was tested, not of the world; the unrepaired run collapses at tick 144-159. A window still effective at the last tick tested would be OPEN_THROUGH_TESTED_LIMIT (not closed, no irreversible tick claimed); the three that were open at tick 330 were measured on to tick 1140 with an extended horizon and all closed.</div></div> : <div className="eco-note">Run backend/scripts/meos_experiments_stage6_final.py to build the table.</div>}
      </details>

      <details open><summary className="dim">stress table: repairability, windows, minimum effective action</summary>
        <table className="eco-table" data-testid="eco-stress-table"><thead><tr><th>stress</th><th>at the decision tick</th><th>at any tested tick</th><th>windows</th><th>minimum effective</th></tr></thead>
          <tbody>{final.map((r) => <tr key={r.stress}><td>{r.label}</td><td>{r.classification_at_decision_tick_113}</td><td>{r.classification_at_any_tested_tick}</td><td>{windowText(r.timing_window_fragments)}</td><td>{r.minimum_effective.map((m) => `${m.action} ${m.magnitude}`).join('; ') || '-'}</td></tr>)}</tbody></table></details>

      <details open><summary className="dim">resource pulse: insufficient / effective / overshoot</summary>
        <table className="eco-table" data-testid="eco-pulse-bands"><thead><tr><th>stress</th><th>effective band</th><th>phases by pulse size</th></tr></thead>
          <tbody>{Object.entries(lib.final?.resource_non_monotonicity ?? {}).map(([sid, p]) => <tr key={sid}><td>{lib.stresses[sid]?.label ?? sid}</td><td>{p.effective_band[0] === null ? 'none' : `${p.effective_band[0]} - ${p.effective_band[1]}`}</td><td>{p.phases.map((b) => `${b.phase} ${b.from}-${b.to}`).join('; ')}</td></tr>)}</tbody></table></details>

      {fu?.results && (
        <details open><summary className="dim">extended action space (engine meos-0.5): coupling.bypass, resource.rerouting, address.temporary_local</summary>
          <table className="eco-table" data-testid="eco-followup-classes"><thead><tr><th>stress</th><th>decision tick, original</th><th>decision tick, extended</th><th>any tested tick, original</th><th>any tested tick, extended</th></tr></thead>
            <tbody>{Object.entries(fu.results.classification).map(([sid, c]) => <tr key={sid}><td>{lib.stresses[sid]?.label ?? sid}</td><td>{c.original_at_decision_tick_113}</td><td>{c.extended_at_decision_tick_113}</td><td>{c.original_at_any_tested_tick}</td><td>{c.extended_at_any_tested_tick}</td></tr>)}</tbody></table>
          <div className="eco-note">The original columns are the frozen Stage 6 classification (the three actions were not built). The extended columns add them, with the same protocol (exploration seeds 1-5, validation 6-10).</div></details>)}
      {fu?.open_windows && (
        <details open><summary className="dim">windows that were open at tick 330, measured on with the extended horizon</summary>
          <table className="eco-table" data-testid="eco-open-windows"><thead><tr><th>stress</th><th>setting</th><th>ticks tested</th><th>latest effective tick</th><th>effective intervals (last)</th></tr></thead>
            <tbody>{fu.open_windows.windows.map((w, i) => <tr key={i}><td>{lib.stresses[w.stress]?.label ?? w.stress}</td><td>{w.parts.map((p) => `${p[0]} ${p[1]}`).join(' + ')}</td><td>{`${w.ticks_tested[0]}-${w.ticks_tested[1]}`}</td><td>{w.latest_effective_tick ?? 'none'}</td><td>{w.effective_intervals.slice(-2).map((x) => `${x[0]}-${x[1]}`).join(', ') || '-'}</td></tr>)}</tbody></table>
          <div className="eco-note">{`Horizon ${fu.open_windows.extended_horizon}: an action tick is tested up to ${fu.open_windows.last_tick_tested}. A window still effective at the last tick tested would be OPEN_THROUGH_TESTED_LIMIT; here each ended earlier.`}</div></details>)}

      {cross && (
        <>
          <details open><summary className="dim">repairability by MFS (the repairs validated on the full arrangement, tried on each MFS, seeds 1-5)</summary>
            <table className="eco-table" data-testid="eco-mfs-repairability" style={{ width: 430, maxWidth: "100%", tableLayout: "fixed", fontSize: 9, wordBreak: "break-word" }}><thead><tr><th>stress</th>{Object.keys(cross.C1_mfs.profile).map((m) => <th key={m}>{m}</th>)}</tr></thead>
              <tbody>{Object.keys(Object.values(cross.C1_mfs.profile)[0] ?? {}).map((sid) => <tr key={sid}><td>{lib.stresses[sid]?.label ?? sid}</td>{Object.values(cross.C1_mfs.profile).map((p, i) => <td key={i}>{p[sid]}</td>)}</tr>)}</tbody></table></details>
          <details open><summary className="dim">Address: operational, Address and observability restoration are three measures</summary>
            <table className="eco-table" data-testid="eco-address-three"><thead><tr><th>case</th><th>operation restored</th><th>Address restored</th><th>observer agrees</th><th>Address integrity</th></tr></thead>
              <tbody>{cross.C4_address_three_restorations.rows.map((r) => <tr key={r.case}><td>{r.case}</td><td>{r.operational_restoration}</td><td>{r.address_restoration}</td><td>{r.observability_restoration}</td><td>{r.mean_address_integrity}</td></tr>)}</tbody></table></details>
          <details open><summary className="dim">observation: operational recovery is not observed recovery</summary>
            <table className="eco-table" data-testid="eco-observation-recovery"><thead><tr><th>run</th><th>observation</th><th>operational</th><th>observed</th><th>observability</th><th>operational recovery</th><th>observed recovery</th></tr></thead>
              <tbody>{cross.C3_observation.rows.filter((r) => r.run.startsWith('coupling stress, resource pulse')).map((r) => <tr key={r.observation}><td>{r.run.slice(0, 40)}</td><td>{r.observation}</td><td>{r.operational_state}</td><td>{r.observed_state}</td><td>{r.observability_status}</td><td>{r.operational_recovery ? 'yes' : 'no'}</td><td>{r.observed_recovery ? 'yes' : 'no'}</td></tr>)}</tbody></table></details>
        </>
      )}

      <details><summary className="dim">actions the engine cannot do (never run or simulated by something else)</summary>
        <ul>{notImpl.map((a) => <li key={a.id}><b>{a.id}</b>: {a.note}</li>)}{lib.actions.filter((a) => a.status === 'proxy').map((a) => <li key={a.id}><b>{a.id}</b> (proxy): {a.note}</li>)}</ul></details>
    </fieldset>
  );
}
const R_T = 113;
