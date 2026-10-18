// A stored experiment record, read back: its tables, charts and specialised views, negative results, unobserved differences, the settings that
// reproduce it, and before/after comparison with another record. All of it comes from the record returned by the runtime.
import { useMemo, useState } from 'react';
import type { Catalog, Series, Table, XbRecord } from '../../api/xbtro';
import { CouplingNetwork, DataTable, LineChart, Matrix, type Line } from './charts';
import { compareRecords, fmt } from './logic';
import { useXb } from './store';

const asArr = <T,>(x: unknown): T[] => (Array.isArray(x) ? (x as T[]) : []);
type Dict = Record<string, unknown>;
const get = (o: unknown, path: string): unknown => path.split('.').reduce<unknown>((a, k) => (a && typeof a === 'object' ? (a as Dict)[k] : undefined), o);

function SeriesCharts({ series }: { series: Record<string, Series> }) {
  const keys = Object.keys(series);
  const groups: string[][] = [];
  for (let i = 0; i < keys.length; i += 4) groups.push(keys.slice(i, i + 4));
  return (
    <div className="xb-charts">
      {groups.map((g, i) => (
        <LineChart key={i} title="Centre of mass of the paired seeds (mean ± sd, reference)" yLabel="m"
          lines={g.map((k): Line => ({ label: k, t: series[k].t, v: series[k].mean, sd: series[k].sd, layer: 'reference' }))} />
      ))}
    </div>
  );
}

function tableOf(rec: XbRecord, name: string): Table | undefined { return rec.results.tables.find((t) => t.name === name); }

function Observability({ rec }: { rec: XbRecord }) {
  const t = tableOf(rec, 'identifiability_by_configuration') ?? tableOf(rec, 'reanalysis');
  if (!t) return null;
  const ci = t.columns.indexOf('configuration'); const di = t.columns.indexOf('difference'); const si = t.columns.indexOf('status');
  const ri = t.columns.indexOf('reason unobserved'); const ei = t.columns.indexOf('exists in model reference');
  const cfgs = [...new Set(t.rows.map((r) => String(r[ci])))];
  const diffs = [...new Set(t.rows.map((r) => String(r[di])))];
  const cell = (d: string, c: string) => {
    const r = t.rows.find((x) => x[di] === d && x[ci] === c);
    if (!r) return undefined;
    const st = String(r[si]);
    return { word: st, title: `${st}${r[ri] ? ` (${r[ri]})` : ''}; exists in the model reference: ${r[ei]}`, value: st === 'unobserved' ? `unobs: ${String(r[ri]).replace('-mismatch', '')}`.slice(0, 11) : st === 'no-difference-in-model' ? 'none in model' : st.replace('identified-by-proxy', 'proxy') };
  };
  return (
    <>
      <h4>What each observation configuration identifies</h4>
      <Matrix rows={diffs} cols={cfgs} cell={cell} />
      <div className="small dim">“none in model” = the two bodies do not differ in this respect in the model reference. “unobs: …” = the difference exists in the model but this configuration cannot show it, and why (unmeasured · device · scale · time · boundary · impossible). Not seeing a difference is not the same as there being none.</div>
    </>
  );
}

