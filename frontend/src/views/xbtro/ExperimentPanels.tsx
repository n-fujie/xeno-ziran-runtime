// Starting experiments (A–F as defined, and the added G, M, R, S, V) and following their jobs.
import { useState } from 'react';
import type { Catalog, Experiment } from '../../api/xbtro';
import { useXb } from './store';

const ORIGINAL = ['A', 'B', 'C', 'D', 'E', 'F'];

function Params({ exp, catalog, value, onChange }: { exp: Experiment; catalog: Catalog; value: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void }) {
  const maxSeeds = Number(catalog.limits.max_seeds ?? 32);
  const set = (k: string, v: unknown) => onChange({ ...value, [k]: v });
  const has = (k: string) => k in exp.params;
  return (
    <div className="xb-form">
      <label>Seeds (paired runs)<input type="number" min={4} max={maxSeeds} value={Number(value.n_seeds ?? exp.default_n_seeds)} onChange={(e) => set('n_seeds', Math.max(4, Math.min(maxSeeds, Number(e.target.value))))} /></label>
      {exp.id !== 'F' && exp.id !== 'V' && (
        <label>Body<select value={String(value.preset ?? 'human-like-planar')} onChange={(e) => set('preset', e.target.value)}>
          {catalog.presets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      )}
      {has('rounds') && <label>Observation rounds<input type="number" min={1} max={6} value={Number(value.rounds ?? 4)} onChange={(e) => set('rounds', Number(e.target.value))} /></label>}
      {has('alteration') && (
        <label>Hidden body change<select value={String(value.alteration ?? 'mixed')} onChange={(e) => set('alteration', e.target.value)}>
          {['mixed', 'delay-only', 'tone-only', 'fatigue-only'].map((a) => <option key={a}>{a}</option>)}</select></label>
      )}
      {exp.id === 'D' && <label>Adaptation trials<input type="number" min={3} max={Number(catalog.limits.max_trials ?? 8)} value={Number(value.trials ?? 5)} onChange={(e) => set('trials', Number(e.target.value))} /></label>}
      {has('push_force') && <label>Push (N)<input type="number" min={5} max={200} value={Number(value.push_force ?? 60)} onChange={(e) => set('push_force', Number(e.target.value))} /></label>}
      {has('ablate') && <label><input type="checkbox" checked={value.ablate !== false} onChange={(e) => set('ablate', e.target.checked)} /> ablation (rule line off) runs</label>}
      {(exp.id === 'C' || exp.id === 'G' || exp.id === 'R') && (
        <details className="xb-sub wide"><summary>Principles ({Array.isArray(value.principles) ? (value.principles as string[]).length : 14} of 14)</summary>
          <div className="xb-checks">{catalog.xeno14.map((p) => {
            const cur = (Array.isArray(value.principles) ? value.principles : catalog.xeno14.map((x) => x.id)) as string[];
            return <label key={p.id}><input type="checkbox" checked={cur.includes(p.id)} onChange={(e) => set('principles', e.target.checked ? [...cur, p.id] : cur.filter((i) => i !== p.id))} />{p.id}</label>;
          })}</div></details>
      )}
    </div>
  );
}

export function ExperimentsTab({ catalog }: { catalog: Catalog }) {
  const start = useXb((s) => s.startExperiment);
  const jobs = useXb((s) => s.jobs);
  const cancel = useXb((s) => s.cancelJob);
  const [params, setParams] = useState<Record<string, Record<string, unknown>>>({});
  const list = [...catalog.experiments].sort((a, b) => (ORIGINAL.includes(a.id) ? 0 : 1) - (ORIGINAL.includes(b.id) ? 0 : 1) || a.id.localeCompare(b.id));
  const running = Object.values(jobs).filter((j) => j.status === 'queued' || j.status === 'running');
  return (
    <div className="xb-grid">
      <section className="xb-col">
        <div className="small dim">Experiments A–F keep their defined purposes. G, M, R, S and V are additions designed independently of them. Final runs use seeds {String(catalog.seeds.final_base)}… (the tuning seeds {catalog.seeds.exploration.join('–')} are never used for results).</div>
        {list.map((e) => (
          <details key={e.id} className="xb-card" open={e.id === 'B'}>
            <summary><b>{e.id}</b> · {e.title}{!ORIGINAL.includes(e.id) && <span className="dim small"> (added)</span>}</summary>
            <p className="small">{e.question}</p>
            <Params exp={e} catalog={catalog} value={params[e.id] ?? {}} onChange={(v) => setParams({ ...params, [e.id]: v })} />
            <div className="xb-row"><button onClick={() => void start(e.id, params[e.id] ?? {})} disabled={running.length > 0}>Run {e.id}</button>
              <span className="small dim">{running.length > 0 ? 'wait for the running experiment' : 'runs as a job; the record is stored in the history'}</span></div>
          </details>
        ))}
      </section>
      <aside className="xb-col">
        <h4>Jobs</h4>
        {Object.values(jobs).length === 0 && <div className="small dim">No experiment has been started in this workspace yet.</div>}
        {Object.values(jobs).reverse().map((j) => (
          <div key={j.id} className="xb-job">
            <div className="xb-row"><b className="mono">{j.label}</b><span className={j.status === 'error' ? 'warn' : j.status === 'done' ? 'ok' : 'dim'}>{j.status}</span>
              {(j.status === 'running' || j.status === 'queued') && <button className="ghost" onClick={() => void cancel(j.id)}>cancel</button>}</div>
            <progress value={j.progress} max={1} aria-label={`${j.label} progress`} />
            <div className="small dim">{j.stage}{j.error && <span className="warn"> · {j.error}</span>}</div>
          </div>
        ))}
      </aside>
    </div>
  );
}
