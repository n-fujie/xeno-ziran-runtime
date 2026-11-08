// Panels around the live body: create, run, intervene, switch operation lines, choose observation devices, inspect a part, watch the series.
import { useMemo, useState } from 'react';
import type { BodyInfo, Catalog, ObsConfig, ObsModel } from '../../api/xbtro';
import { LineChart, type Line } from './charts';
import { fmt, obsComSeries } from './logic';
import { frames, obsStore, useXb } from './store';

export function BodyCreator({ catalog }: { catalog: Catalog }) {
  const create = useXb((s) => s.createBody);
  const [preset, setPreset] = useState('human-like-planar');
  const [seeds, setSeeds] = useState(1);
  const [horizon, setHorizon] = useState(20);
  const [obs, setObs] = useState('motion+emg+contact');
  const [x14, setX14] = useState<string[]>([]);
  const maxSeeds = Number(catalog.limits.max_body_seeds ?? 1);
  const maxH = Number(catalog.limits.max_horizon_s ?? 30);
  return (
    <details className="xb-card" open>
      <summary>New body</summary>
      <div className="xb-form">
        <label>Body<select value={preset} onChange={(e) => setPreset(e.target.value)}>
          {catalog.presets.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.family}, dt {p.dt} s)</option>)}</select></label>
        <label>Observation<select value={obs} onChange={(e) => setObs(e.target.value)}>
          {Object.keys(catalog.observation.presets).map((k) => <option key={k} value={k}>{k}: {catalog.observation.presets[k].join(', ')}</option>)}</select></label>
        <label>Seeds (bodies run together)<input type="number" min={1} max={maxSeeds} value={seeds} onChange={(e) => setSeeds(Math.max(1, Math.min(maxSeeds, Number(e.target.value))))} /></label>
        <label>Horizon (s)<input type="number" min={2} max={maxH} value={horizon} onChange={(e) => setHorizon(Math.max(2, Math.min(maxH, Number(e.target.value))))} /></label>
      </div>
      <details className="xb-sub">
        <summary>Xeno-14 conditions ({x14.length} on)</summary>
        <div className="xb-checks">
          {catalog.xeno14.map((p) => (
            <label key={p.id} title={`${p.definition}\n\nIn this planar body: ${p.operationalization}\n\nFidelity: ${p.fidelity}. ${p.gap}`}>
              <input type="checkbox" checked={x14.includes(p.id)} onChange={(e) => setX14(e.target.checked ? [...x14, p.id] : x14.filter((i) => i !== p.id))} />
              {p.id}{p.fidelity === 'proxy-only' && <span className="warn-soft"> (proxy only)</span>}
            </label>
          ))}
        </div>
        <div className="small dim">Experimental conditions, never assumed to help. They are fixed when a body is created.</div>
      </details>
      <button onClick={() => void create({ preset, n_seeds: seeds, horizon_s: horizon, observation: { name: obs }, xeno14: x14 })}>Create body</button>
    </details>
  );
}

export function RunBar({ body }: { body: BodyInfo }) {
  const running = useXb((s) => s.running);
  const speed = useXb((s) => s.speed);
  const status = useXb((s) => s.status);
  const { run, pause, stepOnce, setSpeed, closeBody, saveBody } = useXb.getState();
  useXb((s) => s.tick);
  const t = status?.t ?? 0;
  const state = status?.diverged[0] ? { w: 'numerical divergence', c: 'warn' } : status?.fell[0] ? { w: 'fell (physical)', c: 'warn' } : status ? { w: 'standing', c: 'ok' } : { w: 'ready', c: 'dim' };
  return (
    <div className="xb-runbar">
      <button className={running ? 'on' : ''} onClick={() => (running ? pause() : run())}>{running ? 'Pause' : 'Run'}</button>
      <button onClick={() => void stepOnce(5)} disabled={running}>Step</button>
      <label className="small">speed<select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
        {[0.25, 0.5, 1, 2].map((s) => <option key={s} value={s}>{s}×</option>)}</select></label>
      <span className="mono">t = {fmt(t, 3)} s / {body.horizon_s} s</span>
      <span className={state.c}>{state.w}</span>
      <span className={body.numeric_stability.stable ? 'ok small' : 'warn small'} title={body.numeric_stability.scope}>
        {body.numeric_stability.integrator}: passive plant {body.numeric_stability.stable ? 'stable' : 'UNSTABLE'} (radius {fmt(body.numeric_stability.margin, 4)})</span>
      <span className="grow" />
      <button className="ghost" onClick={() => void saveBody()} title="Store this run in the history as a record">Save run</button>
      <button className="ghost" onClick={() => void closeBody()}>Close body</button>
    </div>
  );
}

