import { useEffect, useMemo, useState } from 'react';
import { branchLabel, components, meanSweeps, outcomeTable, type Branch, type FramesFile, type Summary, type World } from './model';

// SBS — Simondonian Body Simulation: the recorded experiments of docs/sbs/, as measured. The positions come from the saved frames and are never interpolated; the
// group colouring and the share are computed here from those positions with the cut-off of the analysis (the saved record's own values are shown beside them).
// The page states what the substrate is (a condensation model with no body in it) and what was not done.

const PALETTE = ['#e0a458', '#58a6e0', '#8fd694', '#d97fb4', '#b79cf0', '#e0d458'];
const get = async <T,>(path: string): Promise<T> => { const r = await fetch(path); if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json() as Promise<T>; };

export function Scene({ x, box }: { x: number[][]; box: number }) {
  const c = useMemo(() => components(x, box), [x, box]);
  return (
    <svg viewBox={`0 0 ${box} ${box}`} role="img" aria-label="measured particle positions" style={{ width: '100%', maxWidth: 420, background: 'var(--panel, #111)', border: '1px solid var(--line, #333)' }}>
      {x.map((p, i) => <circle key={i} cx={p[0]} cy={box - p[1]} r={0.5} fill={c.labels[i] < 0 ? '#777' : PALETTE[c.labels[i] % PALETTE.length]} />)}
    </svg>
  );
}

export function RecordsPanel({ b, ref_size }: { b: Branch; ref_size: number }) {
  const d = b.dissolution, r = b.reconfiguration;
  const f = (v: number | null | undefined, k = 2) => (v === null || v === undefined ? '—' : v.toFixed(k));
  return (
    <div style={{ overflowX: 'auto' }}><table className="small" data-testid="sbs-records">
      <caption>Six records of dissolution at the end of the intervention (reference group: {ref_size} particles) — kept apart, never summed</caption>
      <tbody>
        <tr><th>physical</th><td>largest group {f(d.physical.largest_share)} of the particles; {d.physical.bonds} contacts; {d.physical.groups_tracked} groups of 4 or more</td></tr>
        <tr><th>organizational</th><td>membership overlap with the reference group {f(d.organizational.best_overlap)}; {f(d.organizational.reference_retained_in_best_group)} of its members in the best-matching group; {d.organizational.groups_now} groups now</td></tr>
        <tr><th>functional</th><td>{d.functional_transmission.ratio === null ? `not computed (${d.functional_transmission.why ?? 'n/a'})` : `force transmission (trailing/leading displacement) ${f(d.functional_transmission.ratio)}`}</td></tr>
        <tr><th>attributional</th><td>{d.attributional}</td></tr>
        <tr><th>agentic</th><td>{d.agentic}</td></tr>
        <tr><th>observational</th><td>{d.observational}; at the end of recovery: {Object.entries(r.final_observation).map(([k, v]) => `${k} observer: ARI ${f(v.ari_vs_true_partition)} → ${v.outcome_as_read_by_observer}`).join('; ')}</td></tr>
        <tr><th>reconfiguration</th><td><b>{r.outcome}</b> (overlap {f(r.organizational.best_overlap)}, largest group {f(r.physical.largest_share)}, {r.transitions_of_cohesion} crossings of the cohesion line)</td></tr>
      </tbody>
    </table></div>
  );
}

