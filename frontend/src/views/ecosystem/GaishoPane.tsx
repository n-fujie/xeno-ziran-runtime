import { useEffect, useMemo, useRef, useState } from 'react';
import { FIGURE_KIND_TEXT, LEVELS, OBS_PRESETS, cellTrace, claimGroups, UNOBSERVED_TEXT, constructionOf, domainStatusRows, exportRecord, figureTable, frameOf, levelRows, negativeCounts, num, observationDiff, operationPart, parseRecord, relationRows, relationSupport, snapshotsOf, type ComparatorsOut, type ConstructionOut, type GaishoObservation, type GaishoRecord, type GaishoSpecInfo, type GaishoUi, type ShapeReading } from './gaisho';
import { gaishoCompareObservations, gaishoComparators, gaishoCompareShapes, gaishoConstruction, gaishoFigure, gaishoRestore, gaishoRun, type GaishoObsComparison, type GaishoShapeComparison } from './gaishoApi';

// GAISHO - Operational Shape Laboratory: a research tab of the XENO ECOSYSTEM view. It runs SYNTHETIC computational experiments in the engine (backend/xzr/gaisho) and reads the record: nothing here simulates, scores or
// attributes. The operation, the operational shape, the conceptual operational shape, the Gaisho operational shape and the Gaisho attribution are five SEPARATE records; the attribution is never computed, and an operational
// difference is not evidence of it. A figure is shown with its kind; an experiment that was not executed is never shown as measured.

export interface GaishoCtx {
  info: GaishoSpecInfo | null; infoErr: string | null; ui: GaishoUi; setUi: (f: (u: GaishoUi) => GaishoUi) => void; busy: boolean; setBusy: (b: boolean) => void; err: string | null; setErr: (e: string | null) => void; focus3d: () => void;
}

const chip = (e: string) => <span className={`eco-chip gs-${e}`}>{e}</span>;
const Section = ({ title, children, testid }: { title: string; children: React.ReactNode; testid?: string }) => <><h3>{title}</h3><div className="gs-sec" data-testid={testid}>{children}</div></>;

