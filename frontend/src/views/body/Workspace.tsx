import { useEffect, useState } from 'react';
import './body.css';
import ViewA from './BodyView';
import { teooFigure, teooLegal, teooSession, teooSafety, type FigureOut, type LegalBundle, type SafetyOut } from './bodyApi';
import { needsSyntheticBanner } from './bodyDraw';
import { svgToPng } from './png';
import type { Session } from './session';
import { Plot as _Plot, ViewB, ViewC, ViewD, ViewE, ViewF, ViewG, ViewH, ViewI } from './views';

// BODY / TOTAL OBSERVATION — the workspace: View A (unchanged) and Views B-H over one session bundle. The shared header names the time base, the time t and the body configuration versions every view uses.
export const TABS = [['A', 'Body Observation'], ['B', 'Temporal Operational Shape'], ['C', 'Relational Observation'], ['D', 'Observation Limits'], ['E', 'Intervention'], ['F', 'Reconstruction'], ['G', 'Experimental Evidence'], ['H', 'Total Observation'], ['I', 'AI Legal Governance']] as const;
export type Tab = (typeof TABS)[number][0];
const FIGURE_OF: Partial<Record<Tab, string>> = { A: 'body', B: 'timeseries', D: 'limits', G: 'evidence' };
void _Plot;

function download(name: string, data: string | Uint8Array, type: string) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([data as BlobPart], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function SyntheticBanner() {
  return <div className="teoo-banner" role="alert" data-testid="teoo-synthetic-banner">SYNTHETIC — artificial functional-test data. Not a measurement, not a physiological model. This banner cannot be hidden.</div>;
}

export function ExportBar({ kind, safety }: { kind: string; safety: SafetyOut | null }) {
  const [fig, setFig] = useState<FigureOut | null>(null), [msg, setMsg] = useState('');
  // a response for a tab that has since been left must not replace the figure of the current tab (it would be exported under the wrong title and metadata)
  useEffect(() => { let live = true; setFig(null); teooFigure(kind).then((f) => { if (live) setFig(f); }).catch((e: Error) => { if (live) setMsg(e.message); }); return () => { live = false; }; }, [kind]);
  if (!fig) return <div className="small dim" data-testid="teoo-export">{msg || 'preparing the figure…'}</div>;
  const id = fig.metadata.figure_id;
  return (
    <div className="teoo-export small" data-testid="teoo-export">
      <b>Export figure {id}</b> (evidence: {fig.metadata.evidence.classes.join(' + ')}; the band and the watermark are part of the figure)
      <button onClick={() => download(`${id}.svg`, fig.svg, 'image/svg+xml')} data-testid="teoo-export-svg">SVG</button>
      <button onClick={() => { void svgToPng(fig.svg, fig.metadata_ascii).then((b) => download(`${id}.png`, b, 'image/png')).catch((e: Error) => setMsg(e.message)); }} data-testid="teoo-export-png">PNG</button>
      <button onClick={() => download(`${id}.json`, JSON.stringify(fig.metadata, null, 1), 'application/json')} data-testid="teoo-export-json">JSON metadata</button>
      {fig.issues.length > 0 && <span className="teoo-bad"> verification failed: {fig.issues.join('; ')}</span>}
      {msg && <span className="teoo-bad"> {msg}</span>}
      <span className="dim"> · human data ingestion: {safety?.production_ready ? 'gate open' : 'closed (see Protections)'}</span>
    </div>
  );
}

export default function Workspace() {
  const [s, setS] = useState<Session | null>(null), [tab, setTab] = useState<Tab>('A'), [t, setT] = useState(0), [variable, setVariable] = useState('joint.angle.knee_l');
  const [safety, setSafety] = useState<SafetyOut | null>(null), [err, setErr] = useState<string | null>(null), [legal, setLegal] = useState<LegalBundle | null>(null);
  useEffect(() => { teooSession().then(setS).catch((e: Error) => setErr(e.message)); teooSafety().then(setSafety).catch(() => undefined); }, []);
  useEffect(() => { if (tab === 'I' && !legal) teooLegal().then(setLegal).catch((e: Error) => setErr(e.message)); }, [tab, legal]);
  if (err) return <div className="panel-view" data-testid="teoo-error"><b>BODY / TOTAL OBSERVATION</b><div className="dim">{err}</div></div>;
  if (!s) return <div className="panel-view dim">loading…</div>;
  const fig = FIGURE_OF[tab];
  return (
    <div className="teoo-workspace" data-testid="teoo-workspace">
      <nav className="teoo-tabs" role="tablist" aria-label="BODY / TOTAL OBSERVATION views">
        {TABS.map(([k, name]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)} data-testid={`teoo-tab-${k}`}>{k} · {name}</button>)}
      </nav>
      <div className="teoo-shared small" data-testid="teoo-shared"><span>time base: {s.time_base}</span><span>t = <b>{t} s</b> <input type="range" min={0} max={20} step={1} value={t} onChange={(e) => setT(Number(e.target.value))} aria-label="time t (s)" data-testid="teoo-t" /></span>
        <span>body version {s.body_versions.before} (before) / {s.body_versions.after} (after the brace)</span><span>{s.records.length} records · ledger {s.ledger.issues.length === 0 ? 'verified' : 'issues'}</span></div>
      {tab === 'A' ? <ViewA /> : (
        <div className="teoo-pane">
          {needsSyntheticBanner(s.records) && <SyntheticBanner />}
          {tab === 'B' && <ViewB s={s} variable={variable} onVariable={setVariable} />}
          {tab === 'C' && <ViewC s={s} t={t} />}
          {tab === 'D' && <ViewD s={s} t={t} />}
          {tab === 'E' && <ViewE s={s} />}
          {tab === 'F' && <ViewF s={s} />}
          {tab === 'G' && <ViewG s={s} />}
          {tab === 'H' && <ViewH s={s} t={t} />}
          {tab === 'I' && (legal ? <><SyntheticBanner /><ViewI b={legal} /></> : <div className="dim">loading…</div>)}
        </div>
      )}
      {fig && <ExportBar kind={fig} safety={safety} />}
      {safety && <section className="teoo-protections" data-testid="teoo-safety"><h4>Data protection and the production gate</h4>
        <div className="small">Human measurements may be ingested for real: <b>{safety.human_measurement_ingestion_allowed ? 'yes' : 'no'}</b>. Missing: {safety.missing.map((m) => m.needed).join('; ')}. {safety.note}</div></section>}
    </div>
  );
}
