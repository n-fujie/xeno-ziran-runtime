import { useEffect, useState } from 'react';
import { api, type Shapes } from '../api/client';
import { useSim } from '../store/sim';

export default function ShapePanel() {
  const info = useSim((s) => s.info);
  const tick = useSim((s) => s.tick);
  const [sh, setSh] = useState<Shapes | null>(null);
  const [showInterp, setShowInterp] = useState(false);

  useEffect(() => {
    if (info) void api.shapes(info.id).then(setSh);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info, Math.floor(tick / 10)]);
  if (!sh) return <aside className="shapepanel dim">…</aside>;
  const interp = Object.fromEntries(sh.interpretation.interpretations.map((x) => [x.signature, x.labels]));
  return (
    <aside className="shapepanel">
      <h4>Abstract Shape Space</h4>
      <p className="dim small">Each configuration is placed by its operational descriptors (PCA of ignition rate, memory, retention,
        effective threshold, degree, loop membership, return and transformation rates, bottleneck share, difference) — not by
        connectivity or geography. Nearby = operationally alike.</p>
      <table className="list mono small">
        <thead><tr><td>descriptor</td><td>axis 1</td><td>axis 2</td></tr></thead>
        <tbody>{Object.entries(sh.embedding_loadings).map(([k, [a, b]]) => (
          <tr key={k}><td>{k}</td><td>{a.toFixed(2)}</td><td>{b.toFixed(2)}</td></tr>))}</tbody>
      </table>
      <h4>Recurrent operational shapes</h4>
      <p className="dim small">Regional clusters quantized per axis into lower / middle / upper third (relative to the field now):
        {' '}{sh.axes.map((a) => `${a.key} ${a.descriptor}`).join(' · ')}.</p>
      <table className="list mono small">
        <thead><tr><td>signature</td><td>now</td><td>max</td><td>passes</td><td>first</td></tr></thead>
        <tbody>{sh.recurrent_shapes.map((r) => (
          <tr key={r.signature}>
            <td>{r.signature}{showInterp && interp[r.signature]?.length ? (
              <div className="interp">{interp[r.signature].map((l) => <span key={l.label} title={`${l.rule} — ${l.gloss}`}>{l.label}</span>)}</div>) : null}</td>
            <td>{r.clusters_now}</td><td>{r.max_clusters}</td><td>{r.passes}</td><td>t{r.first_seen}</td>
          </tr>))}</tbody>
      </table>
      <label className="small"><input type="checkbox" checked={showInterp} onChange={(e) => setShowInterp(e.target.checked)} />
        {' '}show optional interpretation layer</label>
      {showInterp && <p className="small warn-soft">{sh.interpretation.disclaimer}</p>}
      {showInterp && <details className="small"><summary className="dim">interpretation rules</summary>
        <ul className="mono">{sh.interpretation.rules.map((r) => <li key={r.label}>{r.label}: {r.rule} <span className="dim">— {r.gloss}</span></li>)}</ul></details>}
    </aside>
  );
}
