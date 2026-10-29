import { useState } from 'react';
import { candidateRows, classCounts, compareMfs, CLASSES, equivalenceOf, sssAt, sssGrid, sssStatement, type LibraryOut } from './mfsPanels';

// RESEARCH, fifth stage — the saved results of experiments F-K: the table of conditions F1-F16, the candidate retaining sets (validated or rejected, kept apart), the comparison of two MFS and
// the SSS map of an MFS. Everything is read from the library the server returns; a candidate that failed the search or the validation is listed as a candidate, never as an MFS.

const REGION_COLOR: Record<string, string> = { ACTIVE: '#47c26b', 'OBSERVATION-SENSITIVE': '#7aa7e0', DEGRADED: '#c9a227', COLLAPSED: '#d04a3a', RECOVERING: '#5fb98a' };
export interface MfsInitial { mfs?: string; experiment?: string; sssmap?: string }

export default function MfsPanels({ lib, initial, seed, busy, onRun }: { lib: LibraryOut | null; initial: MfsInitial; seed: number; busy: boolean; onRun: (id: string) => void }) {
  const [a, setA] = useState(initial.mfs ?? initial.sssmap ?? ''), [b, setB] = useState(''), [sssId, setSssId] = useState(initial.sssmap ?? initial.mfs ?? '');
  const ids = (lib?.mfs ?? []).map((m) => m.id);
  if (!lib || !lib.mfs.length) return <fieldset className="eco-group"><legend>saved results of experiments F-K (fifth stage)</legend><div className="eco-note">The saved results are not on this server: run backend/scripts/meos_experiments_v5.py and backend/scripts/finalize_stage5.py.</div></fieldset>;
  // a selection that names nothing falls back to the first MFS (A, the map) or the second (B)
  const pick = (id: string, fallback: number) => lib.mfs.find((m) => m.id === id) ?? lib.mfs[Math.min(fallback, lib.mfs.length - 1)];
  const A = pick(a, 0), S = pick(sssId, 0);
  const B = lib.mfs.find((m) => m.id === b) ?? lib.mfs.find((m) => m.condition_id === A.condition_id && m.id !== A.id) ?? pick('', 1);  // B starts as the other MFS of A's condition, when it has one
  const counts = classCounts(lib.classification_table), eq = A && B && A.id !== B.id ? equivalenceOf(lib.route_equivalence, A.id, B.id, lib.mfs) : undefined;
  const grid = S?.sss_points?.length ? sssGrid(S.sss_points) : null;
  const focus = initial.experiment?.toUpperCase();
  return (
    <fieldset className="eco-group" data-testid="eco-mfs-panels"><legend>saved results of experiments F-K (fifth stage)</legend>
      <div className="eco-note"><b>Multiple operational realisations are not a general rule: they are local to particular conditions.</b> Search seeds 1-5 and validation seeds 6-10 are kept apart; a set is an MFS only if it is inclusion-minimal on the search seeds and persists on every validation seed.</div>
      <div className="eco-row" data-testid="eco-class-counts">{CLASSES.map((k) => <span key={k} className="eco-chip">{`${k} ${counts[k]}`}</span>)}</div>

      <details open={!!focus}><summary className="dim">conditions F1-F16 · classification</summary>
        <table className="eco-table" data-testid="eco-f-compact"><thead><tr><th>id</th><th>condition</th><th>cand.</th><th>MFS</th><th>history</th><th>class</th></tr></thead>
          <tbody>{lib.classification_table.map((r) => <tr key={r.condition_id} data-focus={focus === r.condition_id ? 'true' : undefined} style={focus === r.condition_id ? { outline: '2px solid #2f8fd0' } : undefined}>
            <td>{r.condition_id}</td><td>{r.description}</td><td>{r.candidate_retaining_sets}</td><td>{r.validated_mfs}</td><td>{r.history_role}</td><td><b>{r.classification}</b></td></tr>)}</tbody></table>
        <details><summary className="dim">all columns (roles, SSS region, observational robustness, MFS ids)</summary>
        <div style={{ overflowX: 'auto', maxWidth: '100%' }}><table className="eco-table" data-testid="eco-f-table"><thead><tr><th>id</th><th>condition</th><th>candidates</th><th>validated MFS</th><th>MFS</th><th>cardinality</th><th>history</th><th>M2</th><th>Address</th><th>coupling</th><th>resource</th><th>renewal</th><th>SSS region</th><th>obs. robustness</th><th>class</th></tr></thead>
          <tbody>{lib.classification_table.map((r) => <tr key={r.condition_id} data-fullfocus={focus === r.condition_id ? 'true' : undefined} style={focus === r.condition_id ? { outline: '2px solid #2f8fd0' } : undefined}>
            <td>{r.condition_id}</td><td>{r.description}</td><td>{r.candidate_retaining_sets}</td><td>{r.validated_mfs}</td><td>{r.mfs_ids.join(', ') || '—'}</td><td>{r.cardinality.join(', ') || '—'}</td><td>{r.history_role}</td><td>{r.m2_role}</td><td>{r.address_role}</td><td>{r.coupling_role}</td><td>{r.resource_role}</td><td>{r.renewal_role}</td>
            <td>{r.sss_region_default_setting.join(', ') || '—'}</td><td>{r.observational_robustness.map((v) => (v === null ? '—' : v.toFixed(2))).join(', ') || '—'}</td><td><b>{r.classification}</b></td></tr>)}</tbody></table></div>
        </details>
        <div className="eco-note">search seeds {lib.classification_table[0]?.search_seeds.join(', ')} · validation seeds {lib.classification_table[0]?.validation_seeds.join(', ')}</div></details>

      <details><summary className="dim">candidates: validated MFS and rejected candidate sets</summary>
        <table className="eco-table" data-testid="eco-candidates"><thead><tr><th>set</th><th>condition</th><th>components</th><th>on search seeds</th><th>on validation seeds</th><th>status</th></tr></thead>
          <tbody>{candidateRows(lib).map((c) => <tr key={c.id}><td style={{ textDecoration: c.mark === 'validated MFS' ? 'none' : 'underline dotted' }}>{c.id}</td><td>{c.condition_id}</td><td>{c.cardinality}: {c.retained.join(', ')}</td><td>{c.search}</td><td>{c.validation}</td><td>{c.mark === 'validated MFS' ? c.mark : `${c.mark} (${c.status})`}</td></tr>)}</tbody></table>
        <div className="eco-note">F8: the second retaining set found on the first three search seeds did not survive the five-seed search and the independent validation; it is kept here as a rejected candidate and F8 is not counted as a condition with multiple MFS. F9: Under the allowed reductions and specified preservation criterion, no validated inclusion-minimal retaining set was found. (A negative result for this condition, not a general statement.)</div></details>

      <details open={!!initial.mfs}><summary className="dim">compare two MFS</summary>
        <div className="eco-row"><label>A <select value={A.id} onChange={(e) => setA(e.target.value)}>{ids.map((i) => <option key={i}>{i}</option>)}</select></label><label>B <select value={B.id} onChange={(e) => setB(e.target.value)}>{ids.map((i) => <option key={i}>{i}</option>)}</select></label>
          <button disabled={busy} onClick={() => onRun(A.id)} title={`run the configuration of ${A.id} on seed ${seed}`}>RUN A</button><button disabled={busy} onClick={() => onRun(B.id)}>RUN B</button></div>
        <table className="eco-table" data-testid="eco-mfs-compare"><thead><tr><th>measure</th><th>{A.id}</th><th>{B.id}</th></tr></thead><tbody>{compareMfs(A, B).map((r) => <tr key={r.measure} className={r.differs ? 'diff' : ''}><td>{r.measure}</td><td>{r.a}</td><td>{r.b}</td></tr>)}</tbody></table>
        {A.id !== B.id && <div className="eco-note" data-testid="eco-equivalence">{eq ? <><b>{eq.class}</b>: {eq.verdict}{eq.via ? ` (${eq.via})` : ''}</> : 'This pair was not compared in the saved results: no equivalence is stated.'}</div>}</details>

      <details open={!!initial.sssmap}><summary className="dim">SSS map of an MFS</summary>
        <div className="eco-row"><label>MFS <select value={S.id} onChange={(e) => setSssId(e.target.value)}>{ids.map((i) => <option key={i}>{i}</option>)}</select></label></div>
        {grid ? <div data-testid="eco-sss-map"><div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>{grid.speeds.map((sp) => { const g = sssGrid((S.sss_points ?? []).filter((p) => p.speed === sp)); return <div key={sp}><div className="dim">speed {sp}</div><table className="eco-table"><thead><tr><th>size \ scale</th>{g.scales.map((x) => <th key={x}>{x}</th>)}</tr></thead>
          <tbody>{g.sizes.map((sz) => <tr key={sz}><td>{sz}</td>{g.scales.map((x) => { const r = sssAt(g, x, sz, sp); return <td key={x} title={r ?? 'not tested'} style={{ background: r ? REGION_COLOR[r] ?? '#999' : 'transparent', color: r ? '#111' : undefined }}>{r ? r.slice(0, 3) : '·'}</td>; })}</tr>)}</tbody></table></div>; })}</div>
          <div className="eco-note">{sssStatement(S.sss_points ?? [])} Each table lists only the scales and sizes tested at its speed; a dot is a point that was not tested. OBS = OBSERVATION-SENSITIVE, COL = COLLAPSED.</div></div> : <div className="eco-note">No SSS points are saved for {S.id}.</div>}
      </details>
    </fieldset>
  );
}
