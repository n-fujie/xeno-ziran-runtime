import { useEffect, useState } from 'react';
import { api, type StudyDetail, type StudyRunRow } from '../../api/client';
import { Chip, ModeBanner, Section } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Paper outputs and reproduction: Methods / Results text, tables, figures with captions that name the experiment, the
// reproducibility package (checksums), verification, replay of a stored run and re-execution of the whole protocol.

export default function OutputsPanel({ study, runs, onChange, onOpen }: { study: StudyDetail; runs: StudyRunRow[]; onChange: () => void; onOpen: (id: string) => void }) {
  const [idx, setIdx] = useState<{ files: string[]; figures: { file: string; caption: string; png: string | null }[] } | null>(null);
  const [text, setText] = useState<{ name: string; body: string } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rep, setRep] = useState<string>('');
  const [repro, setRepro] = useState<any>(null);
  const id = study.id;

  useEffect(() => { setIdx(null); setText(null); setMsg(null); }, [id]);
  useEffect(() => {
    if (study.has_report && !idx) api.studyReport(id).then(setIdx).catch(() => undefined);
  }, [id, study.has_report]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.studyReproduction(id).then(setRepro).catch(() => setRepro(null)); }, [id, study.status.updated]);

  const run = async (f: () => Promise<any>, ok: (r: any) => string) => { setErr(null); setMsg(null); try { const r = await f(); setMsg(ok(r)); onChange(); } catch (e) { setErr(String(e)); } };
  const show = async (name: string) => setText({ name, body: await api.studyReportText(id, name) });
  const okRuns = runs.filter((r) => r.status === 'ok');

  return (
    <div>
      <ModeBanner mode={study.mode} />
      <div className="study-row">
        <button className="on" onClick={() => void run(() => api.studyReport(id).then((r) => { setIdx(r); return r; }), (r) => `${r.files.length} files written`)}>Build paper outputs</button>
        <button disabled={!study.has_report} onClick={() => void run(() => api.studyPackage(id), (r) => `${r.zip}: ${r.bytes} bytes, ${r.verify.files} files checksummed, verification ${r.verify.ok ? 'passed' : 'FAILED'}`)}>Package for reproduction</button>
        <button disabled={!study.has_package} onClick={() => void run(() => api.studyVerify(id), (r) => (r.ok ? `all ${r.files} files match their checksums` : `MISMATCH: ${[...r.mismatched, ...r.missing].join(', ')}`))}>Verify</button>
        {study.has_package && <a className="button" href={api.studyPackageUrl(id)}>Download .zip</a>}
      </div>
      {msg && <p className="small mono">{msg}</p>}
      {err && <div className="error">{err}</div>}
      {idx && (
        <>
          <Section title="Files" note="Methods and Results state measurements only; no theoretical proposition is generated. Tables are CSV; figures are SVG (PNG only when an SVG converter is installed).">
            <ul className="hpo-rows">{idx.files.map((f) => (
              <li key={f}>{f.endsWith('.md') ? <button className="link mono" onClick={() => void show(f)}>{f}</button> : <a className="mono" href={api.studyReportUrl(id, f)} target="_blank" rel="noreferrer">{f}</a>}</li>))}</ul>
            {text && <pre className="study-pre small">{text.body}</pre>}
          </Section>
          <Section title="Figures">
            {idx.figures.map((f) => (
              <figure key={f.file} className="study-fig"><img src={api.studyReportUrl(id, f.file)} alt={f.caption} /><figcaption className="small dim">{f.caption}</figcaption></figure>))}
          </Section>
        </>
      )}
      <Section title="Replay a stored run" note="Re-executes one run from the protocol alone and compares it with the stored record (wall time, CPU and memory excluded). Agreement is expected on the same machine and software versions.">
        <div className="study-row">
          <select value={rep} onChange={(e) => setRep(e.target.value)}><option value="">—</option>{okRuns.map((r) => <option key={`${r.arm}#${r.index}`} value={`${r.arm}#${r.index}`}>{r.arm} #{r.index}</option>)}</select>
          <button disabled={!rep} onClick={() => { const [a, k] = rep.split('#'); void run(() => api.studyReplay(id, a, +k), (r) => (r.agreement ? 'replay agrees with the stored run' : `DIFFERS in: ${r.metrics_differing.join(', ') || 'trace content'}`)); }}>Replay</button>
        </div>
      </Section>
      <Section title="Reproduce the whole study" note="Creates a new experiment from the registered protocol (same seeds), runs it, and compares every run record with this one.">
        <div className="study-row">
          <button disabled={study.status.state === 'created'} onClick={() => void run(() => api.studyReproduce(id, 2), (r) => { onOpen(r.id); return `started ${r.id}`; })}>Reproduce</button>
          {repro && <span className="mono small">this study reproduces {repro.of}: {fmt1(repro.identical_share)} identical over {repro.runs_compared} runs <Chip s={repro.identical_share === 1 ? 'IDENTICAL' : 'UNRESOLVED'} /></span>}
        </div>
      </Section>
    </div>
  );
}
const fmt1 = (x: number) => `${(100 * x).toFixed(1)}%`;