export default function GaishoPane(c: GaishoCtx) {
  const { info, ui, setUi } = c;
  const rec = ui.rec;
  const [obsCmp, setObsCmp] = useState<GaishoObsComparison | null>(null), [shapeCmp, setShapeCmp] = useState<GaishoShapeComparison | null>(null);
  const [svg, setSvg] = useState<{ svg: string; kind: string; digest: string } | null>(null), [note, setNote] = useState<string | null>(null);
  const [showNeg, setShowNeg] = useState(false), [reading, setReading] = useState<ShapeReading | null>(null), [trace, setTrace] = useState<ConstructionOut | null>(null), [cmpOut, setCmpOut] = useState<ComparatorsOut | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const dom = info?.domains[ui.domain] ?? null;
  const executed = !!dom?.status.executed;
  const guard = async (fn: () => Promise<void>) => { c.setBusy(true); c.setErr(null); try { await fn(); } catch (e) { c.setErr(String(e)); } finally { c.setBusy(false); } };
  const spec = () => ({ domain: ui.domain, observation: ui.obs, seeds: Array.from({ length: Math.min(ui.seeds, dom?.max_seeds || 20) }, (_, i) => i + 1), conditions: ui.picked.length ? ui.picked : undefined });

  const load = (r: GaishoRecord, label: string) => setUi((u) => {
    const conds = r.result ? Object.keys(r.result.conditions) : [];
    const cond = conds.includes(u.cond) ? u.cond : conds[0] ?? '', snaps = snapshotsOf(r);
    return { ...u, domain: r.spec.domain, rec: r, recB: null, obsBName: null, cond, snap: snaps.includes(u.snap) ? u.snap : snaps[snaps.length - 1] ?? 'end', ghost: { kind: 'none', cond: '', snap: '' }, selected: null, relation: null,
      history: [...u.history, { id: u.history.length + 1, label, spec: r.spec, digest: r.digest, restored: null }].slice(-30) };
  });
  const run = () => guard(async () => { setObsCmp(null); setShapeCmp(null); setSvg(null); const r = await gaishoRun(spec()); load(r, `${ui.domain} ${observationDiff(ui.obs).join(' ') || 'full observation'} (${ui.seeds} seeds)`); });
  const seeOther = (name: string, patch: Partial<GaishoObservation>) => guard(async () => {
    if (!rec?.executed) return;
    const second = { ...rec.spec.observation, ...patch }, req = { domain: rec.spec.domain, seeds: rec.spec.seeds, conditions: [ui.cond] };
    const [b, cmp] = await Promise.all([gaishoRun({ ...req, observation: second }), gaishoCompareObservations({ ...req, condition: ui.cond, first: rec.spec.observation, second })]);
    setObsCmp(cmp); setUi((u) => ({ ...u, recB: b, obsBName: name, ghost: { kind: 'observation', cond: u.cond, snap: u.snap } }));
  });
  const setGhost = (kind: 'none' | 'moment' | 'condition' | 'observation', cond = ui.cond, snap = ui.snap) => {
    setUi((u) => ({ ...u, ghost: { kind, cond, snap } })); setShapeCmp(null); setReading(null);
  };
  // the engine's comparison of the two shapes in view (a moment or a condition of the same record)
  useEffect(() => {
    if (!rec?.executed || (ui.ghost.kind !== 'moment' && ui.ghost.kind !== 'condition')) return;
    let live = true;
    const first = { condition: ui.cond, snapshot: ui.snap }, second = { condition: ui.ghost.kind === 'condition' ? ui.ghost.cond : ui.cond, snapshot: ui.ghost.kind === 'moment' ? ui.ghost.snap : ui.snap };
    gaishoCompareShapes({ domain: rec.spec.domain, observation: rec.spec.observation, seeds: rec.spec.seeds, conditions: rec.spec.conditions ?? undefined, first, second }).then((r) => { if (live) setShapeCmp(r.comparison); setReading(r.reading); }).catch((e) => { if (live) c.setErr(String(e)); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec?.digest, ui.cond, ui.snap, ui.ghost.kind, ui.ghost.cond, ui.ghost.snap]);

  const restore = (id: number) => guard(async () => {
    const h = ui.history.find((x) => x.id === id);
    if (!h) return;
    const [chk, r] = await Promise.all([gaishoRestore({ spec: h.spec, digest: h.digest }), gaishoRun({ ...h.spec, conditions: h.spec.conditions ?? undefined })]);
    setUi((u) => ({ ...u, history: u.history.map((x) => (x.id === id ? { ...x, restored: chk.same_digest } : x)) }));
    setNote(chk.same_digest ? `restored by running the specification again: the digest ${h.digest.slice(0, 12)} is reproduced` : `the specification was run again and the digest differs (recorded ${chk.digest_recorded.slice(0, 12)}, rerun ${chk.digest_rerun.slice(0, 12)}): the record is NOT restored`);
    if (chk.same_digest) setUi((u) => { const conds = r.result ? Object.keys(r.result.conditions) : []; return { ...u, rec: r, recB: null, obsBName: null, domain: r.spec.domain, obs: r.spec.observation, cond: conds.includes(u.cond) ? u.cond : conds[0] ?? '', selected: null }; });
  });
  const importFile = (file: File) => guard(async () => {
    const t = parseRecord(await file.text()), chk = await gaishoRestore(t);
    if (!chk.same_digest) throw new Error(`the imported specification does not reproduce its digest (recorded ${chk.digest_recorded.slice(0, 12)}, rerun ${chk.digest_rerun.slice(0, 12)}): not loaded`);
    load(await gaishoRun({ ...t.spec, conditions: t.spec.conditions ?? undefined }), `imported ${t.spec.domain}`);
    setNote('imported: the specification was run again and its digest is reproduced');
  });
  const download = (name: string, text: string, type: string) => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };
  const traceShape = () => guard(async () => { if (!rec?.executed) return; setTrace(await gaishoConstruction({ domain: rec.spec.domain, observation: rec.spec.observation, seeds: rec.spec.seeds, conditions: rec.spec.conditions ?? undefined, condition: ui.cond, snapshot: ui.snap })); });
  const compare = () => guard(async () => { if (!rec?.executed) return; setCmpOut(await gaishoComparators({ domain: rec.spec.domain, observation: rec.spec.observation, seeds: rec.spec.seeds.slice(0, 10) })); });
  const figure = () => guard(async () => { if (!rec?.executed) return; const f = await gaishoFigure({ domain: rec.spec.domain, observation: rec.spec.observation, seeds: rec.spec.seeds, conditions: rec.spec.conditions ?? undefined, snapshot: ui.snap }); setSvg({ svg: f.svg, kind: f.figure_kind, digest: f.digest }); });

  useEffect(() => { setTrace(null); }, [rec?.digest, ui.cond, ui.snap]);
  const conds = rec?.result ? Object.keys(rec.result.conditions) : dom?.conditions ?? [];
  const shape = frameOf(ui).shape, snaps = rec ? snapshotsOf(rec) : [];
  const relRows = useMemo(() => (rec ? relationRows(rec, ui.cond) : []), [rec, ui.cond]);
  const lv = rec ? levelRows(rec, ui.cond) : [];
  const verdicts = rec?.models?.rows.find((r) => r.condition === ui.cond)?.verdicts ?? [];
  const test = rec?.attribution_tests?.find((t) => t.condition === ui.cond);
  const ro = rec?.research_objects?.[ui.cond];
  const cons = shape && ui.selected ? constructionOf(shape, ui.selected) : null;
  const obsSet = <K extends keyof GaishoObservation>(k: K, v: GaishoObservation[K]) => setUi((u) => ({ ...u, obs: { ...u.obs, [k]: v } }));
  const togg = (k: 'boundary' | 'sensor_channels', v: string) => setUi((u) => { const s = new Set(u.obs[k]); if (s.has(v)) s.delete(v); else s.add(v); return { ...u, obs: { ...u.obs, [k]: [...s] } }; });
  const opPart = rec?.executed ? operationPart(rec.spec.observation) : null;

  return (
    <>
      <h3>GAISHO - Operational Shape Laboratory (synthetic)</h3>
      <div className="eco-note" data-testid="gs-scope">{info?.scope ?? 'SYNTHETIC computational experiments only.'} {info?.source_status}</div>
      {c.infoErr && <div className="eco-err">{c.infoErr}</div>}
      {c.err && <div className="eco-err" data-testid="gs-err">{c.err}</div>}
      {note && <div className="eco-note" data-testid="gs-note">{note}</div>}

      <Section title="Research domains (each judged on its own)" testid="gs-domains">
        <table className="eco-table"><tbody>
          {(info ? domainStatusRows(info) : []).map((d) => <tr key={d.id}><td><button className={ui.domain === d.id ? 'on' : ''} onClick={() => setUi((u) => ({ ...u, domain: d.id, picked: [] }))}>{d.id}</button></td><td>{d.title}</td><td>{chip(d.completion)}</td></tr>)}
        </tbody></table>
        {dom && <div className="eco-note">{dom.status.criteria}</div>}
      </Section>

      <Section title="Experiment: conditions, interventions, observation" testid="gs-setup">
        {!executed && <div className="eco-note" data-testid="gs-not-executed">This domain is specified and NOT executed: no substitute computation is made, and no figure of an experiment is drawn for it.</div>}
        <div className="eco-note">Candidate operations (all are run unless some are ticked):</div>
        <div className="eco-col" data-testid="gs-conditions">{(dom?.conditions ?? []).map((cn) => <label key={cn}><input type="checkbox" checked={ui.picked.includes(cn)} onChange={() => setUi((u) => ({ ...u, picked: u.picked.includes(cn) ? u.picked.filter((x) => x !== cn) : [...u.picked, cn] }))} /> {cn}</label>)}</div>
        <div className="eco-note">Observation conditions (the ten axes; the change of the operation itself is only through the temporal window, the environment and the probe):</div>
        <div className="eco-row" data-testid="gs-observation" role="group" aria-label="observation conditions">
          <label>sensor noise <select value={ui.obs.sensor_noise} onChange={(e) => obsSet('sensor_noise', Number(e.target.value))}>{[0, 0.1, 0.3].map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>scale <select value={ui.obs.scale} onChange={(e) => obsSet('scale', Number(e.target.value))}>{[1, 2, 4].map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>temporal window <select value={ui.obs.temporal_window} onChange={(e) => obsSet('temporal_window', Number(e.target.value))}>{[10, 20, 40, 100].map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>speed <select value={ui.obs.speed} onChange={(e) => obsSet('speed', Number(e.target.value))}>{[1, 2, 3].map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>coupling <select value={ui.obs.coupling} onChange={(e) => obsSet('coupling', e.target.value as GaishoObservation['coupling'])}><option>intervened</option><option>passive</option></select></label>
          <label>resources (cells) <select value={ui.obs.resources} onChange={(e) => obsSet('resources', Number(e.target.value))}>{[30, 60, 10000].map((x) => <option key={x}>{x}</option>)}</select></label>
          <label><input type="checkbox" checked={ui.obs.memory} onChange={(e) => obsSet('memory', e.target.checked)} /> memory record</label>
          <label>environment <select value={ui.obs.environment} onChange={(e) => obsSet('environment', e.target.value)}>{(info?.environments ?? ['default']).map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>probe <select value={ui.obs.probe} onChange={(e) => obsSet('probe', Number(e.target.value))}>{[0, 0.5, 1].map((x) => <option key={x}>{x}</option>)}</select></label>
          <span>outside the boundary: {['x', 'y'].map((a) => <label key={a}><input type="checkbox" checked={ui.obs.boundary.includes(a)} onChange={() => togg('boundary', a)} /> {a}</label>)}</span>
          <span>sensor channels: {['x', 'y', 'memory'].map((a) => <label key={a}><input type="checkbox" checked={ui.obs.sensor_channels.includes(a)} onChange={() => togg('sensor_channels', a)} /> {a}</label>)}</span>
          <label>seeds <select value={Math.min(ui.seeds, dom?.max_seeds || 20)} onChange={(e) => setUi((u) => ({ ...u, seeds: Number(e.target.value) }))}>{[5, 10, 20].filter((x) => x <= (dom?.max_seeds || 20)).map((x) => <option key={x}>{x}</option>)}</select></label>
        </div>
        <div className="eco-row"><button onClick={run} disabled={c.busy || !info} data-testid="gs-run">{c.busy ? 'running...' : executed ? 'Run the experiment' : 'Show the specification'}</button>
          <button onClick={() => setUi((u) => ({ ...u, obs: { ...u.obs, ...info?.observation_defaults } }))} disabled={c.busy}>fullest observation</button></div>
      </Section>

      {rec && !rec.executed && <Section title="Not executed" testid="gs-spec-only"><div className="eco-note">{rec.note}</div><div className="eco-note">{chip(rec.figure_kind)} {FIGURE_KIND_TEXT[rec.figure_kind] ?? rec.figure_kind}</div></Section>}

      {rec?.executed && rec.result && <>
        <Section title="Result: the candidates, one record each" testid="gs-result">
          <div className="eco-note">{chip(rec.figure_kind)} {FIGURE_KIND_TEXT[rec.figure_kind]} - model {rec.model_version} - {rec.result.seeds.length} seeds (one run per seed is the replication unit; intervals are t-based 95 %) - record digest {rec.digest.slice(0, 16)}</div>
          <table className="eco-table"><thead><tr><th>condition</th><th>accuracy before shift</th><th>operation</th></tr></thead><tbody>
            {conds.map((cn) => <tr key={cn} className={cn === ui.cond ? 'gs-sel' : ''}><td><button className={cn === ui.cond ? 'on' : ''} onClick={() => setUi((u) => ({ ...u, cond: cn, selected: null, ghost: u.ghost.kind === 'observation' ? { kind: 'none', cond: '', snap: '' } : u.ghost, recB: u.ghost.kind === 'observation' ? null : u.recB }))}>{cn}</button></td><td>{num(rec.result!.conditions[cn].accuracy_pre_shift.mean)}</td><td>{rec.result!.conditions[cn].operation_digest.slice(0, 8)}</td></tr>)}
          </tbody></table>
          <div className="eco-note">Accuracy is shown only because candidates that look alike in it are told apart by the interventions below; an improved accuracy does not establish knowledge.</div>
        </Section>

        <Section title="Relations under interventions (this condition)" testid="gs-relations">
          <table className="eco-table"><tbody>
            {relRows.map((r) => <tr key={r.name} className={r.name === ui.relation ? 'gs-sel' : ''}><td><button className={r.name === ui.relation ? 'on' : ''} onClick={() => setUi((u) => ({ ...u, relation: u.relation === r.name ? null : r.name }))}>{r.name}</button></td><td>{r.status === 'IDENTIFIED' ? r.text : <span data-testid={`gs-unobs-${r.name}`}>{chip(r.status)} {r.text}</span>}</td></tr>)}
          </tbody></table>
          {ui.relation && shape && <div className="eco-note" data-testid="gs-support">{relationSupport(ui.relation, shape).note}{relationSupport(ui.relation, shape).cells ? ` (${relationSupport(ui.relation, shape).cells!.length} cells marked blue in the scene)` : ''}</div>}
        </Section>

        <Section title="Operational shape in the 3D scene" testid="gs-shape">
          <div className="eco-row">
            <label>moment <select value={ui.snap} onChange={(e) => setUi((u) => ({ ...u, snap: e.target.value, selected: null }))} data-testid="gs-snap">{snaps.map((s) => <option key={s}>{s}</option>)}</select></label>
            <label>compare with <select value={ui.ghost.kind} onChange={(e) => { const k = e.target.value as 'none' | 'moment' | 'condition' | 'observation'; if (k === 'observation') { if (!ui.recB) setNote('choose an observation condition below'); return; } setGhost(k, k === 'condition' ? conds.find((x) => x !== ui.cond) ?? ui.cond : ui.cond, k === 'moment' ? snaps.find((s) => s !== ui.snap) ?? ui.snap : ui.snap); }} data-testid="gs-ghost">
              <option value="none">nothing</option><option value="moment">another moment (before / after)</option><option value="condition">another condition</option>{ui.recB && <option value="observation">the same operation, another observation</option>}</select></label>
            {ui.ghost.kind === 'moment' && <label>other moment <select value={ui.ghost.snap} onChange={(e) => setGhost('moment', ui.cond, e.target.value)}>{snaps.map((s) => <option key={s}>{s}</option>)}</select></label>}
            {ui.ghost.kind === 'condition' && <label>other condition <select value={ui.ghost.cond} onChange={(e) => setGhost('condition', e.target.value, ui.snap)}>{conds.map((s) => <option key={s}>{s}</option>)}</select></label>}
            <button onClick={c.focus3d} data-testid="gs-focus">show in the 3D scene</button>
          </div>
          <div className="eco-row">{(['surface', 'cuts', 'branch', 'unresolved'] as const).map((k) => <label key={k}><input type="checkbox" checked={ui.show[k]} onChange={(e) => setUi((u) => ({ ...u, show: { ...u.show, [k]: e.target.checked } }))} /> {k}</label>)}</div>
          {shape && <div className="eco-note" data-testid="gs-shape-counts">{shape.recorded ? `${shape.vertices.length} recorded cells - ${shape.edges.length + shape.cuts.length} edges (${shape.cuts.length} cut) - ${shape.branch.length} branch points - ${shape.unresolved.length} unresolved regions` : `not recorded (${shape.reason})`} - projection: {shape.projection.kind} ({shape.projection.name}); x = {shape.projection.axes.x}, y = {shape.projection.axes.y}, height = {shape.projection.axes.z}</div>}
          {shape && shape.unresolved.length > 0 && <div className="eco-note" data-testid="gs-unresolved">Unresolved regions kept: {Object.entries(shape.unresolved.reduce<Record<string, number>>((m, u) => ({ ...m, [u.reason]: (m[u.reason] ?? 0) + 1 }), {})).map(([k, n]) => `${n} ${k}`).join(', ')}</div>}
          {shapeCmp && <div className="eco-note" data-testid="gs-shape-cmp">{shapeCmp.comparable ? `difference of the two shapes (from the engine): mean |d| ${num(shapeCmp.mean_abs_difference)}, max |d| ${num(shapeCmp.max_abs_difference)}, mean signed ${num(shapeCmp.mean_signed_difference)}; cuts only in the first ${shapeCmp.cuts_only_in_first?.length ?? 0}, only in the second ${shapeCmp.cuts_only_in_second?.length ?? 0}; branch points ${shapeCmp.branch_points?.join(' / ')}` : shapeCmp.reason}</div>}
          {reading && <div data-testid="gs-reading"><div className="eco-note">What this difference is a difference of: the realized operation {chip(reading.real_operation.split(' ')[0])} - the recorded observation {chip(reading.recorded_observation.reading ?? 'NOT_READ')} (mean |d| {num(reading.recorded_observation.mean_abs_difference)} against an expected sampling noise of {num(reading.recorded_observation.expected_sampling_noise)}) - the reconstructed relation (cuts and branch points {reading.reconstructed_relation.branch_points?.join(' / ') ?? '-'}) follows the record - display: no record changes.</div><div className="eco-note">{reading.summary}.{reading.weight_change ? ` Change of the weights of the operation: ${Object.entries(reading.weight_change).map(([k, v]) => `${k} ${v >= 0 ? '+' : ''}${num(v, 2)}`).join(', ')}.` : ''}</div></div>}
          {cons ? <table className="eco-table" data-testid="gs-construction"><tbody>{cons.rows.map(([a, b]) => <tr key={a}><td>{a}</td><td>{b}</td></tr>)}</tbody></table> : <div className="eco-note">Click a point or a hollow marker in the scene to read its construction data.</div>}
        </Section>

        <Section title="Where the cells and edges come from" testid="gs-trace">
          <div className="eco-row"><button onClick={traceShape} disabled={c.busy} data-testid="gs-trace-run">trace the construction of this shape</button></div>
          {trace?.recorded && trace.counts && <div data-testid="gs-trace-out">
            <div className="eco-note" data-testid="gs-trace-counts">{trace.counts.cells_total} cells = the {trace.counts.grid[0]} x {trace.counts.grid[1]} grid of the two interventions ({trace.counts.cells_recorded} recorded, {trace.counts.cells_unresolved} unresolved); {trace.counts.edges_drawn} edges drawn of {trace.counts.edges_expected_if_all_recorded} possible ({trace.counts.grid[0] - 1} x {trace.counts.grid[1]} along the first axis + {trace.counts.grid[0]} x {trace.counts.grid[1] - 1} along the second), {trace.counts.cuts} cut, {trace.counts.branch_points} branch points. Counts consistent: {String(trace.counts_consistent)}.</div>
            <div className="eco-note">A cell is {trace.what_a_cell_is}. {trace.outcome_of_the_domain}</div>
            <table className="eco-table"><tbody>{Object.entries(trace.rules).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}</tbody></table>
            <div className="eco-note"><b>Which layer each element is</b> (real operation / recorded observation / reconstructed relation / display):</div>
            <table className="eco-table" data-testid="gs-trace-layers"><thead><tr><th>element</th><th>real operation</th><th>recorded observation</th><th>reconstructed relation</th><th>display</th></tr></thead><tbody>{Object.entries(trace.layers).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.real_operation}</td><td>{v.recorded_observation}</td><td>{v.reconstructed_relation}</td><td>{v.display}</td></tr>)}</tbody></table>
            {trace.what_the_surface_carries && <div className="eco-note" data-testid="gs-trace-carries">Refitting the cells: weights {Object.entries(trace.what_the_surface_carries.fitted_weights).map(([k, v]) => `${k}=${num(v, 2)}`).join(', ')} against the operation's {Object.entries(trace.what_the_surface_carries.weights_of_the_operation).map(([k, v]) => `${k}=${num(v, 2)}`).join(', ')}; residual {num(trace.what_the_surface_carries.rms_residual_of_the_fit, 4)} against an expected sampling noise of {num(trace.what_the_surface_carries.expected_sampling_rms, 4)}. {trace.what_the_surface_carries.reading}</div>}
            {ui.selected && (() => { const t = cellTrace(trace, ui.selected); return t.cell ? <table className="eco-table" data-testid="gs-trace-cell"><tbody>
              <tr><td>cell</td><td>{t.cell.id} (i={t.cell.cell[0]}, j={t.cell.cell[1]})</td></tr><tr><td>intervention</td><td>{Object.entries(t.cell.intervention).map(([k, v]) => `${k} = ${num(v, 2)}`).join('; ')}</td></tr>
              <tr><td>value</td><td>{num(t.cell.value)} (se {num(t.cell.se_of_mean)}; {t.cell.trials_per_cell_and_seed} trials x {t.cell.seeds} seeds)</td></tr><tr><td>the weights of the operation predict</td><td>{num(t.cell.expected_from_the_agents_weights)}{t.cell.value_minus_expected === null ? '' : ` (value - prediction ${num(t.cell.value_minus_expected)})`}</td></tr>
              <tr><td>edges</td><td>{t.edges.map((e) => `${e.a}-${e.b} along ${e.along}: d=${num(e.difference)}${e.kind === 'cut' ? ' CUT' : ''}`).join('; ')}</td></tr></tbody></table> : t.unresolved ? <div className="eco-note" data-testid="gs-trace-cell">unresolved region ({t.unresolved}): not recorded, no value</div> : null; })()}
          </div>}
        </Section>

        <Section title="The same operation under another observation" testid="gs-observe">
          <div className="eco-note">The current record is laid against the same operation seen through one other observation. The engine says whether the realized operation is the same (the record differs) or not (the observation changed the operation).</div>
          <div className="eco-row" role="group" aria-label="other observation conditions">{OBS_PRESETS.map((p) => <button key={p.name} disabled={c.busy} className={ui.obsBName === p.name ? 'on' : ''} onClick={() => seeOther(p.name, p.patch)}>{p.name}</button>)}</div>
          {obsCmp && <div data-testid="gs-obs-cmp">
            <div className="eco-note">{ui.obsBName}: {obsCmp.same_realized_operation ? 'the realized operation is IDENTICAL; what differs is the record' : 'the realized operation DIFFERS'}{obsCmp.observation_changed_the_operation ? ' - the observation changed the operation it records (probe, environment or window)' : ''}</div>
            <div className="eco-note" data-testid="gs-kinds">Real operation: {obsCmp.change_kinds.real_operation}. Recorded observation: {obsCmp.change_kinds.recorded_observation}. Reconstructed relation: {obsCmp.change_kinds.reconstructed_relation.unobserved_in_one.length ? `unobserved in one of the two: ${obsCmp.change_kinds.reconstructed_relation.unobserved_in_one.join(', ')}` : 'identified in both'}. Display: {obsCmp.change_kinds.display}.</div>
            <table className="eco-table"><tbody>{obsCmp.relations.map((r) => <tr key={r.relation}><td>{r.relation}</td><td>{typeof r.first === 'number' ? num(r.first) : r.first}</td><td>{typeof r.second === 'number' ? num(r.second) : r.second}</td><td>{chip(r.kind)}</td></tr>)}</tbody></table>
          </div>}
          {opPart && <div className="eco-note">Part of the observation that is part of the run: {Object.entries(opPart).map(([k, v]) => `${k}=${v}`).join(', ')}</div>}
        </Section>

        <Section title="Five levels (separate records)" testid="gs-levels">
          <table className="eco-table"><tbody>
            {lv.map((l) => <tr key={l.level}><td>{info?.levels[l.level] ?? l.level}</td><td>{chip(l.state)}</td><td>{l.note}</td></tr>)}
          </tbody></table>
          <div className="eco-note" data-testid="gs-attribution">Gaisho attribution (independent evidence): {chip(lv.find((l) => l.level === 'gaisho_attribution')?.state ?? 'UNRESOLVED')} - the laboratory never computes it. {test && <>Operational test on this condition: {chip(test.operational_test)} - {test.why}</>}</div>
          {LEVELS.length === 5 && ro && <details><summary>The twelve questions of this candidate</summary><table className="eco-table"><tbody>{Object.entries(ro).filter(([k]) => k !== 'id').map(([k, v]) => <tr key={k}><td>{k}</td><td>{typeof v === 'string' ? v : JSON.stringify(v).slice(0, 360)}</td></tr>)}</tbody></table></details>}
        </Section>

        {!rec.models && <Section title="Competing explanations" testid="gs-models-absent"><div className="eco-note">The comparison with competing explanations is made only when every candidate condition of the domain is run (and only for the knowledge domain so far): run all conditions to see the verdicts. The other explanations of the brief (attention, memory, predictive processing, sensorimotor, cognitive appraisal, concept learning, SNN, dynamical systems, operational-shape analysis) have not been run.</div></Section>}
        {rec.models && <Section title="Competing explanations (same information, same held-out interventions)" testid="gs-models">
          <table className="eco-table"><tbody>{verdicts.map((v) => <tr key={v.competitor}><td>{v.competitor}</td><td>{chip(v.verdict)}</td></tr>)}</tbody></table>
          <div className="eco-note">{rec.models.rule} The verdicts are kept apart; they are not added into a score.</div>
          <div className="eco-row"><button onClick={compare} disabled={c.busy} data-testid="gs-comparators-run">show what each model is given, and add the equal-parameter cue account</button></div>
          {cmpOut && <div data-testid="gs-comparators">
            <table className="eco-table"><thead><tr><th>model</th><th>fits</th><th>parameters</th><th>information</th><th>history</th><th>nested in</th></tr></thead><tbody>{Object.entries(cmpOut.comparators).map(([k, m]) => <tr key={k}><td>{k}: {m.label}</td><td>{m.fits}</td><td>{m.parameters}</td><td>{m.information}</td><td>{m.history ? 'yes' : 'none'}</td><td>{m.nested_in ?? '-'}</td></tr>)}</tbody></table>
            <table className="eco-table"><tbody>{cmpOut.rows.map((r) => <tr key={r.condition}><td>{r.condition}</td><td>{r.verdicts.map((v) => `${v.competitor.split(' ')[0]} ${v.verdict}`).join(' - ')}</td></tr>)}</tbody></table>
            <div className="eco-note">Held out: {cmpOut.held_out}. {cmpOut.reading}</div>
            <div className="eco-note">Not run: {cmpOut.not_run.join(', ')}.</div>
          </div>}
        </Section>}

        <Section title={`Negative results kept (${rec.negative_results?.length ?? 0})`} testid="gs-negative">
          <div className="eco-row">{negativeCounts(rec).map(([k, n]) => <span key={k}>{chip(k)} {n}</span>)}</div>
          <button onClick={() => setShowNeg((s) => !s)}>{showNeg ? 'hide' : 'list'}</button>
          {showNeg && <table className="eco-table"><tbody>{(rec.negative_results ?? []).map((n, i) => <tr key={i}><td>{n.kind}</td><td>{n.condition ?? ''}</td><td>{n.relation ?? n.competitor ?? ''} {n.class ? UNOBSERVED_TEXT[n.class as keyof typeof UNOBSERVED_TEXT] ?? n.class : n.why ?? n.what ?? n.note ?? ''}</td></tr>)}</tbody></table>}
        </Section>

        <Section title="Figure and its experiment conditions" testid="gs-figure">
          <div className="eco-row"><button onClick={figure} disabled={c.busy}>regenerate the figure from the record</button>
            {svg && <button onClick={() => download(`gaisho-${rec.spec.domain}-${rec.digest.slice(0, 8)}.svg`, svg.svg, 'image/svg+xml')}>download the SVG</button>}</div>
          {svg && <><div className="eco-note" data-testid="gs-figure-kind">{chip(svg.kind)} regenerated from record {svg.digest.slice(0, 12)}</div><div className="gs-figure" dangerouslySetInnerHTML={{ __html: svg.svg }} /></>}
          <table className="eco-table" data-testid="gs-figure-table"><thead><tr><th>drawn condition</th><th>operation</th><th>seeds</th><th>shapes (moment: cells / cuts / branch / unresolved)</th></tr></thead><tbody>
            {figureTable(rec).map((f) => <tr key={f.condition}><td>{f.condition}</td><td>{f.operation_digest.slice(0, 8)}</td><td>{f.seeds}</td><td>{f.shapes.map((s) => `${s.snapshot}: ${s.recorded ? `${s.vertices}/${s.cuts}/${s.branch}/${s.unresolved}` : 'not recorded'}`).join('; ')}</td></tr>)}
          </tbody></table>
        </Section>
      </>}

      <Section title="Experiment history (restored by running the specification again)" testid="gs-history">
        {ui.history.length === 0 && <div className="eco-note">No experiment yet.</div>}
        <table className="eco-table"><tbody>{ui.history.map((h) => <tr key={h.id}><td>{h.id}</td><td>{h.label}</td><td>{h.digest.slice(0, 10)}</td><td><button onClick={() => restore(h.id)} disabled={c.busy}>restore</button></td><td>{h.restored === null ? '' : h.restored ? 'digest reproduced' : 'DIGEST DIFFERS'}</td></tr>)}</tbody></table>
        <div className="eco-row">
          <button disabled={!rec?.executed} onClick={() => rec && download(`gaisho-record-${rec.digest.slice(0, 8)}.json`, exportRecord(rec), 'application/json')} data-testid="gs-export">export the record (JSON)</button>
          <button onClick={() => fileRef.current?.click()} disabled={c.busy}>import a record</button>
          <input ref={fileRef} type="file" accept="application/json,.json" style={{ display: 'none' }} data-testid="gs-import" onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = ''; }} />
        </div>
        <div className="eco-note">The record holds the specification, the seeds, the model version, the digests and the negative results; importing it runs the specification again and loads it only if its digest is reproduced.</div>
      </Section>

      <Section title="Claims: supported, limited, and hypotheses not tested" testid="gs-claims">
        {claimGroups(info?.claims ?? []).map((g) => <div key={g.status}><div className="eco-note"><b>{g.title}</b></div><ul className="gs-list">{g.items.map((c) => <li key={c.id}>{c.id}: {c.claim} <i>(rests on: {c.rests_on})</i></li>)}</ul></div>)}
      </Section>

      <Section title="Not to be inferred" testid="gs-prohibited">
        <ul className="gs-list">{(info?.prohibited_inferences ?? []).map((p) => <li key={p.premise}>{p.premise} {'→'} {p.conclusion}: {p.reason}</li>)}</ul>
        <div className="eco-note">{info?.limits}</div>
      </Section>
    </>
  );
}
