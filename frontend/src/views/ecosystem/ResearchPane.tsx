import { useMemo, useState } from 'react';
import {
  BOUNDARY_KINDS, addressIntervention, boundaryPerturbation, runLog, runLogCsv, FULL_OBSERVATION,
  type AddressInterventionOut, type BoundaryKind, type BoundaryPerturbationOut, type Intervention, type MeosRecord, type Observation, type Observed, type PathActivity, type SssClassOut,
} from './meosApi';
import { deltaSnapshots, inspectAt, MARKER_COLOR, MARKER_LABEL, snapshotTicks, type Inspect, type Marker } from './research';
import { affected } from './researchMap';
import type { LibraryMfs, Outcome, RouteState } from './routeGraph';
import MfsResults, { type MfsInitial } from './MfsResults';
import RepairPanel, { type RepairInitial } from './RepairPanel';
import type { RepairBlock, RepairLibraryOut } from './meosApi';
import type { LibraryOut } from './mfsPanels';

// RESEARCH — the experiment console and the readings of a run. Everything under "MODEL RESULT" is read from the record or returned by the engine; "VISUAL REPRESENTATION" says how the
// bodies and the sheet are posed for it. The console builds interventions (and the observation configuration) and re-runs the engine; it never edits a run.

export interface ResearchCtx {
  rec: MeosRecord | null; out: { observed?: Observed; paths?: PathActivity } | null; tick: number; setTick: (t: number) => void; obs: Observation; setObs: (o: Observation) => void;
  conn: { m2: string; m2w: number; m2t: number; phil: string; channel: string; power: string }; setConn: (c: ResearchCtx['conn']) => void;
  ivs: Intervention[]; execute: (l: Intervention[], t: number | null) => Promise<void>; cfg: Record<string, unknown>; seed: number; markers: Marker[]; inspect: Inspect | null;
  sssClass: SssClassOut | null; sssRegion: string; compare: boolean; setCompare: (b: boolean) => void; busy: string | null; wrap: (name: string, fn: () => Promise<void>) => Promise<void>;
  setTab: (t: 'technical') => void; openMarker: Marker | null; setOpenMarker: (m: Marker | null) => void;
  library: LibraryMfs[]; routeState: RouteState | null; outcomes: Outcome[]; runControlled: (controller: string, scenario: string) => Promise<void>;
  libraryOut: LibraryOut | null; initialMfs: MfsInitial; runMfs: (id: string) => Promise<void>; initialRoute?: { controller: string; scenario: string };
  repairLib?: RepairLibraryOut | null; repair?: RepairBlock | null; initialRepair?: RepairInitial; runRepair?: (body: { stress: string; controller?: string | null; actions?: Array<{ action: string; magnitude: number; duration: number; t: number }> }) => Promise<void>;
}

const REGIONS: Array<[string, number[] | null]> = [['whole arena', null], ['left half', [0, 0, 6, 13]], ['right half', [7, 0, 13, 13]], ['centre', [3, 3, 10, 10]], ['around A1 and A2', [2, 4, 6, 8]], ['A1 cell only', [3, 6, 3, 6]], ['away from both', [8, 8, 12, 12]], ['corner', [0, 0, 3, 3]]];
const OCCLUDERS: Array<[string, number[] | null]> = [['none', null], ['over A1', [3, 6, 3, 6]], ['over A1 and A2', [3, 5, 5, 7]], ['left strip', [0, 0, 2, 13]]];
const SCENARIO_NAMES = ['no stress (control for false switches)', 'history lost', 'coupling weakened (gain 0.5)', 'resource reduced', 'renewal efficiency 0.6', 'renewal disabled', 'Address degraded (A2 partial 50 %)'];
const Chip = ({ s }: { s: string }) => <span className={`eco-chip ${s}`}>{s}</span>;
const download = (name: string, text: string, type: string) => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); };