export function LayerBar() {
  const layer = useXb((s) => s.layer);
  const overlay = useXb((s) => s.overlay);
  const { setLayer, setOverlay } = useXb.getState();
  const opts: { id: 'reference' | 'observation' | 'estimate'; label: string; hint: string; c: string }[] = [
    { id: 'reference', label: 'Reference', hint: 'the model\'s own state (simulator-internal)', c: '#d8d8dc' },
    { id: 'observation', label: 'Observation', hint: 'what the deployed devices delivered — delayed, noisy, with dropouts; unobserved segments are not drawn', c: '#5fd0e8' },
    { id: 'estimate', label: 'Estimate', hint: 'the controller\'s belief and the COM computed from observations only, against the reference', c: '#f0b45a' },
  ];
  return (
    <div className="xb-layers" role="radiogroup" aria-label="Which kind of value the body shows">
      {opts.map((o) => (
        <button key={o.id} role="radio" aria-checked={layer === o.id} className={layer === o.id ? 'on' : ''} title={o.hint} onClick={() => setLayer(o.id)}>
          <i style={{ background: o.c }} />{o.label}</button>
      ))}
      <label className="small"><input type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} /> show the reference as a wireframe</label>
    </div>
  );
}

export function Interventions({ catalog, body }: { catalog: Catalog; body: BodyInfo }) {
  const command = useXb((s) => s.command);
  const [vals, setVals] = useState<Record<string, number>>(() => Object.fromEntries(Object.entries(catalog.interventions).map(([k, v]) => [k, v.default])));
  const [done, setDone] = useState<string[]>([]);
  void body;
  return (
    <details className="xb-card" open>
      <summary>Interventions</summary>
      {Object.entries(catalog.interventions).map(([id, spec]) => (
        <div key={id} className="xb-row" title={spec.edits}>
          <span className="grow">{spec.label}<span className="dim small"> · {spec.unit}</span></span>
          <input type="range" min={spec.range[0]} max={Math.min(spec.range[1], id === 'perturbation' ? 200 : spec.range[1])} step={(spec.range[1] - spec.range[0]) / 200 || 0.01}
            value={vals[id]} onChange={(e) => setVals({ ...vals, [id]: Number(e.target.value) })} aria-label={`${spec.label} magnitude`} />
          <input type="number" value={Number(vals[id].toFixed(3))} onChange={(e) => setVals({ ...vals, [id]: Number(e.target.value) })} step="any" />
          <button onClick={async () => { if (await command({ type: 'intervention', id, magnitude: vals[id] })) setDone([...done, `${id} ${fmt(vals[id])}`]); }}>Apply</button>
        </div>
      ))}
      {done.length > 0 && <div className="small dim">applied so far: {done.join(' · ')}</div>}
      <div className="small dim">An intervention edits configuration values from now on; it never touches the random streams, so a re-run with and without it shares its noise.</div>
    </details>
  );
}

export function Lines({ body }: { body: BodyInfo }) {
  useXb((s) => s.tick);
  const command = useXb((s) => s.command);
  const f = frames.latest();
  const active = f?.reference.lines_active[0] ?? [];
  return (
    <details className="xb-card">
      <summary>Operation lines ({body.lines.length})</summary>
      <div className="xb-lines">
        {body.lines.map((ln, i) => (
          <div key={ln.id} className="xb-row" title={`${ln.label}\nignition: ${ln.ignition.signal}\ntime scale ${ln.timescale_s} s`}>
            <i className={`dot ${active[i] ? 'on' : ''} ${ln.enabled ? '' : 'off'}`} aria-label={active[i] ? 'active' : 'inactive'} />
            <span className="grow mono small">{ln.id}</span>
            <span className="dim small">{ln.kind}</span>
            <label className="small"><input type="checkbox" checked={ln.enabled} onChange={(e) => void command({ type: 'line', id: ln.id, enabled: e.target.checked })} /> on</label>
          </div>
        ))}
      </div>
      <div className="small dim">Lines fire, hold, lapse and re-fire on their own conditions and time scales; stopping one is a different thing from it having nothing to do.</div>
    </details>
  );
}

const SPATIAL_FIELD: Record<string, string> = { posture: 'joint / segment / pooled' };

