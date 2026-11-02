import { useEffect, useState } from 'react';
import { api, type StudyAnalysis } from '../../api/client';
import { Chip, Section, Table } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Which research lines can actually be run, replayed or reached from this runtime, and which are only referred to. Probed from the file system by the
// backend each time; the existence of a name in a document is not a capability.

export default function LineagePanel() {
  const [m, setM] = useState<StudyAnalysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.studyLineage().then(setM).catch((e) => setErr(String(e))); }, []);
  if (err) return <div className="error">{err}</div>;
  if (!m) return <p className="dim small">probing…</p>;
  return (
    <div>
      <p className="small">{m.rule}. {Object.entries(m.counts).map(([k, v]) => `${k} ${v}`).join(' · ')}.</p>
      <Table head={['line', 'status', 'also', 'connection', 'not supported', 'scientific state']}
        rows={m.lines.map((r: any) => [<b key="l">{r.line}</b>, <Chip key="s" s={r.status} />, <span className="small" key="a">{r.also.join(', ') || '—'}</span>,
          <span className="small" key="c">{r.connection}</span>, <span className="small" key="u">{r.unsupported}</span>, <span className="small dim" key="x">{r.scientific_state}</span>])} />
      <Section title="Research environments: what each may be used for" note="Computed by the Study Engine's own validation, not asserted. Confirmatory readiness is never READY: at best a draft is CONDITIONALLY READY, blocked by the approvals it declares.">
        <Table head={['environment', 'functional', 'exploratory', 'confirmatory', 'reproducibility (evidence)']}
          rows={(m.environments ?? []).map((e: any) => [<b key="n">{e.environment}</b>, <Chip key="f" s={e.functional === 'READY' ? 'ok' : 'failed'} />,
            <span className="small" key="x">{e.exploratory}</span>, <span className="small" key="c">{e.confirmatory}</span>, <span className="small dim" key="r">{e.reproducibility}</span>])} />
      </Section>
      <Section title="Reality as a whole" note="An ontological scope, not a module."><p className="small">{m.reality_as_a_whole}</p></Section>
      <Section title="Evidence per line (this machine)">
        {m.lines.map((r: any) => (
          <details key={r.line}><summary>{r.line} — <span className="mono">{r.status}</span></summary>
            <p className="small">input: {r.input}<br />output: {r.output}<br />storage: {r.storage}<br />reproduction: {r.reproduction}</p>
            <ul className="small mono">{Object.entries(r.evidence).flatMap(([mode, ev]: any) => ev.map((e: any) => <li key={mode + e.target}>{mode}: {e.kind} {e.target} — {e.exists ? 'found' : 'MISSING'}</li>))}</ul>
          </details>))}
      </Section>
    </div>
  );
}