export default function ResearchPane(c: ResearchCtx) {
  const { rec, obs, setObs, conn, setConn } = c;
  const [bk, setBk] = useState<BoundaryKind>('coupling'), [dur, setDur] = useState(40), [bnd, setBnd] = useState<BoundaryPerturbationOut | null>(null);
  const [am, setAm] = useState({ mode: 'loss', target: 'A2', x: 9, y: 6, fraction: 0.5, delay: 20, duration: 40, restoreAfter: 40 }), [adr, setAdr] = useState<AddressInterventionOut | null>(null);
  const [sss, setSss] = useState({ scale: 1, size: 1, speed: 1 }), [pulse, setPulse] = useState(2), [renew, setRenew] = useState(0.8);
  const [snap, setSnap] = useState<'baseline' | 'intervention' | 'recovered'>('baseline');
  const [ctlKind, setCtlKind] = useState(c.initialRoute?.controller ?? 'adaptive'), [scen, setScen] = useState(c.initialRoute?.scenario ?? 'coupling weakened (gain 0.5)');  // a deep link names them
  const tk = useMemo(() => (rec ? snapshotTicks(rec) : null), [rec]);
  const disabled = !rec || !!c.busy;
  const at = Math.min(c.tick, (rec?.frames.length ?? 1) - 1);
  const add = (list: Intervention[]) => void c.execute([...c.ivs, ...list.map((iv) => ({ ...iv }))], c.tick);
  const lim = (t: number) => Math.min(t, (rec?.frames.length ?? 1) - 1);
  const pair = (cut: Omit<Intervention, 'tick'>, back: Omit<Intervention, 'tick'>) => add([{ ...cut, tick: at } as Intervention, { ...back, tick: lim(at + dur) } as Intervention]);
  const o = c.out?.observed;

  const applyBoundary = () => {
    if (bk === 'observation') { setObs({ ...obs, region: [0, 0, 2, 13] }); return; }
    if (bk === 'coupling') pair({ op: 'ISOLATE', target: 'interaction_channel' }, { op: 'RECONNECT', target: 'interaction_channel' });
    else if (bk === 'resource_exchange') pair({ op: 'ISOLATE', target: 'feedback' }, { op: 'RECONNECT', target: 'feedback' });
    else if (bk === 'history_access') pair({ op: 'ISOLATE', target: 'history' }, { op: 'RECONNECT', target: 'history' });
    else pair({ op: 'ADDRESS', target: 'A2', mode: 'loss' }, { op: 'ADDRESS', target: 'A2', mode: 'restore' });
  };
  const applyAddress = () => {
    const a = am, iv: Intervention = { tick: at, op: 'ADDRESS', target: a.target, mode: a.mode,
      ...(a.mode === 'reassign' || a.mode === 'delayed' ? { x: a.x, y: a.y } : {}), ...(a.mode === 'fragment' || a.mode === 'partial' ? { fraction: a.fraction } : {}), ...(a.mode === 'delayed' ? { delay: a.delay } : {}), ...(a.mode === 'stale' && a.duration > 0 ? { duration: a.duration } : {}) };
    add(a.restoreAfter > 0 && !['restore', 'reassign', 'delayed'].includes(a.mode) ? [iv, { tick: lim(at + a.restoreAfter), op: 'ADDRESS', target: a.target, mode: 'restore' }] : [iv]);
  };
  const runBoundary = () => c.wrap('boundary perturbation', async () => setBnd(await boundaryPerturbation(c.cfg, { kind: bk, tick: Math.max(20, at), duration: dur, seeds: [c.seed] })));
  const runAddress = () => c.wrap('Address Domain intervention', async () => setAdr(await addressIntervention(c.cfg, { mode: am.mode === 'restore' ? 'loss' : am.mode, target: am.target, tick: Math.max(20, at), duration: am.restoreAfter || 40, seed: c.seed, params: { x: am.x, y: am.y, fraction: am.fraction, delay: am.delay } })));
  const jump = (k: 'baseline' | 'intervention' | 'recovered') => { setSnap(k); if (tk) c.setTick(tk[k]); };
  const exportLog = (fmt: 'json' | 'csv') => c.wrap(`run log (${fmt})`, async () => {
    const stem = `meos-run-seed${c.seed}-${rec?.result_digest.slice(0, 8) ?? 'x'}`, obsBody = JSON.stringify(obs) === JSON.stringify(FULL_OBSERVATION) ? undefined : { ...obs };
    if (fmt === 'json') download(`${stem}.json`, JSON.stringify(await runLog(c.cfg, c.ivs, obsBody), null, 1), 'application/json'); else download(`${stem}.csv`, await runLogCsv(c.cfg, c.ivs, obsBody), 'text/csv');
  });
  const num = (v: number, set: (n: number) => void, step = 1, min = 0, max = 99) => <input type="number" step={step} min={min} max={max} value={v} style={{ width: 54 }} onChange={(e) => set(Number(e.target.value))} />;
  const ins = c.inspect;

  return (
    <>
      <h3>RESEARCH · experiment console</h3>
      <div className="eco-note">Every control below builds an intervention or an observation configuration; the run is recomputed from the recorded seed (nothing is edited in place). <b>MODEL RESULT</b> is read from the record; <b>VISUAL REPRESENTATION</b> says how the bodies and the sheet are posed and is never evidence about the run.</div>

      <fieldset className="eco-group"><legend>observation (research observer)</legend>
        <div className="eco-row">
          <label title="ticks between samples">interval <select value={obs.sampling_interval} onChange={(e) => setObs({ ...obs, sampling_interval: Number(e.target.value) })}>{[1, 2, 3, 4, 6, 8, 12].map((h) => <option key={h}>{h}</option>)}</select></label>
          <label title="every n-th cell is resolved">spatial resolution (stride) <select value={obs.spatial_stride} onChange={(e) => setObs({ ...obs, spatial_stride: Number(e.target.value) })}>{[1, 2, 3, 4, 6].map((h) => <option key={h}>{h}</option>)}</select></label>
          <label title="ticks over which the observer counts cycles">window <select value={obs.window} onChange={(e) => setObs({ ...obs, window: Number(e.target.value) })}>{[6, 12, 24, 48, 96].map((h) => <option key={h}>{h}</option>)}</select></label>
        </div>
        <div className="eco-row">
          <label>region <select value={obs.region ? obs.region.join(',') : 'all'} onChange={(e) => setObs({ ...obs, region: e.target.value === 'all' ? null : e.target.value.split(',').map(Number) })}>{REGIONS.map(([n, r]) => <option key={n} value={r ? r.join(',') : 'all'}>{n}</option>)}</select></label>
          <label title="a boundary that hides what is inside it from the observer">occluder <select value={obs.occluder ? obs.occluder.join(',') : 'none'} onChange={(e) => setObs({ ...obs, occluder: e.target.value === 'none' ? null : e.target.value.split(',').map(Number) })}>{OCCLUDERS.map(([n, r]) => <option key={n} value={r ? r.join(',') : 'none'}>{n}</option>)}</select></label>
          <label title="the observer detects only events whose signal is at least this">detection threshold <select value={obs.threshold ?? ''} onChange={(e) => setObs({ ...obs, threshold: e.target.value === '' ? null : Number(e.target.value) })}><option value="">off</option>{[0.05, 0.1, 0.2, 0.3, 0.5, 0.9].map((h) => <option key={h}>{h}</option>)}</select></label>
          <label title="the observer attributes an event to a configuration only while its address integrity is at least this">address resolution <select value={obs.address_resolution ?? ''} onChange={(e) => setObs({ ...obs, address_resolution: e.target.value === '' ? null : Number(e.target.value) })}><option value="">off</option>{[0.25, 0.5, 0.75, 1].map((h) => <option key={h}>{h}</option>)}</select></label>
          <button onClick={() => setObs(FULL_OBSERVATION)} disabled={JSON.stringify(obs) === JSON.stringify(FULL_OBSERVATION)}>full resolution</button>
        </div>
        {o ? <dl className="eco-kv"><dt>operational state (end of run)</dt><dd><Chip s={o.operational_state} /> ({o.true_cycles} cycles)</dd><dt>observed state (end of run)</dt><dd><Chip s={o.observed_state} /> ({o.observed_cycles} cycles resolved)</dd>
          <dt>observability</dt><dd>{o.observability?.status ?? o.observability_status}{o.limiting_parameters.length ? ` — limited by ${o.limiting_parameters.join(', ')}` : ''}{o.observability?.observed_collapse_is_artifact ? ' — the observed collapse is a limit of the observation, not a collapse of the run' : ''}</dd></dl> : <div className="eco-note">full-resolution observation: the observed state is the operational state.</div>}
      </fieldset>

      <fieldset className="eco-group"><legend>XenoBody boundary</legend>
        <div className="eco-row">
          <label>boundary <select value={bk} onChange={(e) => setBk(e.target.value as BoundaryKind)}>{BOUNDARY_KINDS.map((k) => <option key={k}>{k}</option>)}</select></label>
          <label>for <input type="number" min={1} max={200} value={dur} style={{ width: 54 }} onChange={(e) => setDur(Number(e.target.value))} /> ticks</label>
          <button disabled={disabled} onClick={applyBoundary} title="adds the cut at the current tick and its restoration after the duration (the observation boundary is set in the observation group)">APPLY at tick {at}</button>
          <button disabled={disabled} onClick={runBoundary} title="runs the unperturbed, perturbed, restored and pulsed runs and reports before / after">REPORT</button>
        </div>
        <div className="eco-row"><span className="dim">relations</span>
          <button disabled={disabled} onClick={() => add([{ tick: at, op: 'ISOLATE', target: 'interaction_channel' }])}>cut coupling</button><button disabled={disabled} onClick={() => add([{ tick: at, op: 'RECONNECT', target: 'interaction_channel' }])}>restore coupling</button>
          <button disabled={disabled} onClick={() => add([{ tick: at, op: 'ISOLATE', target: 'history' }])}>cut history access</button><button disabled={disabled} onClick={() => add([{ tick: at, op: 'RECONNECT', target: 'history' }])}>restore history</button>
          <button disabled={disabled} onClick={() => add([{ tick: at, op: 'ISOLATE', target: 'feedback' }])}>cut renewal feedback</button><button disabled={disabled} onClick={() => add([{ tick: at, op: 'RECONNECT', target: 'feedback' }])}>restore feedback</button>
        </div>
        {bnd && <><table className="eco-table"><thead><tr><th>seed</th><th>before</th><th>end of perturbation</th><th>restored</th><th>+ pulse</th><th>collapse</th><th>observed / observability</th></tr></thead>
          <tbody>{bnd.rows.map((r) => <tr key={r.seed}><td>{r.seed}</td><td><Chip s={r.state_before} /></td><td><Chip s={r.state_end_of_perturbation} /></td><td><Chip s={r.state_final_restored} /></td><td><Chip s={r.state_final_restored_and_pulse} /></td><td>{r.collapse_tick ?? '-'}</td><td>{r.observability.observed_state} / {r.observability.status}</td></tr>)}</tbody></table>
          <dl className="eco-kv"><dt>boundary</dt><dd>{bnd.label}</dd><dt>cut directly</dt><dd>{bnd.paths_cut_directly.join(', ') || 'none (an observation boundary cuts no relation)'}</dd><dt>changed (incl. downstream)</dt><dd>{bnd.affected_paths.join(', ') || 'none'}</dd>
            <dt>recovery</dt><dd>without a pulse: {bnd.rows[0].recovers_without_pulse ? 'yes' : 'no'}; with a pulse: {bnd.rows[0].recovers_with_pulse ? 'yes' : 'no'} (a pulse alone into the unperturbed run: {bnd.rows[0].state_final_unperturbed_and_pulse})</dd>
            {Object.entries(bnd.bodies).map(([k, b]) => <><dt key={k + 'd'}>{k}</dt><dd key={k}>{b.label}: legs broken {b.legs_broken_by_perturbation.length}/{b.legs_closed_count} closed; affected inside {b.affected_inside.join(', ') || 'none'}</dd></>)}</dl></>}
      </fieldset>

      <fieldset className="eco-group"><legend>Address Domain</legend>
        <div className="eco-row">
          <select value={am.mode} onChange={(e) => setAm({ ...am, mode: e.target.value })}>{['loss', 'reassign', 'fragment', 'collision', 'partial', 'delayed', 'stale', 'restore'].map((m) => <option key={m}>{m}</option>)}</select>
          <select value={am.target} onChange={(e) => setAm({ ...am, target: e.target.value })}>{['A1', 'A2', 'both'].map((m) => <option key={m}>{m}</option>)}</select>
          {(am.mode === 'reassign' || am.mode === 'delayed') && <>x {num(am.x, (x) => setAm({ ...am, x }), 1, 0, 13)} y {num(am.y, (y) => setAm({ ...am, y }), 1, 0, 13)}</>}
          {(am.mode === 'fragment' || am.mode === 'partial') && <>fraction {num(am.fraction, (fraction) => setAm({ ...am, fraction }), 0.25, 0, 1)}</>}
          {am.mode === 'delayed' && <>update after {num(am.delay, (delay) => setAm({ ...am, delay }), 1, 1, 100)} ticks</>}
          {am.mode === 'stale' && <>lasts {num(am.duration, (duration) => setAm({ ...am, duration }), 5, 0, 400)} ticks (0 = until restored)</>}
          {!['restore', 'reassign', 'delayed', 'stale'].includes(am.mode) && <>restore after {num(am.restoreAfter, (restoreAfter) => setAm({ ...am, restoreAfter }), 5, 0, 200)} (0 = never)</>}
          <button disabled={disabled} onClick={applyAddress}>APPLY at tick {at}</button><button disabled={disabled || am.mode === 'restore'} onClick={runAddress}>REPORT</button>
        </div>
        <div className="eco-note">loss, reassignment, fragmentation, collision, partial addressability, a delayed update (the body moves, its address names the old cell until the update arrives), a stale address (it stops following the body); recovery after reassignment is a reassignment back.</div>
        {adr && <table className="eco-table"><thead><tr><th>tick</th><th>mode</th><th>address</th><th>old → new</th><th>path</th><th>operational</th><th>observed</th><th>recovery</th></tr></thead>
          <tbody>{adr.effects.map((e, i) => <tr key={i}><td>{e.tick}</td><td>{e.mode}</td><td>{e.affected_address.join(', ')}</td><td>{e.affected_address.map((n) => `${n}: ${JSON.stringify((e.old_state[n] as { mode?: string }).mode ?? 'intact')} → ${JSON.stringify((e.new_state[n] as { mode?: string }).mode ?? 'intact')}`).join('; ')}</td><td>{e.affected_path.join(', ')}</td><td>{e.operational_effect.worst_state_after}{e.operational_effect.collapse_tick != null ? ` @${e.operational_effect.collapse_tick}` : ''}</td><td>{e.observed_effect.observed_state_final} / {e.observed_effect.observability}</td><td>{e.recovery_status}{e.recovery_with_pulse ? ` · with pulse: ${e.recovery_with_pulse}` : ''}</td></tr>)}</tbody></table>}
      </fieldset>

      <fieldset className="eco-group"><legend>SSS · history · resource · M2</legend>
        <div className="eco-row">{(['scale', 'size', 'speed'] as const).map((k) => <label key={k}>{k} {num(sss[k], (v) => setSss({ ...sss, [k]: v }), 0.05, 0.25, 4)}</label>)}
          <button disabled={disabled} onClick={() => add([{ tick: at, op: 'ALTER_SSS', ...sss }])}>APPLY SSS at tick {at}</button>
          <span>region <Chip s={c.sssRegion} /></span></div>
        <div className="eco-row"><span className="dim">resource</span>{num(pulse, setPulse, 0.25, 0, 20)}<button disabled={disabled} onClick={() => add([{ tick: at, op: 'ALTER_RESOURCE', inject: { x: 3, y: 6, amount: pulse } }])}>pulse at (3, 6)</button>
          renewal efficiency {num(renew, setRenew, 0.05, 0.1, 2)}<button disabled={disabled} onClick={() => add([{ tick: at, op: 'RECONFIGURE', path: 'environment.renew_efficiency', value: renew }])}>set</button>
          <label>power <select value={conn.power} onChange={(e) => setConn({ ...conn, power: e.target.value })}><option>finite</option><option>unlimited</option></select></label></div>
        <div className="eco-row"><label title="A1 also senses M2, the alteration A2's reconfiguration leaves">M2 → A1 <select value={conn.m2} onChange={(e) => setConn({ ...conn, m2: e.target.value })}>{['none', 'direct', 'delayed', 'noisy', 'threshold'].map((m) => <option key={m}>{m}</option>)}</select></label>
          weight {num(conn.m2w, (m2w) => setConn({ ...conn, m2w }), 0.25, 0.25, 4)}{conn.m2 === 'threshold' && <>threshold {num(conn.m2t, (m2t) => setConn({ ...conn, m2t }), 0.05, 0, 2)}</>}</div>
      </fieldset>

      <fieldset className="eco-group" data-testid="eco-reconfiguration"><legend>reconfiguration (fifth stage)</legend>
        <div className="eco-row"><label>scenario <select value={scen} onChange={(e) => setScen(e.target.value)}>{SCENARIO_NAMES.map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>controller <select value={ctlKind} onChange={(e) => setCtlKind(e.target.value)}>{['none', 'fixed', 'adaptive', 'adaptive_shed', 'delayed', 'noisy'].map((x) => <option key={x}>{x}</option>)}</select></label>
          <button disabled={!c.library.length || !!c.busy} onClick={() => void c.wrap('controlled run', () => c.runControlled(ctlKind, scen))} title="a stress at tick 100 on an arrangement with the M2 tap installed and dormant; the controller senses, matches the saved MFS library and moves between known MFS">RUN</button></div>
        <div className="eco-note">{c.library.length ? `${c.library.length} MFS in the saved library (experiment F). The controller reads only the run's traces; what it senses, the candidates, the choice and its cost are in the timeline markers and the inspection.` : 'The MFS library is not saved on this server: run backend/scripts/meos_experiments_v5.py.'}</div>
        {c.outcomes.length > 0 && <table className="eco-table"><thead><tr><th>tick</th><th>from → to</th><th>trigger</th><th>cost</th><th>lost ticks</th><th>latency</th><th>preserved</th></tr></thead><tbody>{c.outcomes.map((o, i) => <tr key={i}><td>{o.tick}</td><td>{o.from} → {o.to}</td><td>{o.trigger.join(', ')}</td><td>{o.cost}</td><td>{o.operation_lost_ticks_after}</td><td>{o.recovery_latency ?? '-'}</td><td>{o.preserved_at_end ? 'yes' : 'no'}</td></tr>)}</tbody></table>}
        {c.library.length > 0 && <details><summary className="dim">the MFS library</summary><table className="eco-table"><thead><tr><th>MFS</th><th>condition</th><th>route</th><th>retained</th></tr></thead><tbody>{c.library.map((m) => <tr key={m.id}><td>{m.id}</td><td>{m.condition}</td><td>{m.route_kind}</td><td>{m.retained.join(', ')}</td></tr>)}</tbody></table></details>}
      </fieldset>

      <RepairPanel lib={c.repairLib ?? null} repair={c.repair ?? null} initial={c.initialRepair ?? {}} busy={!!c.busy} onRun={(b) => void c.wrap('repaired run', () => c.runRepair!(b))} />

      <MfsResults lib={c.libraryOut} initial={c.initialMfs} seed={c.seed} busy={!!c.busy} onRun={(id) => void c.wrap(`running ${id}`, () => c.runMfs(id))} />

      <div className="eco-two">
        <div className="mr"><h4>MODEL RESULT · the record at tick {c.tick}</h4>
          {ins ? <dl className="eco-kv"><dt>operational</dt><dd><Chip s={ins.operational} /></dd><dt>observed</dt><dd>{ins.observed ? <Chip s={ins.observed} /> : 'full observation'}</dd><dt>observability</dt><dd>{ins.observability ?? 'full observation'}</dd>
            <dt>XenoBody</dt><dd>{ins.boundary.open.length ? `open: ${ins.boundary.open.join(', ')}` : 'closed'}; arena {ins.boundary.arenaRadius ?? 'whole grid'}</dd>
            <dt>Address Domain</dt><dd>A1 {ins.address.A1.mode ?? 'intact'} · A2 {ins.address.A2.mode ?? 'intact'}</dd><dt>SSS</dt><dd>{ins.sss.scale}/{ins.sss.size}/{ins.sss.speed} → {c.sssRegion}</dd>
            <dt>energy</dt><dd>A1 {ins.energy.a1.toFixed(2)} · power {ins.energy.power.toFixed(2)}</dd><dt>resource</dt><dd>total {ins.resource.total.toFixed(1)} · flow {ins.resource.flow.toFixed(3)}</dd>
            <dt>history</dt><dd>{ins.history.enabled ? 'on' : 'off'} · trace A1 {ins.history.trace.A1.toFixed(2)} A2 {ins.history.trace.A2.toFixed(2)}</dd><dt>paths</dt><dd>{Object.entries(ins.paths).map(([k, v]) => `${k} ${v}`).join(' · ')}</dd>
            <dt>M2</dt><dd>{ins.m2.sense === 'none' ? 'not connected' : `${ins.m2.sense}; A1 senses ${ins.m2.sensed?.toFixed(3)}`}</dd>
            {ins.route && <><dt>current MFS</dt><dd>{ins.route.currentMfs}</dd><dt>active route</dt><dd>{Object.entries(ins.route.paths).filter(([, v]) => v === 'active' || v === 'fallback').map(([k, v]) => `${k}${v === 'fallback' ? ' (fallback)' : ''}`).join(', ')}</dd><dt>alternative routes</dt><dd>{ins.route.alternative.map((m) => m.id).join(', ') || 'none'} ({ins.route.available.length} of {ins.route.available.length + ins.route.disabled.length} library MFS are open)</dd><dt>closed routes</dt><dd>{ins.route.disabled.filter((d) => ins.route!.named.includes(d.mfs.id)).map((d) => `${d.mfs.id} (needs ${d.because.join(', ')})`).join('; ') || 'none of the routes named above'}</dd>
              <dt>transition</dt><dd>{ins.route.lastTransition ? `t${ins.route.lastTransition.tick}: ${ins.route.lastTransition.from} → ${ins.route.lastTransition.to}; cost ${ins.route.lastTransition.cost}; trigger ${ins.route.lastTransition.trigger.join(', ')}` : 'none'}</dd></>}</dl> : <div className="eco-note">no record</div>}</div>
        <div className="vr"><h4>VISUAL REPRESENTATION · the pose</h4>
          <div className="eco-note">The bodies are drawn from the state on the left by fixed rules (bodyState.ts, mechanics.ts): lamps and probes follow the run; SSS scale preloads the observer's boom, size sets the probe ring's posture, speed sets the coupling's tension and the reservoir regulation; the SSS region leaves the archive latch ajar; the M2 tap is node B's probe B2. A pose is a presentation. It cannot show anything the left panel does not already say.</div></div>
      </div>

      <h3>Replay · markers and inspection</h3>
      <div className="eco-legend">{(Object.keys(MARKER_COLOR) as Array<keyof typeof MARKER_COLOR>).map((k) => <span key={k}><i style={{ background: MARKER_COLOR[k] }} />{MARKER_LABEL[k]}</span>)}</div>
      <ul className="eco-log" data-testid="eco-marker-list">{c.markers.map((m, i) => <li key={i}><button className={c.openMarker === m ? 'on' : ''} onClick={() => { c.setOpenMarker(m); c.setTick(m.tick); }}><i style={{ display: 'inline-block', width: 7, height: 7, background: MARKER_COLOR[m.kind], marginRight: 5 }} />t={m.tick} {m.label}</button></li>)}</ul>
      {c.openMarker && <div className="eco-note"><b>{MARKER_LABEL[c.openMarker.kind]}</b> at tick {c.openMarker.tick}: {c.openMarker.detail}{rec ? <> → {affected(rec.intervention_log.find((iv) => iv.tick === c.openMarker!.tick && c.openMarker!.label.startsWith(iv.op)) ?? { tick: c.openMarker.tick, op: c.openMarker.kind, event: 0 })}</> : null}</div>}

      <h3>Compare · baseline / intervention / recovered</h3>
      <div className="eco-row">{(['baseline', 'intervention', 'recovered'] as const).map((k) => <button key={k} className={snap === k ? 'on' : ''} disabled={!tk} onClick={() => jump(k)}>{k}{tk ? ` · tick ${tk[k]}` : ''}</button>)}
        <button disabled={!rec} className={c.compare ? 'on' : ''} onClick={() => { c.setCompare(!c.compare); if (!c.compare) c.setTab('technical'); }} title="three snapshots of this record on the technical sheet, with the changed components, paths, boundary, address and observability">compare on the sheet</button></div>
      {rec && tk && (() => {
        const mk = (t: number) => ({ label: String(t), tick: t, inspect: inspectAt(rec, c.out?.observed, t, c.out?.paths, c.markers), parts: {} as Record<string, never> });
        const d = deltaSnapshots(mk(tk.baseline), mk(tk.intervention));
        return <div className="eco-note">baseline → intervention: state {d.status[0]} → {d.status[1]}; paths changed {d.paths.map((p) => `${p.path} ${p.from}→${p.to}`).join(', ') || 'none'}; boundary {d.boundary.opened.map((x) => 'opened ' + x).join(', ') || 'unchanged'}; observability {d.observabilityChange}. The sheet adds the changed components.</div>;
      })()}

      <h3>Run log</h3>
      <div className="eco-row"><button disabled={disabled} onClick={() => void exportLog('json')}>export JSON</button><button disabled={disabled} onClick={() => void exportLog('csv')}>export CSV (per tick)</button></div>
      <div className="eco-note">The log carries the seed, configuration, initial condition, intervention schedule, observation / boundary / Address Domain / SSS / M2 configuration, the operational, observed and observability timelines, collapse and recovery ticks and the digests; replaying its schedule gives the same result digest.</div>
    </>
  );
}