export function OutcomesTable({ worlds }: { worlds: World[] }) {
  const rows = outcomeTable(worlds);
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r.counts)))].sort();
  return (
    <div style={{ overflowX: 'auto' }}><table className="small" data-testid="sbs-outcomes">
      <caption>Outcome of each branch over {worlds.length} worlds (true positions). The control is not at 100% persistence: read interventions against it.</caption>
      <thead><tr><th>branch</th>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{rows.map((r) => <tr key={r.key}><td>{r.label}</td>{cols.map((c) => <td key={c}>{r.counts[c] ?? 0}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

export function Hysteresis({ m }: { m: Summary['metastability'] }) {
  const { eps, up, down } = meanSweeps(m.sweeps);
  const W = 320, H = 180, px = (e: number) => 30 + ((e - eps[0]) / (eps[eps.length - 1] - eps[0])) * (W - 40), py = (v: number) => H - 20 - v * (H - 40);
  const path = (v: number[]) => v.map((y, i) => `${i ? 'L' : 'M'}${px(eps[i]).toFixed(1)},${py(y).toFixed(1)}`).join(' ');
  return (
    <figure data-testid="sbs-hysteresis" style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="largest-group share against coupling, sweep up and sweep down" style={{ width: '100%', maxWidth: 360 }}>
        <path d={path(up)} fill="none" stroke="#58a6e0" strokeWidth={2} /><path d={path(down)} fill="none" stroke="#e0a458" strokeWidth={2} />
        <text x={30} y={14} fontSize={10} fill="currentColor">up (blue) / down (orange); mean of {m.sweeps.length} sweeps</text>
        <text x={30} y={H - 4} fontSize={10} fill="currentColor">coupling {eps[0]} … {eps[eps.length - 1]}</text>
      </svg>
      <figcaption className="small dim">Hysteresis area {m.hysteresis_area_mean.toFixed(2)} ± {m.hysteresis_area_sd === null ? '—' : m.hysteresis_area_sd.toFixed(2)} (sd). Finite-time path dependence at these hold times; not a demonstration of metastability in Simondon's sense.</figcaption>
    </figure>
  );
}

export function ComparisonTable({ s }: { s: Summary }) {
  const cmp = s.comparison;
  return (
    <div data-testid="sbs-comparison" style={{ overflowX: 'auto' }}>
      <table className="small">
        <caption>Mean Brier score (lower is better), {cmp.evaluations[0]?.n_test_worlds} independent test worlds, same observed frame and intervention descriptor for every model</caption>
        <thead><tr><th>observation</th><th>protocol</th>{Object.keys(cmp.models).map((m) => <th key={m} title={cmp.models[m].label}>{m}</th>)}</tr></thead>
        <tbody>{cmp.evaluations.map((e) => <tr key={e.observation + e.protocol}><td>{e.observation}</td><td>{e.protocol.replace(/_/g, ' ')}</td>{Object.keys(cmp.models).map((m) => <td key={m}>{e.mean_brier[m].toFixed(4)}</td>)}</tr>)}</tbody>
      </table>
      <table className="small">
        <caption>Verdicts (margin {cmp.margin}; Holm-adjusted over all {cmp.comparisons.length} comparisons). UNRESOLVED is kept as such; EQUIVALENT_WITHIN_MARGIN is not identity.</caption>
        <thead><tr><th>observation</th><th>protocol</th><th>pair</th><th>Brier(y) − Brier(x)</th><th>verdict</th></tr></thead>
        <tbody>{cmp.comparisons.map((c, i) => <tr key={i}><td>{c.observation}</td><td>{c.protocol.replace(/_/g, ' ')}</td><td>{c.pair[0]} vs {c.pair[1]}</td><td>{c.brier_difference_y_minus_x.mean.toFixed(4)} [{c.brier_difference_y_minus_x.ci95.map((v) => v.toFixed(3)).join(', ')}]</td><td>{c.verdict}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

export function Evidence({ s }: { s: Summary }) {
  return (
    <div className="small" data-testid="sbs-evidence">
      <p><b>{s.classification}</b> — {s.frozen_protocol_in_code}. Protocol digest <code>{s.protocol_digest.slice(0, 12)}</code>, source revision <code>{s.source_revision.slice(0, 10)}</code>. Reproduce: <code>{s.reproduce}</code></p>
      <ul>
        <li>The substrate is a condensation model of identical particles; it contains no body. A group is what an observer detects with a declared contact cut-off.</li>
        <li>Not a validated physical result, not an actual bodily intervention, not proof of Simondonian individuation, of metastability in Simondon's sense, or of any posthuman disconnection.</li>
        <li>Not done: reproduction of the ON Lab experiments and the Operational Nihilism module (the sources are not available), and any cross-engine comparison.</li>
        <li>The comparison is exploratory with a protocol frozen in code, not a preregistered confirmatory test. A body-inclusive description showed no demonstrated advantage in this task; that is not evidence that no body-level organization exists.</li>
      </ul>
    </div>
  );
}

export default function SbsView() {
  const [sum, setSum] = useState<Summary | null>(null), [fr, setFr] = useState<FramesFile | null>(null), [err, setErr] = useState('');
  const [seed, setSeed] = useState<string>(''), [bi, setBi] = useState(0), [fi, setFi] = useState(0), [playing, setPlaying] = useState(false);
  useEffect(() => { get<Summary>('/api/sbs/summary').then(setSum).catch((e: Error) => setErr(e.message)); get<FramesFile>('/api/sbs/frames').then((f) => { setFr(f); setSeed(Object.keys(f.worlds)[0] ?? ''); }).catch((e: Error) => setErr(e.message)); }, []);
  const branches = fr && seed ? fr.worlds[seed] : [];
  const frames = branches[bi]?.frames ?? [];
  useEffect(() => { setFi(0); setPlaying(false); }, [seed, bi]);
  useEffect(() => { if (!playing) return; const h = setInterval(() => setFi((i) => (i + 1 >= frames.length ? (setPlaying(false), i) : i + 1)), 250); return () => clearInterval(h); }, [playing, frames.length]);
  if (err) return <section className="panel"><h2>SBS</h2><p role="alert">{err}. The SBS view needs the local runtime and the records in docs/sbs/ (run scripts/sbs_experiments.py).</p></section>;
  if (!sum || !fr) return <section className="panel"><h2>SBS</h2><p className="dim">loading the recorded experiments…</p></section>;
  const world = sum.worlds.find((w) => String(w.seed) === seed);
  const b = world?.branches[bi];
  const f = frames[fi];
  const live = f ? components(f.x, fr.box) : null;
  return (
    <section className="panel" aria-labelledby="sbs-h" style={{ padding: 16, display: 'grid', gap: 20 }}>
      <header>
        <h2 id="sbs-h">SBS — Simondonian Body Simulation</h2>
        <p className="small dim">Formation, hysteresis, dissolution and reconfiguration of a condensation substrate with no body in it, and a comparison of body-inclusive, body-free and dynamical descriptions. Recorded states only; nothing is interpolated.</p>
      </header>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20 }}>
        <div>
          <div className="small" style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <label>world <select value={seed} onChange={(e) => setSeed(e.target.value)}>{Object.keys(fr.worlds).map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
            <label>branch <select value={bi} onChange={(e) => setBi(Number(e.target.value))}>{branches.map((br, i) => <option key={i} value={i}>{branchLabel(br.kind, br.level)}</option>)}</select></label>
          </div>
          {f && <Scene x={f.x} box={fr.box} />}
          <div className="small" style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 6 }}>
            <button onClick={() => setPlaying((p) => !p)}>{playing ? 'Pause' : 'Play'}</button>
            <button onClick={() => { setPlaying(false); setFi((i) => Math.max(0, i - 1)); }} aria-label="previous frame">◀</button>
            <button onClick={() => { setPlaying(false); setFi((i) => Math.min(frames.length - 1, i + 1)); }} aria-label="next frame">▶</button>
            <input type="range" min={0} max={Math.max(0, frames.length - 1)} value={fi} onChange={(e) => { setPlaying(false); setFi(Number(e.target.value)); }} aria-label="time" />
          </div>
          {f && live && <p className="small" data-testid="sbs-frame">step {f.t_steps} · {f.phase} · measured frame {fi + 1}/{frames.length} · computed here from these positions (rounded to three decimals, so a contact exactly at the cut-off can differ by one from the saved record): largest group {live.largestShare.toFixed(2)}, {live.bonds} contacts, {live.groups} groups of 4 or more</p>}
        </div>
        <div style={{ flex: '1 1 380px' }}>{b && world && <RecordsPanel b={b} ref_size={world.reference_group_size} />}</div>
      </div>
      <OutcomesTable worlds={sum.worlds} />
      <Hysteresis m={sum.metastability} />
      <ComparisonTable s={sum} />
      <Evidence s={sum} />
    </section>
  );
}
