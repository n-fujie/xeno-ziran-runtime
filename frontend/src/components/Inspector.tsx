import { useEffect, useState } from 'react';
import { api, type NodeDetail } from '../api/client';
import { useSim } from '../store/sim';

export default function Inspector() {
  const info = useSim((s) => s.info);
  const selected = useSim((s) => s.selected);
  const select = useSim((s) => s.select);
  const tick = useSim((s) => s.tick);
  const running = useSim((s) => s.status?.running);
  const [d, setD] = useState<NodeDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!info || selected === null) { setD(null); return; }
    let alive = true;
    api.node(info.id, selected).then((x) => { if (alive) { setD(x); setErr(null); } }).catch((e) => setErr(String(e)));
    return () => { alive = false; };
    // refresh roughly every second while running
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info, selected, running ? Math.floor(tick / 8) : 0]);

  if (selected === null) {
    return (
      <aside className="inspector empty">
        <p className="dim">Select a configuration (zoom to the Configuration or Relation scale and click a node) to
          inspect its state and recent transitions.</p>
      </aside>
    );
  }
  if (err) return <aside className="inspector"><p className="warn">{err}</p></aside>;
  if (!d) return <aside className="inspector"><p className="dim">loading…</p></aside>;
  const near = d.difference / Math.max(1e-9, d.theta_eff);
  return (
    <aside className="inspector">
      <header>
        <h3 className="mono">c{d.id}</h3>
        <button className="ghost" onClick={() => select(null)}>×</button>
      </header>
      <div className="mono dim small">address {d.cluster_path.join(' › ')}</div>
      <div className="meter" title="difference / effective threshold">
        <div style={{ width: `${Math.min(100, near * 100)}%` }} />
      </div>
      <table className="kv mono">
        <tbody>
          <tr><td>difference</td><td>{d.difference.toFixed(3)}</td></tr>
          <tr><td>θ (base · mod)</td><td>{d.theta.toFixed(3)} · {d.theta_mod.toFixed(2)}</td></tr>
          <tr><td>θ effective</td><td>{d.theta_eff.toFixed(3)}</td></tr>
          <tr><td>retention</td><td>{d.retention.toFixed(3)}</td></tr>
          <tr><td>memory</td><td>{d.memory.toFixed(3)} <span className="dim">λ {d.mem_decay.toFixed(2)} κ {d.mem_coupling.toFixed(2)}</span></td></tr>
          <tr><td>form</td><td>{d.form}</td></tr>
          <tr><td>cap / overload</td><td>{d.cap.toFixed(2)} / {d.overload}</td></tr>
          <tr><td>wave</td><td>{d.wave_origin >= 0 ? `origin c${d.wave_origin} · depth ${d.wave_depth}` : '—'}</td></tr>
          <tr><td>ignitions</td><td>{d.ignite_count} <span className="dim">last t{d.last_ignite}</span></td></tr>
          <tr><td>constraints</td><td>{d.frozen ? 'frozen' : '—'}{d.refractory ? ` · refractory ${d.refractory}` : ''}</td></tr>
          <tr><td>in loop</td><td>{d.in_loop ? 'yes' : 'no'}</td></tr>
          <tr><td>regional shape</td><td>{d.regional_signature ?? '—'}</td></tr>
          <tr><td>geo</td><td>{d.geo ? `${d.geo[0].toFixed(1)}, ${d.geo[1].toFixed(1)}` : 'none'}</td></tr>
        </tbody>
      </table>
      <h4>Reachable transitions <span className="dim">({d.out_degree} out · {d.in_degree} in)</span></h4>
      <table className="list mono small">
        <thead><tr><td>to</td><td>w</td><td>gate</td><td>load</td><td /></tr></thead>
        <tbody>
          {d.reachable_transitions.map((r) => (
            <tr key={r.edge} className={r.reachable ? '' : 'dim'}>
              <td><button className="link" onClick={() => select(r.to)}>c{r.to}</button></td>
              <td>{r.weight.toFixed(2)}</td><td>{r.gate.toFixed(2)}</td><td>{r.load.toFixed(2)}</td>
              <td>{r.transform ? `↻${r.transform}` : ''}{r.reachable ? '' : ' blocked'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>Recent transitions</h4>
      <ul className="events mono small">
        {[...d.recent_transitions].reverse().slice(0, 40).map((e, k) => (
          <li key={k}><span className="dim">t{e.t}</span> {e.kind}
            {e.other !== undefined && <> <button className="link" onClick={() => select(Number(e.other))}>c{String(e.other)}</button></>}
            {e.depth !== undefined && <span className="dim"> depth {String(e.depth)}</span>}
            {e.form !== undefined && <span className="dim"> → form {String(e.form)}</span>}
            {e.to !== undefined && <span className="dim"> {String(e.from)} → {String(e.to)}</span>}
          </li>
        ))}
        {d.recent_transitions.length === 0 && <li className="dim">none in the retained window</li>}
      </ul>
    </aside>
  );
}
