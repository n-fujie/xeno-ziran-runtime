import { useMemo, useState } from 'react';
import Chart from '../../components/Chart';
import { MissingSummary, RESOLUTIONS, useSummary } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
const SHADE = ['#e6e6ea', '#b4b4bc', '#86868f', '#5f5f68', '#a0c8ff'];

export default function ScalePenetrationView() {
  const { data, error } = useSummary(['penetration', 'matrix.references']);
  const rows: any[] = useMemo(() => (data?.penetration?.rows ?? []).slice().sort((a: any, b: any) => b.scales_crossed - a.scales_crossed), [data]);
  const [sel, setSel] = useState(0);
  if (!data?.penetration) return <MissingSummary error={error} loaded={!!data} study="matrix" />;
  const r = rows[sel];
  const horizon = data.matrix.references[r?.condition]?.condition?.horizon ?? 1;
  const w = r ? r.divergence_series.local.length : 0;
  const t = Array.from({ length: w }, (_, i) => Math.round(((i + 1) * horizon) / w));
  return (
    <div className="panel-view research">
      <p className="dim small">From a local reasoning difference to the world and back: reasoning levels differ → compiled
        interventions differ → the world state differs (exact) → the targeted configurations differ → the first macro cluster
        differs (exact) → systematic differences appear at each resolution (segment onset). Divergence ratio = window distance of
        the pair ÷ distance between C and its noise replicate (0 identical, ~1 as different as an independent run). Only existing
        operational transitions are used; nothing propagates by a special path.</p>
      <h4>Comparison <select value={sel} onChange={(e) => setSel(Number(e.target.value))}>
        {rows.map((x, i) => <option key={i} value={i}>{x.comparison} · {x.condition} · depth {x.depth}</option>)}</select></h4>
      {r && (<>
        <table className="list mono small">
          <thead><tr><td>reasoning levels</td><td>interventions</td><td>world (exact)</td><td>targets (exact)</td><td>first macro cluster</td>
            {RESOLUTIONS.map((x) => <td key={x}>{x} systematic</td>)}</tr></thead>
          <tbody><tr><td>t{r.chain_steps.level ?? '—'}</td><td>t{r.chain_steps.intervention ?? '—'}</td><td>t{r.chain_steps.world ?? '—'}</td>
            <td>t{r.chain_steps.target ?? '—'}</td><td>t{r.chain_steps.macro_exact ?? '—'}</td>
            {RESOLUTIONS.map((x) => <td key={x}>{r.systematic_onset_step[x] === null ? '—' : `≥t${r.systematic_onset_step[x]}`}</td>)}</tr></tbody>
        </table>
        <div className="cards">
          <div className="card"><div className="dim small">penetration depth (coarsest systematic)</div><div className="mono big">{r.depth}</div></div>
          <div className="card"><div className="dim small">resolutions crossed</div><div className="mono big">{r.scales_crossed} / 5</div></div>
          <div className="card"><div className="dim small">amplification (end ratio, coarser ÷ finer)</div>
            <div className="mono">{Object.entries(r.amplification).map(([k, v]) => `${k} ${v}`).join(' · ')}</div></div>
          <div className="card"><div className="dim small">return into local (local ratio, late − at macro onset)</div>
            <div className="mono big">{r.return_into_local}</div></div>
        </div>
        <Chart title="divergence ratio per resolution (pair ÷ noise pair)" height={170} series={RESOLUTIONS.map((x, i) => ({
          label: x, t, v: r.divergence_series[x], color: SHADE[i] }))} />
      </>)}
      <h4>All comparisons with a trajectory difference</h4>
      <table className="list mono small">
        <thead><tr><td>vs C</td><td>condition</td><td>depth</td><td>crossed</td><td>world onset</td><td>macro onset</td>{RESOLUTIONS.map((x) => <td key={x}>{x} end ratio</td>)}<td>return</td></tr></thead>
        <tbody>{rows.slice(0, 300).map((x, i) => (
          <tr key={i} className="clickable" onClick={() => setSel(i)}><td>{x.comparison}</td><td>{x.condition}</td><td>{x.depth}</td>
            <td>{x.scales_crossed}</td><td>{x.chain_steps.world ?? '—'}</td><td>{x.chain_steps.macro_exact ?? '—'}</td>
            {RESOLUTIONS.map((y) => <td key={y}>{Number(x.divergence_ratio_end[y]).toFixed(2)}</td>)}<td>{x.return_into_local}</td></tr>))}</tbody>
      </table>
    </div>
  );
}
