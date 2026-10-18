// History of records (with the links between them and the registry of unobserved differences), and the statement of scope.
import { useRef } from 'react';
import type { BodyInfo, Catalog } from '../../api/xbtro';
import { DataTable } from './charts';
import { fmt } from './logic';
import { useXb } from './store';

export function HistoryTab() {
  const history = useXb((s) => s.history);
  const record = useXb((s) => s.record);
  const { openRecord, deleteRecord, exportHistory, importText, setTab } = useXb.getState();
  const file = useRef<HTMLInputElement>(null);
  return (
    <div className="xb-grid">
      <section className="xb-col">
        <div className="xb-row">
          <button onClick={() => void exportHistory()} disabled={!history?.records.length}>Export history (JSON)</button>
          <button onClick={() => file.current?.click()}>Import…</button>
          <input ref={file} type="file" accept="application/json" hidden onChange={async (e) => { const f = e.target.files?.[0]; if (f) await importText(await f.text()); e.target.value = ''; }} />
          <span className="small dim">{history?.records.length ?? 0} of {history?.limit ?? '…'} records. An import is checked against the record's own digest; an edited record is refused.</span>
        </div>
        {history && history.records.length === 0 && <div className="small dim">Nothing has been run yet. Start an experiment, or save a live run.</div>}
        <table className="xb-table">
          <thead><tr><th>#</th><th>exp.</th><th>record</th><th>from</th><th>digest</th><th>seeds</th><th>negative</th><th>unobserved</th><th /></tr></thead>
          <tbody>{history?.records.map((r) => (
            <tr key={r.id} className={record?.id === r.id ? 'sel' : ''}>
              <td className="num">{r.sequence}</td><td>{r.experiment}</td>
              <td><button className="link mono" onClick={() => { void openRecord(r.id); setTab('results'); }}>{r.id}</button></td>
              <td className="mono small">{r.parent ?? '—'}</td><td className="mono small">{r.digest}</td><td className="num">{r.seeds}</td><td className="num">{r.negative_results}</td><td className="num">{r.unobserved}</td>
              <td><button className="ghost" onClick={() => void deleteRecord(r.id)} aria-label={`delete ${r.id}`}>×</button></td>
            </tr>))}</tbody>
        </table>
      </section>
      <aside className="xb-col">
        <h4>Registry of unobserved differences</h4>
        <div className="small dim">Differences that existed in the model but were not identified, accumulated over the records; a later record that identifies one marks it. They are the targets of later observation reconfigurations.</div>
        {(history?.unobserved_registry ?? []).length === 0 && <div className="small dim">empty</div>}
        <ul className="xb-list small">{(history?.unobserved_registry ?? []).map((e) => (
          <li key={e.id}><span className="mono">{e.id}</span> — first seen in <span className="mono">{e.first_record}</span>; {e.identified_later ? <span className="ok">identified later in {e.identified_in}</span> : <span className="warn-soft">still unidentified</span>}
            <div className="dim">{e.history.slice(-3).map((h) => `${h.configuration}: ${h.status}${h.reason ? ` (${h.reason})` : ''}`).join(' · ')}</div></li>
        ))}</ul>
      </aside>
    </div>
  );
}

export function ScopeTab({ catalog, body }: { catalog: Catalog; body: BodyInfo | null }) {
  const z = catalog.ziran;
  return (
    <div className="xb-scope">
      <p>{catalog.scope}</p>
      <h4>Three kinds of value, kept apart</h4>
      <table className="xb-table"><tbody>{Object.entries(catalog.labels).map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
      <h4>Ziran System: MO · DO · ZCA · MS</h4>
      <p className="small">{z.statement}</p>
      <div className="small dim">Definitions are quoted from {z.sources.definitions}; repository status from {z.sources.reconciliation}.</div>
      {Object.entries(z.spec).map(([code, s]) => (
        <details key={code} className="xb-card">
          <summary><b>{code}</b> · {s.name} <span className="chip">{z.status[code].repository_status}</span></summary>
          <p className="small"><b>Definition (quoted).</b> {s.definition}</p>
          <p className="small"><b>Not this (quoted).</b> {s.not_this}</p>
          <p className="small"><b>The instance on this body model.</b> {z.status[code].xbtro_instance}</p>
          <p className="small warn-soft"><b>Not covered.</b> {z.status[code].not_covered}</p>
        </details>
      ))}
      <h4>Xeno-14 in this planar body</h4>
      <div className="small dim">Names and definitions from {catalog.xeno14_source}. Each is an experimental condition, never assumed to help. “proxy only” means the planar body has no counterpart of what the principle acts on; its effects say nothing about the principle.</div>
      <DataTable table={{ name: 'x14', title: '', columns: ['principle', 'fidelity', 'ignition (planar)', 'what the source rule does', 'gap'], rows: catalog.xeno14.map((p) => [p.id, p.fidelity, p.ignition, p.source_rule, p.gap]) }} />
      <h4>Tolerances fixed in advance</h4>
      <table className="xb-table"><tbody>{Object.entries(catalog.tolerance).map(([k, v]) => <tr key={k}><th>{k}</th><td className="num">{fmt(v.band * 1000)} mm</td><td className="small">{v.rule}</td></tr>)}</tbody></table>
      <div className="small dim">Bands were set from the steady fluctuation of each nominal body on tuning seeds, before any experiment was evaluated, and are not adjusted to outcomes. Recovery or settling that does not happen inside its window is recorded as censored, not as the window length.</div>
      {body && (
        <>
          <h4>Numerical status of the body on screen</h4>
          <p className="small">{body.numeric_stability.scope}. Spectral radius of the step matrix {fmt(body.numeric_stability.margin, 5)} ({body.numeric_stability.stable ? 'stable' : 'unstable'}). This does not cover the feedback loop or contact switching; those are checked at run time (a numerically diverged run is reported as such, never as a fall).</p>
        </>
      )}
    </div>
  );
}