export function Devices({ catalog, body }: { catalog: Catalog; body: BodyInfo }) {
  const command = useXb((s) => s.command);
  const [draft, setDraft] = useState<ObsConfig>(() => structuredClone(body.observation));
  const [seen, setSeen] = useState(body.observation);
  if (seen !== body.observation) { setSeen(body.observation); setDraft(structuredClone(body.observation)); }
  const has = (k: string) => draft.models.some((m) => m.kind === k);
  const toggle = (k: string, on: boolean) => {
    if (on && !has(k)) {
      const defs = catalog.observation.kinds[k].defaults;
      setDraft({ ...draft, models: [...draft.models, { id: k, kind: k, ...defs, blind_windows: [], blind_regions: [], effects_on: true } as unknown as ObsModel] });
    } else if (!on) setDraft({ ...draft, models: draft.models.filter((m) => m.kind !== k) });
  };
  const patch = (id: string, p: Partial<ObsModel>) => setDraft({ ...draft, models: draft.models.map((m) => (m.id === id ? { ...m, ...p } : m)) });
  const cov = body.coverage;
  return (
    <details className="xb-card" open>
      <summary>Observation devices</summary>
      {Object.entries(catalog.observation.kinds).map(([k, spec]) => {
        const m = draft.models.find((x) => x.kind === k);
        return (
          <div key={k} className="xb-device">
            <label title={spec.signals.join('; ')}><input type="checkbox" checked={!!m} onChange={(e) => toggle(k, e.target.checked)} /> <b>{k}</b> <span className="dim small">{spec.label}</span></label>
            {m && (
              <div className="xb-form compact">
                <label>rate Hz<input type="number" min={1} max={1000} value={m.sample_hz} onChange={(e) => patch(m.id, { sample_hz: Number(e.target.value) })} /></label>
                <label title={spec.noise_unit}>noise ×<input type="number" min={0} max={20} step={0.1} value={m.noise} onChange={(e) => patch(m.id, { noise: Number(e.target.value) })} /></label>
                <label>delay s<input type="number" min={0} max={2} step={0.01} value={m.delay_s} onChange={(e) => patch(m.id, { delay_s: Number(e.target.value) })} /></label>
                <label>dropout<input type="number" min={0} max={0.9} step={0.05} value={m.dropout} onChange={(e) => patch(m.id, { dropout: Number(e.target.value) })} /></label>
                {spec.spatial_choices.length > 1 && (
                  <label title={SPATIAL_FIELD[k] ?? ''}>scale<select value={m.spatial} onChange={(e) => patch(m.id, { spatial: e.target.value })}>{spec.spatial_choices.map((c) => <option key={c}>{c}</option>)}</select></label>
                )}
                <label title="blind window: the device delivers nothing between these times">blind from–to s
                  <input type="text" size={8} placeholder="e.g. 3-4" defaultValue={m.blind_windows.map((w) => w.join('-')).join(', ')}
                    onBlur={(e) => patch(m.id, { blind_windows: e.target.value.split(',').map((x) => x.trim().split('-').map(Number)).filter((w) => w.length === 2 && w.every(Number.isFinite)) as [number, number][] })} /></label>
              </div>
            )}
          </div>
        );
      })}
      <div className="xb-row"><button onClick={() => void command({ type: 'observation', observation: { config: draft } })}>Apply from now</button>
        <span className="small dim">A device added now starts blind until now; one removed is retired; one whose settings change is replaced. The past is not rewritten.</span></div>
      <div className="small">Outside every deployed device's boundary: {cov.unobserved_regions.length ? <b className="warn-soft">{cov.unobserved_regions.join(', ')}</b> : 'nothing'}. These regions are <b>unobserved</b>, not absent.</div>
    </details>
  );
}

