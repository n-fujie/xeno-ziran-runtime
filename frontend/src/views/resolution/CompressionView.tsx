import { MissingSummary, useSummary } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
const f = (x: any, d = 3) => (x?.mean === null || x?.mean === undefined ? '—' : `${Number(x.mean).toFixed(d)} ± ${Number(x.sd).toFixed(d)}`);

export default function CompressionView() {
  const { data, error } = useSummary(['compression']);
  if (!data?.compression) return <MissingSummary error={error} loaded={!!data} study="compression" />;
  const hs = data.compression.horizons;
  return (
    <div className="panel-view research">
      <p className="dim small">Recurrent trajectories summarised every 10 steps at macro resolution (8 clusters × activity,
        memory, difference) are quantized into 32 recurrent shapes and factorised into recurring phrases (LZ78). The shapes
        are detected summaries; they never enter the runtime. Distinction fidelity asks whether what separates two structures
        (and the noise floor) survives compression.</p>
      {Object.entries(hs).map(([h, r]: [string, any]) => (
        <div key={h}>
          <h4>{Number(h).toLocaleString()} steps · {r.seeds} seeds</h4>
          <table className="list mono small">
            <thead><tr><td>run</td><td>compression ratio</td><td>phrases</td><td>replay R²</td><td>path dependence raw</td><td>path dependence compressed</td></tr></thead>
            <tbody>{Object.entries(r.per_variant).map(([k, v]: [string, any]) => (
              <tr key={k}><td>{k}</td><td>{f(v.compression_ratio, 2)}</td><td>{f(v.phrases, 0)}</td><td>{f(v.replay_r2)}</td>
                <td>{f(v.path_dependence_raw)}</td><td>{f(v.path_dependence_compressed)}</td></tr>))}</tbody>
          </table>
          <table className="list mono small">
            <thead><tr><td>pair vs C</td><td>distance ÷ noise raw</td><td>compressed</td><td>systematic raw</td><td>systematic compressed</td>
              <td>onset delay (windows)</td><td>onset lost</td><td>local difference corr.</td><td>local magnitude kept</td></tr></thead>
            <tbody>{Object.entries(r.pairs).map(([k, v]: [string, any]) => (
              <tr key={k}><td>{k}</td><td>{f(v.raw_distance_ratio)}</td><td>{f(v.compressed_distance_ratio)}</td>
                <td>{v.systematic_raw.detected ? 'yes' : 'no'}</td><td>{v.systematic_compressed.detected ? 'yes' : 'no'}</td>
                <td>{f(v.onset_delay_windows, 1)}</td><td>{v.onset_missing_compressed}</td><td>{f(v.local_difference_correlation)}</td>
                <td>{f(v.local_magnitude_ratio)}</td></tr>))}</tbody>
          </table>
        </div>))}
    </div>
  );
}
