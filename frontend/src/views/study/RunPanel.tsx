import { useEffect, useState } from 'react';
import { api, type StudyDetail, type StudyRunRow, type StudyStatus } from '../../api/client';
import { Chip, ModeBanner, Section, Table, fmt } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Execution control and monitoring: start / stop / resume, progress, per-run table, the experiment log.

export default function RunPanel({ study, onChange }: { study: StudyDetail; onChange: () => void }) {
  const [status, setStatus] = useState<StudyStatus | null>(null);
  const [runs, setRuns] = useState<StudyRunRow[]>([]);
  const [log, setLog] = useState<any[]>([]);
  const [procs, setProcs] = useState(2);
  const [err, setErr] = useState<string | null>(null);
  const id = study.id;

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.studyStatus(id);
        if (!alive) return;
        setStatus(s);
        setRuns(await api.studyRuns(id));
        setLog(await api.studyLog(id, 60));
        if (!s.running && s.state !== 'running') return false;
      } catch (e) { if (alive) setErr(String(e)); return false; }
      return true;
    };
    let timer: ReturnType<typeof setTimeout>;
    const loop = async () => { const again = await tick(); if (alive && again) timer = setTimeout(() => void loop(), 1000); else onChange(); };
    void loop();
    return () => { alive = false; clearTimeout(timer); };
  }, [id, study.status.updated]);   // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (f: () => Promise<unknown>) => { setErr(null); try { await f(); onChange(); } catch (e) { setErr(String(e)); } };
  const s = status ?? study.status;
  const running = !!status?.running;
  const pct = s.n_total ? Math.round((100 * s.n_ok) / s.n_total) : 0;
  return (
    <div>
      <ModeBanner mode={study.mode} />
      <div className="study-row">
        <Chip s={running ? 'running' : s.state} />
        <span className="mono small">{s.n_ok}/{s.n_total} runs ok · {s.n_failed} failed{s.elapsed_s !== undefined ? ` · ${fmt(s.elapsed_s, 3)} s` : ''}</span>
        <label className="small">workers <input type="number" min={1} max={16} value={procs} onChange={(e) => setProcs(+e.target.value)} style={{ width: 50 }} /></label>
        <button className="on" disabled={running} onClick={() => void act(() => api.studyRun(id, procs))}>{s.n_ok > 0 && s.state !== 'created' ? 'Resume' : 'Start'}</button>
        <button disabled={!running} onClick={() => void act(() => api.studyStop(id))}>Stop</button>
      </div>
      <div className="study-progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div>
      {s.stop_reason && <p className="small warn">Stopped: {s.stop_reason} — {s.remaining} runs remain; Resume continues from the stored runs.</p>}
      {err && <div className="error">{err}</div>}
      <Section title="Runs" note="One record per arm × seed, stored under the experiment directory. Failed and timed-out runs are kept and counted.">
        <Table head={['arm', '#', 'gen/seed', 'status', 'fired', 'ignitions', 'unobservable', 'changes (ctl/protocol)', 's']}
          rows={runs.map((r) => [<span className="mono" key="a">{r.arm}</span>, r.index, `${r.gen}/${r.seed}`, <Chip key="s" s={r.status} />, fmt(r.metrics.fired_samples),
            fmt(r.metrics.ignitions), fmt(r.metrics.unobservable_samples), `${r.controller_changes}/${r.protocol_changes}`, fmt(r.wall_s)])} />
      </Section>
      <Section title="Experiment log">
        <ul className="small mono study-log">{log.slice().reverse().map((l, i) => <li key={i}><span className="dim">{String(l.at).slice(11, 19)}</span> {l.event}
          {l.arm ? ` ${l.arm}#${l.index}` : ''}{l.error ? ` — ${l.error}` : ''}{l.reason ? ` — ${l.reason}` : ''}</li>)}</ul>
      </Section>
    </div>
  );
}
