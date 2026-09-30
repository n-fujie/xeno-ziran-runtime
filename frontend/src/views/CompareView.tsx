import { useState } from 'react';
import type { CompareResult, MetricRow } from '../api/client';
import Chart from '../components/Chart';
import { useSim } from '../store/sim';
import GraphView from './GraphView';
import { EDGE_CLASS_COLOR, NODE_CLASS_COLOR } from './palette';

const rgb = (c: number[]) => `rgb(${c[0]},${c[1]},${c[2]})`;

export default function CompareView() {
  const cmp = useSim((s) => s.compare);
  const jobs = useSim((s) => s.jobs);
  const start = useSim((s) => s.startCompare);
  const loadCompare = useSim((s) => s.loadCompare);
  const [horizon, setHorizon] = useState(150);
  const running = Object.values(jobs).some((j) => j.status === 'running');
  const done = Object.values(jobs).filter((j) => j.status === 'done');

  return (
    <div className="compare">
      <div className="compare-graph">
        <GraphView projection="network" compare={cmp} />
      </div>
      <div className="compare-side">
        <div className="row">
          <label className="dim">horizon</label>
          <input type="number" min={10} max={5000} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
          <button onClick={() => void start(horizon)} disabled={running}>{running ? 'running…' : 'Compare baseline vs intervention'}</button>
          {done.length > 1 && (
            <select value={cmp?.id ?? ''} onChange={(e) => void loadCompare(e.target.value)}>
              {done.map((j) => <option key={j.id} value={j.id}>{j.id}</option>)}
            </select>
          )}
        </div>
        {!cmp ? (
          <p className="dim">No comparison yet. Enter an intervention in the Philosophical Practice console (it runs a comparison
            automatically), or press Compare to contrast the applied configuration with the current draft.</p>
        ) : <CompareReport r={cmp} />}
      </div>
    </div>
  );
}

function CompareReport({ r }: { r: CompareResult }) {
  const s = r.summary;
  const reachNoise = s.reachable.exceeds_noise;
  return (
    <div className="report">
      <p className="dim small">Steps {r.start_t}–{r.start_t + r.horizon}. Both branches start from the same state and random stream;
        the noise floor is a third run of the baseline under a different random stream. Differences below it are not
        distinguishable from stochastic variation here. {r.elapsed_s}s.</p>
      {r.intervention_log.length > 0 && <p className="mono small">intervention: {r.intervention_log.join(' · ')}</p>}
      <div className="cards">
        <Card title="reachable (ignited ≥1×)" a={s.reachable.baseline} b={s.reachable.intervention}
          note={<>+{s.reachable.newly_reached} / −{s.reachable.no_longer_reached} configurations ·
            noise-floor flips {s.reachable.noise_floor_flips ?? '—'}
            {reachNoise === false && <span className="warn"> · within noise</span>}</>} />
        <Card title="ignitions (total)" a={s.ignition_pattern.total_baseline} b={s.ignition_pattern.total_intervention}
          note={<>{s.ignition_pattern.ignites_more} ignite ≥2× more · {s.ignition_pattern.ignites_less} ≥2× less</>} />
        <Card title="loop fraction" a={s.loops.baseline_fraction} b={s.loops.intervention_fraction}
          note={<>+{s.loops.gained} / −{s.loops.lost} configurations in loops</>} />
        <Card title="cuts" a={s.cuts.only_baseline + s.cuts.shared} b={s.cuts.only_intervention + s.cuts.shared}
          note={<>{s.cuts.only_baseline} only baseline · {s.cuts.only_intervention} only intervention</>} />
        <Card title="reconfigurations" a={s.reconfiguration.baseline} b={s.reconfiguration.intervention}
          note={<>{s.reconfiguration.only_intervention} only in intervention</>} />
        <Card title="new connections" a={s.new_connections.baseline} b={s.new_connections.intervention}
          note={<>gates changed: {s.gates_changed} · first divergence t{s.first_divergence_step ?? '—'}</>} />
      </div>
      <Chart title="ignitions per step" height={110} series={[
        { label: 'baseline', t: r.series.t, v: r.series.baseline, color: '#8f8f96' },
        { label: 'intervention', t: r.series.t, v: r.series.intervention, color: '#e6e6ea' },
      ]} />
      <h4>Graph legend</h4>
      <ul className="legend-inline small">
        {Object.entries(r.node_class_names).filter(([k]) => k !== '0').map(([k, v]) => (
          <li key={k}><i className="ring" style={{ borderColor: rgb(NODE_CLASS_COLOR[Number(k)]) }} />{v}</li>))}
        {Object.entries(r.edge_class_names).map(([k, v]) => (
          <li key={k}><i className="line" style={{ background: rgb(EDGE_CLASS_COLOR[Number(k)]) }} />{v}</li>))}
      </ul>
      {r.commitment_changes.length > 0 && (<>
        <h4>Changed commitment dependencies</h4>
        <table className="list small">
          <thead><tr><td>claim</td><td>before</td><td>after</td></tr></thead>
          <tbody>{r.commitment_changes.map((c) => (
            <tr key={c.claim}><td className="mono">{c.claim}<div className="dim">{c.text}</div></td>
              <td className="small">{c.before.status}</td><td className="small">{c.after.status}</td></tr>))}
          </tbody>
        </table>
      </>)}
      <h4>Operational effects (compiled)</h4>
      <div className="grid2 small">
        <div><div className="dim">baseline</div>{r.operational_changes.baseline.map((p, i) => <div key={i} className="mono">{p.source}: {p.effect}</div>)}</div>
        <div><div className="dim">intervention</div>{r.operational_changes.intervention.map((p, i) => <div key={i} className="mono">{p.source}: {p.effect}</div>)}</div>
      </div>
      <h4>Shape descriptors (means over the horizon)</h4>
      <table className="list mono small">
        <thead><tr><td>descriptor</td><td>baseline</td><td>intervention</td><td>Δ</td><td>noise floor</td><td /></tr></thead>
        <tbody>{Object.entries(r.metrics).map(([k, v]: [string, MetricRow]) => (
          <tr key={k} className={v.exceeds_noise ? '' : 'dim'}>
            <td>{k}</td><td>{fmt(v.baseline)}</td><td>{fmt(v.intervention)}</td><td>{fmt(v.delta)}</td>
            <td>{v.noise_floor !== undefined ? fmt(v.noise_floor) : '—'}</td><td>{v.exceeds_noise ? '> 2× noise' : ''}</td>
          </tr>))}
        </tbody>
      </table>
    </div>
  );
}

function Card({ title, a, b, note }: { title: string; a: number; b: number; note: React.ReactNode }) {
  const d = b - a;
  return (
    <div className="card">
      <div className="dim small">{title}</div>
      <div className="mono big">{fmt(a)} → {fmt(b)} <span className={d > 0 ? 'up' : d < 0 ? 'down' : 'dim'}>{d > 0 ? '+' : ''}{fmt(d)}</span></div>
      <div className="small dim">{note}</div>
    </div>
  );
}

function fmt(v: number): string {
  if (Number.isInteger(v)) return v.toLocaleString();
  const a = Math.abs(v);
  return a >= 100 ? v.toFixed(0) : a >= 1 ? v.toFixed(2) : v.toFixed(4);
}
