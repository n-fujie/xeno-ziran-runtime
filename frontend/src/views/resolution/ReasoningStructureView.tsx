import { useState } from 'react';
import { Labels, MissingSummary, pct, useSummary } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
const DESC_KEYS = ['dependency_depth', 'cycle_count', 'support_branching', 'incompatibility_density', 'dependency_centralization',
  'record_locality', 'support_redundancy', 'fixpoint_sensitivity', 'cluster_count', 'inter_cluster_coupling', 'unsupported_backed'];

export default function ReasoningStructureView() {
  const { data, error } = useSummary(['structures', 'adaptivity', 'descriptors']);
  const [sel, setSel] = useState('D');
  const [size, setSize] = useState('32');
  if (!data?.structures) return <MissingSummary error={error} loaded={!!data} study="matrix" />;
  const s = data.structures[sel] ?? Object.values(data.structures)[0];
  return (
    <div className="panel-view research primitives">
      <ul className="prim-list">{Object.entries(data.structures).map(([k, v]: [string, any]) => (
        <li key={k} className={k === sel ? 'on' : ''} onClick={() => setSel(k)}><span><span className="mono">{k}</span> {v.name}</span>
          <span className="dim small">{v.visible_coarse.length}/{v.conditions}</span></li>))}</ul>
      <div className="prim-detail">
        <h3><span className="mono">{sel}</span> — {s.description}</h3>
        <div><Labels ls={s.labels} /></div>
        <div className="cards">
          <div className="card"><div className="dim small">globally non-redundant (macro / global)</div><div className="mono big">{s.globally_non_redundant ? 'yes' : 'no'} ({s.visible_coarse.length})</div></div>
          <div className="card"><div className="dim small">locally non-redundant only</div><div className="mono big">{s.locally_non_redundant_only ? 'yes' : 'no'} ({s.locally_only.length})</div></div>
          <div className="card"><div className="dim small">hidden at coarse resolution</div><div className="mono big">{s.hidden.length}</div></div>
          <div className="card"><div className="dim small">bit-identical to C everywhere</div><div className="mono big">{s.exact_identical_everywhere ? 'yes' : 'no'}</div></div>
        </div>
        <h4>Factor dependence (visible = systematic at meso+; equivalent = coarse equivalence established within the stated margin)</h4>
        <table className="list mono small">
          <thead><tr><td>factor</td><td>dependent</td><td>visible at</td><td>equivalent at</td><td>unresolved at</td></tr></thead>
          <tbody>{Object.entries(s.factor_dependence).map(([f, d]: [string, any]) => (
            <tr key={f}><td>{f}</td><td>{d.dependent ? 'yes' : 'no'}</td><td>{d.visible_at.join(', ') || '—'}</td>
              <td className="dim">{d.absent_at.join(', ') || '—'}</td><td className="dim">{d.unresolved_at.join(', ') || '—'}</td></tr>))}</tbody>
        </table>
        <h4>Systematic effects where visible</h4>
        <ul className="evidence-list mono small">{s.effects.map((e: any, i: number) => (
          <li key={i}>{e.condition}: {e.resolution ?? '—'} · {e.feature ?? ''} {e.relative !== undefined ? pct(e.relative) : ''}</li>))}
          {s.effects.length === 0 && <li className="dim">none</li>}</ul>
        {data.adaptivity && (<>
          <h4>World-responsive revision (all ten triggers)</h4>
          <table className="list mono small">
            <thead><tr><td>noise</td><td>schedule adaptivity C / M / S / R</td><td>in-band C / S / M / R / A</td><td>C − R in-band (t)</td>
              <td>responded vs control</td></tr></thead>
            <tbody>{Object.entries(data.adaptivity).map(([k, a]: [string, any]) => (
              <tr key={k}><td>{k.replace('adaptivity:', '')}</td>
                <td>{['C', 'M', 'S', 'R'].map((x) => a.adaptivity[x]).join(' / ')}</td>
                <td>{['C', 'S', 'M', 'R', 'A'].map((x) => pct(a.in_band[x].share_mean, 1)).join(' / ')}</td>
                <td>{pct(a.in_band_paired['C-R'].mean, 1)} ({a.in_band_paired['C-R'].t})</td>
                <td>{pct(a.response.responded, 0)} vs {pct(a.response.control, 0)}</td></tr>))}</tbody>
          </table>
        </>)}
        <h4>Reasoning structures (descriptors) · size <select value={size} onChange={(e) => setSize(e.target.value)}>{['9', '32', '128'].map((z) => <option key={z}>{z}</option>)}</select></h4>
        <div className="scroll-x"><table className="list mono small">
          <thead><tr><td>structure</td>{DESC_KEYS.map((k) => <td key={k}>{k.replace(/_/g, ' ')}</td>)}</tr></thead>
          <tbody>{Object.entries(data.descriptors).map(([k, v]: [string, any]) => (
            <tr key={k}><td>{k}</td>{DESC_KEYS.map((d) => <td key={d}>{v[size]?.[d]}</td>)}</tr>))}</tbody>
        </table></div>
      </div>
    </div>
  );
}