function Fragility({ rec }: { rec: XbRecord }) {
  const matrix = get(rec.results, 'matrix') as Record<string, Record<string, { label: string; d: number | null; q?: number | null; group?: string }>> | undefined;
  const transfers = asArr<{ principle: string; improved: string[]; worsened: string[]; not_predicted_by_definition?: string[]; directional?: boolean; falls_in_any_condition_run?: boolean; worsened_only_by_declared_cost?: string[]; line_accounts_for?: Record<string, number | null> | null }>(get(rec.results, 'transfers'));
  if (!matrix) return null;
  const rows = Object.keys(matrix);
  const cols = Object.keys(matrix[rows[0]] ?? {});
  return (
    <>
      <h4>Effect of each condition on each organization</h4>
      <Matrix rows={rows} cols={cols} colLabel={(c) => c.replaceAll('_', ' ')}
        cell={(r, c) => { const x = matrix[r]?.[c]; return x ? { word: x.label, title: `d = ${fmt(x.d)}${x.q !== undefined ? `, q = ${fmt(x.q)}` : ''}`, value: x.label === 'improved' ? '↓' : x.label === 'worsened' ? '↑' : '·' } : undefined; }} />
      <div className="small dim">↓ improved (lower is better for every measure) · ↑ worsened · · no detectable effect. Labels need BH q &lt; 0.05 over the whole matrix and |d| ≥ 0.8; they are fixed in advance.</div>
      <h4>Fragility Transfers ({transfers.length})</h4>
      {transfers.length === 0 && <div className="small dim">None met the criterion in this record. That is a result, kept with the others.</div>}
      {transfers.map((t) => (
        <div key={t.principle} className="xb-note">
          <b className="mono">{t.principle}</b>{t.directional && <span className="chip">directional</span>}
          {t.falls_in_any_condition_run === false && <span className="chip">no falls involved</span>}
          <div className="small">improved: <span className="ok">{t.improved.join(', ') || '—'}</span> · weakened: <span className="warn">{t.worsened.join(', ') || '—'}</span></div>
          {t.not_predicted_by_definition && t.not_predicted_by_definition.length > 0 && <div className="small dim">not named by the principle's own definition: {t.not_predicted_by_definition.join(', ')}</div>}
          {t.worsened_only_by_declared_cost && t.worsened_only_by_declared_cost.length > 0 && <div className="small dim">not counted: energy use that is only the principle's declared line cost ({t.worsened_only_by_declared_cost.join(', ')})</div>}
          {t.line_accounts_for && <div className="small dim">share due to the rule line (vs the same condition with the line off): {Object.entries(t.line_accounts_for).map(([k, v]) => `${k} ${fmt(v)}`).join(' · ')}</div>}
        </div>
      ))}
    </>
  );
}

function Velocity({ rec }: { rec: XbRecord }) {
  const st = get(rec.results, 'status') as Record<string, { id: string; label: string; status: string; reason: string | null }[]> | undefined;
  if (!st) return null;
  const conds = Object.keys(st);
  const ids = st[conds[0]]?.map((r) => r.id).filter((i) => i !== 'adaptation' && i !== 'reconfiguration') ?? [];
  return (
    <>
      <h4>Established · varied · lapsed, per measure and condition</h4>
      <Matrix rows={conds} cols={ids} colLabel={(c) => c.replaceAll('_', ' ')}
        cell={(r, c) => { const x = st[r]?.find((y) => y.id === c); return x ? { word: x.status, title: x.reason ?? '', value: x.status === 'lapsed' ? `lapsed: ${(x.reason ?? '').replace('description-inapplicable', 'n/a').replace('not-achieved-in-window', 'censored').replace('line-stopped', 'stopped').slice(0, 9)}` : x.status.slice(0, 5) } : undefined; }} />
      <div className="small dim">A lapse is one of: <b>line stopped</b> (the operation behind it did not run) · <b>observation lost</b> (it still exists but the configuration cannot estimate it) · <b>description inapplicable</b> (the defining event did not occur) · <b>censored</b> (not achieved inside the window: no time is recorded for it).</div>
    </>
  );
}

function Reachability({ rec }: { rec: XbRecord }) {
  const c = get(rec.results, 'curves') as { forces: number[] } & Record<string, number[]> | undefined;
  if (!c) return null;
  return <LineChart title="Fraction of seeds that recover from a push of a given force" xLabel="N" yLabel="fraction"
    lines={Object.keys(c).filter((k) => k !== 'forces').map((k) => ({ label: k, t: c.forces, v: c[k] }))} />;
}

function Specialised({ rec }: { rec: XbRecord }) {
  const e = rec.experiment;
  const coupling = get(rec.results, 'coupling') as { nodes: string[]; edges: Parameters<typeof CouplingNetwork>[0]['edges']; classes: Record<string, number> } | undefined;
  return (
    <div className="xb-analysis">
      {['A', 'E', 'M', 'RE'].includes(e) && <Observability rec={rec} />}
      {e === 'B' && coupling && (
        <>
          <h4>Couplings between operation lines</h4>
          <CouplingNetwork nodes={coupling.nodes} edges={coupling.edges} />
          <div className="small dim">{Object.entries(coupling.classes).map(([k, v]) => `${v} ${k}`).join(' · ')}. Correlation, synchrony or prediction alone never makes an edge “interventionally-supported”: an intervention on the source has to change the target.</div>
        </>
      )}
      {['C', 'G', 'R'].includes(e) && <Fragility rec={rec} />}
      {e === 'D' && <Velocity rec={rec} />}
      {e === 'F' && <Reachability rec={rec} />}
    </div>
  );
}

export function RecordView({ rec, catalog }: { rec: XbRecord; catalog: Catalog }) {
  const { exportRecord, rerun, reanalyse, reenter, openRecord } = useXb.getState();
  const history = useXb((s) => s.history);
  const [obsName, setObsName] = useState('full');
  const [reExp, setReExp] = useState('B');
  const [part, setPart] = useState<'analysis' | 'tables' | 'charts' | 'reproduce'>('analysis');
  const title = catalog.experiments.find((x) => x.id === rec.experiment)?.title ?? (rec.experiment === 'RE' ? 'Re-observation of a stored simulation' : rec.experiment === 'L' ? 'Live run' : rec.experiment);
  const series = rec.results.series as Record<string, Series> | undefined;
  const hasPair = !!rec.results.pair;
  const design = get(rec.results, 'design') as { reading?: string } | undefined;
  return (
    <article className="xb-record">
      <header>
        <h3>{rec.experiment} · {title}</h3>
        <div className="mono small dim">{rec.id} · digest {rec.digest.slice(0, 16)}… · {rec.model_version} · {rec.seeds.length} seeds ({rec.seeds[0]}…{rec.seeds[rec.seeds.length - 1]}) · {rec.provenance.python} / numpy {rec.provenance.numpy}</div>
        {typeof rec.results.reading === 'string' && <p className="small">{rec.results.reading}</p>}
        {design?.reading && <p className="small dim">Design: {design.reading}</p>}
        <div className="xb-row">
          <button onClick={() => void exportRecord(rec.id, 'json')}>Export JSON</button>
          <button onClick={() => void exportRecord(rec.id, 'csv')}>Export CSV</button>
          <button onClick={() => void rerun(rec.id)} disabled={!rec.rerun || !catalog.experiments.some((x) => x.id === rec.rerun.experiment)} title="Repeat from the stored settings; the digest should match">Re-run</button>
        </div>
      </header>
      <nav className="xb-tabs small" aria-label="Parts of the record">
        {(['analysis', 'tables', 'charts', 'reproduce'] as const).map((p) => <button key={p} className={part === p ? 'on' : ''} onClick={() => setPart(p)}>{p}</button>)}
      </nav>
      {part === 'analysis' && (
        <>
          <Specialised rec={rec} />
          <h4>Negative and null results ({rec.negative_results.length})</h4>
          {rec.negative_results.length === 0 ? <div className="small dim">none recorded</div>
            : <ul className="xb-list small">{rec.negative_results.slice(0, 80).map((n, i) => <li key={i}>{n.statement}</li>)}</ul>}
          <h4>Differences that exist in the model but were not identified ({rec.unobserved_differences.length})</h4>
          {rec.unobserved_differences.length === 0 ? <div className="small dim">none recorded</div>
            : <ul className="xb-list small">{rec.unobserved_differences.slice(0, 80).map((u, i) => <li key={i}><span className="mono">{u.id}</span> — {u.status}{u.reason ? ` (${u.reason})` : ''} · {u.configuration}</li>)}</ul>}
        </>
      )}
      {part === 'tables' && rec.results.tables.map((t) => <section key={t.name}><h4>{t.title}</h4><DataTable table={t} /></section>)}
      {part === 'charts' && (series && Object.keys(series).length ? <SeriesCharts series={series} /> : <div className="small dim">This record stores no time series.</div>)}
      {part === 'reproduce' && (
        <div className="xb-reproduce">
          <h4>Settings that reproduce this record</h4>
          <pre className="mono small">{JSON.stringify({ experiment: rec.rerun.experiment, parameters: rec.parameters, seeds: rec.seeds, time_step_s: rec.time_step_s, numerical_method: rec.numerical_method }, null, 1)}</pre>
          <h4>History</h4>
          <pre className="mono small">{JSON.stringify(rec.history, null, 1)}</pre>
          <h4>Further operations</h4>
          <div className="xb-row">
            <select value={obsName} onChange={(e) => setObsName(e.target.value)} aria-label="observation configuration">
              {Object.keys(catalog.observation.presets).map((k) => <option key={k}>{k}</option>)}</select>
            <button onClick={() => void reanalyse(rec.id, { name: obsName })} disabled={!hasPair}
              title={hasPair ? 'Observe the stored simulated bodies again under this configuration' : 'only records of A, E and M store the pair of bodies'}>Re-observe</button>
            <span className="small dim">re-observation of a simulation, not a new measurement</span>
          </div>
          <div className="xb-row">
            <select value={reExp} onChange={(e) => setReExp(e.target.value)} aria-label="experiment to re-enter">
              {catalog.experiments.filter((x) => ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'M'].includes(x.id)).map((x) => <option key={x.id} value={x.id}>{x.id} · {x.title}</option>)}</select>
            <button onClick={() => void reenter(rec.id, reExp, { n_seeds: Math.max(4, Math.min(12, rec.seeds.length)) })} title="Start the experiment from the retained slow state (fatigue, energy, adaptation, tension) at the end of this record">Re-enter its end state</button>
          </div>
          <div className="xb-row">
            <select value="" onChange={(e) => { if (e.target.value) void openRecord(e.target.value, 'compare'); }} aria-label="record to compare with">
              <option value="">compare with…</option>{history?.records.filter((r) => r.id !== rec.id).map((r) => <option key={r.id} value={r.id}>{r.sequence}. {r.experiment} · {r.id}</option>)}</select>
          </div>
        </div>
      )}
    </article>
  );
}

export function ComparePanel({ a, b }: { a: XbRecord; b: XbRecord }) {
  const diffs = useMemo(() => compareRecords(a, b), [a, b]);
  return (
    <section className="xb-compare">
      <h3>Before / after</h3>
      <div className="small dim">{a.id} → {b.id}. Tables with the same name and columns are matched row by row on their text columns; the numbers are differenced (second minus first).</div>
      {diffs.length === 0 && <div className="small warn-soft">These records share no table with the same columns, so there is nothing to difference. (Records of the same experiment share their tables.)</div>}
      {diffs.map((d) => (
        <div key={d.name} className="xb-table-wrap">
          <h4>{d.title}</h4>
          <table className="xb-table"><thead><tr><th>{d.labelColumns.join(' · ')}</th>{d.rows[0]?.cells.map((c) => <th key={c.column} colSpan={3}>{c.column}</th>)}</tr>
            <tr><th />{d.rows[0]?.cells.map((c) => <><th key={c.column + 'a'}>before</th><th key={c.column + 'b'}>after</th><th key={c.column + 'd'}>Δ</th></>)}</tr></thead>
            <tbody>{d.rows.slice(0, 200).map((r) => (
              <tr key={r.key}><th className="rowh">{r.key}</th>{r.cells.map((c) => <><td className="num" key={c.column + 'a'}>{fmt(c.a)}</td><td className="num" key={c.column + 'b'}>{fmt(c.b)}</td>
                <td className={`num ${c.delta === null ? '' : c.delta > 0 ? 'up' : c.delta < 0 ? 'down' : ''}`} key={c.column + 'd'}>{c.delta === null ? '—' : (c.delta > 0 ? '+' : '') + fmt(c.delta)}</td></>)}</tr>
            ))}</tbody></table>
          {(d.onlyInA > 0 || d.onlyInB > 0) && <div className="small dim">{d.onlyInA} row(s) only before, {d.onlyInB} only after</div>}
        </div>
      ))}
    </section>
  );
}