export function PartInspector({ body }: { body: BodyInfo }) {
  const sel = useXb((s) => s.selected);
  const ins = useXb((s) => s.inspect);
  const select = useXb((s) => s.select);
  useXb((s) => s.tick);
  const parts = [...body.links.map((l) => `link:${l.id}`), ...body.joints.map((j) => `joint:${j.id}`), 'ground', 'neural', 'internal'];
  const lines: Line[][] = useMemo(() => {
    if (!ins) return [];
    return Object.entries(ins.series).map(([k, v]) => [{ label: `${k} (reference)`, t: ins.t, v, layer: 'reference' as const }]);
  }, [ins]);
  const jointId = sel?.startsWith('joint:') ? sel.slice(6) : sel?.startsWith('link:') ? body.joints[body.links.findIndex((l) => l.id === sel.slice(5))]?.id : undefined;
  const observed: Line[] = [];
  const t0 = (frames.latest()?.t ?? 0) - 5;
  if (jointId) for (const [id, m] of obsStore.models) m.channels.forEach((c, k) => { if (c.endsWith(`:${jointId}`)) { const s = obsStore.series(id, k, t0); observed.push({ label: `${id} ${c} (observation)`, t: s.t, v: s.v, layer: 'observation' }); } });
  return (
    <details className="xb-card" open>
      <summary>Part: {sel ?? 'none selected'}{ins && sel ? <span className="dim small"> · as of t = {fmt(ins.t[ins.t.length - 1], 4)} s</span> : null}</summary>
      <div className="xb-chips">{parts.map((p) => <button key={p} className={sel === p ? 'on' : ''} onClick={() => select(sel === p ? null : p)}>{p}</button>)}</div>
      <div className="small dim">Click a segment or joint in the 3D view, or pick a part here.</div>
      {ins && sel && (
        <>
          <table className="xb-kv"><tbody>{Object.entries(ins.now).map(([k, v]) => <tr key={k}><th>{k}</th><td className="mono">{fmt(v)}</td></tr>)}</tbody></table>
          <div className="small"><b>Observation here:</b> {ins.observation.unobserved ? <span className="warn-soft">no deployed device reaches {ins.region} — unobserved</span>
            : ins.observation.covered ? ins.observation.models.map((m) => `${m.id} (${m.sample_hz} Hz, noise ${m.noise}×, delay ${m.delay_s} s${m.dropout ? `, dropout ${m.dropout}` : ''}${m.blind_windows.length ? `, blind ${JSON.stringify(m.blind_windows)}` : ''})`).join('; ') : 'none'}</div>
          <div className="small"><b>Operation lines acting here:</b> {ins.lines.length ? ins.lines.map((l) => `${l.id}${l.enabled ? '' : ' (off)'} ${(l.active_fraction * 100).toFixed(0)}% active`).join('; ') : 'none in the last seconds'}</div>
          {lines.map((l) => <LineChart key={l[0].label} lines={l} height={92} title={l[0].label.replace(' (reference)', '')} />)}
          {observed.length > 0 && <LineChart lines={observed} height={110} title="what the devices delivered for this joint" />}
          <div className="small dim">{ins.note}</div>
        </>
      )}
    </details>
  );
}

export function LiveCharts({ body }: { body: BodyInfo }) {
  useXb((s) => s.tick);
  const f = frames.latest();
  const t1 = f?.t ?? 0;
  const t0 = t1 - 10;
  const ref = frames.series((fr) => fr.reference.com[0]);
  const est = frames.series((fr) => fr.estimates.controller.com[0]);
  const xref = frames.series((fr) => fr.reference.xref[0]);
  const oc = obsComSeries(body, obsStore, t0);
  const com: Line[] = [
    { label: 'COM — reference', t: ref.t, v: ref.v, layer: 'reference' },
    { label: 'target (reference)', t: xref.t, v: xref.v, layer: 'reference', dashed: true, color: '#78e696' },
    { label: 'COM — controller belief (estimate)', t: est.t, v: est.v, layer: 'estimate' },
    { label: 'COM — computed from observations only', t: oc.t, v: oc.v, layer: 'observation' },
  ];
  const cop = frames.series((fr) => fr.reference.cop[0]);
  const tau = body.joints.map((j, k) => ({ label: `${j.id} torque (reference)`, ...frames.series((fr) => fr.reference.tau[0]?.[k]) }));
  const en = frames.series((fr) => fr.reference.energy[0]);
  const fat = frames.series((fr) => fr.reference.fatigue[0]);
  return (
    <div className="xb-charts">
      <LineChart lines={com} title="Centre of mass" yLabel="m" />
      <LineChart lines={[{ label: 'centre of pressure (reference)', t: cop.t, v: cop.v, layer: 'reference' }]} title="Centre of pressure" yLabel="m" band={body.base_of_support_m} />
      <LineChart lines={tau.map((x) => ({ label: x.label, t: x.t, v: x.v }))} title="Joint torques (reference)" yLabel="N·m" />
      <LineChart lines={[{ label: 'energy', t: en.t, v: en.v, layer: 'reference' }, { label: 'fatigue', t: fat.t, v: fat.v, layer: 'estimate', color: '#e0c07f' }]} title="Internal resources (reference)" />
      <div className="small dim">Band in the second chart: the base of support. “Recovered / settled” means within ±{fmt(body.tolerance_band_m * 1000, 3)} mm of the target (a tolerance fixed in advance) and nearly still for 0.4 s.</div>
    </div>
  );
}
