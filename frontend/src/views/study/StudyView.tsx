/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useState } from 'react';
import { api, type StudyDetail, type StudyRunRow, type StudySummary } from '../../api/client';
import OutputsPanel from './OutputsPanel';
import ProtocolPanel from './ProtocolPanel';
import ResultsPanel from './ResultsPanel';
import RunPanel from './RunPanel';
import ZiranPanel from './ZiranPanel';
import { Chip, ModeBanner, Section, Table } from './common';

// Experiments: the workflow of a paper experiment on the local runtime —
//   protocol → create → run (seeded, several arms) → observation / reachability / meta-revision records → analysis →
//   figures, tables, Methods and Results → package → replay and reproduction.
// Everything shown is read from the study directory the backend wrote; nothing here is simulated in the browser.

const TABS = [['new', 'New protocol'], ['studies', 'Studies'], ['run', 'Run'], ['ziran', 'Observation & Ziran'], ['results', 'Statistics'], ['outputs', 'Paper outputs']] as const;
type Tab = typeof TABS[number][0];
const KEY = 'xzr-study-id';

function Info({ study, onChange }: { study: StudyDetail; onChange: () => void }) {
  const [path, setPath] = useState('stop.timeout_per_run_s');
  const [value, setValue] = useState('300');
  const [reason, setReason] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const amend = async () => {
    setErr(null);
    try { await api.studyAmend(study.id, path, JSON.parse(value), reason); setReason(''); onChange(); } catch (e) { setErr(String(e)); }
  };
  const m = study.manifest;
  return (
    <div>
      <ModeBanner mode={study.mode} />
      <h3>{study.title}</h3>
      <p className="mono small">{study.id} · {study.environment} · {study.n_runs} runs · {study.mode}{study.reproduces ? ` · reproduces ${study.reproduces}` : ''}</p>
      <p className="small">{study.protocol.question}</p>
      <Section title="Identity and provenance">
        <ul className="hpo-rows small mono">
          <li>protocol digest <span>{study.protocol_digest}</span></li>
          <li>registered digest <span>{study.registered_digest}</span> {study.registered_digest === study.protocol_digest ? <Chip s="IDENTICAL" /> : <Chip s="UNRESOLVED" />}</li>
          <li>git <span>{m.environment.git_commit.slice(0, 12)} ({m.environment.git_branch}, {m.environment.git_dirty ? 'dirty tree' : 'clean tree'})</span></li>
          <li>software <span>python {m.environment.python} · {Object.entries(m.environment.dependencies).filter(([, v]) => v).map(([k, v]) => `${k} ${v}`).join(' · ')}</span></li>
          <li>platform <span>{m.environment.platform}</span></li>
          <li>seeds <span>{m.seeds.slice(0, 8).map((s: number[]) => `(${s[0]},${s[1]})`).join(' ')}{m.seeds.length > 8 ? ` … ${m.seeds.length}` : ''}</span></li>
        </ul>
        <p className="small dim">{m.environment.determinism_note}</p>
      </Section>
      {study.protocol.preregistration && (
        <Section title="Preregistration" note="What was declared before the first run. Conditions chosen after looking at exploratory data are listed with their provenance.">
          <p className="small"><b>Hypothesis.</b> {study.protocol.preregistration.central_hypothesis}</p>
          <ul className="small">{study.protocol.preregistration.falsification.map((f: string, i: number) => <li key={i}>{f}</li>)}</ul>
          <p className="small dim">Power: {study.protocol.preregistration.power.n_per_arm} seeds per arm; source: {study.protocol.preregistration.power.source}. Multiplicity: {study.protocol.preregistration.analysis_plan.multiplicity}; equivalence margin ±{study.protocol.preregistration.analysis_plan.equivalence_margin}.</p>
          <Table head={['condition', 'derived from', 'source']} rows={study.protocol.preregistration.condition_provenance.map((p: any) => [p.condition, <Chip key="d" s={p.derived_from} />, <span className="small dim" key="s">{p.source}</span>])} />
        </Section>
      )}
      <Section title="Amendments after registration" note="A change after registration is never overwritten: it is recorded with its reason, and one made after a run started is analysed as exploratory.">
        {study.amendments.length === 0 ? <p className="dim small">None.</p> : <Table head={['at', 'path', 'old → new', 'status', 'reason']}
          rows={study.amendments.map((a) => [String(a.at).slice(0, 19), <span className="mono" key="p">{a.path}</span>, `${JSON.stringify(a.old)} → ${JSON.stringify(a.new)}`, a.status, a.reason])} />}
        <div className="study-row">
          <input className="mono" value={path} onChange={(e) => setPath(e.target.value)} aria-label="Protocol path" style={{ width: 200 }} />
          <input className="mono" value={value} onChange={(e) => setValue(e.target.value)} aria-label="New value (JSON)" style={{ width: 120 }} />
          <input value={reason} placeholder="reason (required)" onChange={(e) => setReason(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <button disabled={!reason.trim() || study.running} onClick={() => void amend()}>Record amendment</button>
        </div>
        {err && <div className="error">{err}</div>}
      </Section>
    </div>
  );
}

export default function StudyView() {
  const [tab, setTab] = useState<Tab>('new');
  const [list, setList] = useState<StudySummary[]>([]);
  const [id, setId] = useState<string | null>(() => { try { return localStorage.getItem(KEY); } catch { return null; } });
  const [detail, setDetail] = useState<StudyDetail | null>(null);
  const [runs, setRuns] = useState<StudyRunRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const l = await api.studies();
      setList(l);
      const cur = id && l.some((s) => s.id === id) ? id : (l[0]?.id ?? null);
      if (cur !== id) setId(cur);
      if (cur) { setDetail(await api.study(cur)); setRuns(await api.studyRuns(cur)); } else { setDetail(null); setRuns([]); }
      setErr(null);
    } catch (e) { setErr(String(e)); }
  }, [id]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { try { if (id) localStorage.setItem(KEY, id); } catch { /* storage may be unavailable */ } }, [id]);

  const open = (sid: string, to: Tab = 'run') => { setId(sid); setTab(to); };
  return (
    <div className="panel-view research study">
      <p className="small">Run a paper experiment on the local runtime: set the conditions, run independent seeds for several methods under matched
        information and authority, change what is observed, bounded and scaled, and keep every record — including failures and null results —
        for analysis, figures, Methods / Results text and a reproducibility package. Functional checks are labelled and are not evidence.</p>
      <nav className="hpo-nav">
        {TABS.map(([k, label]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}
          disabled={k !== 'new' && k !== 'studies' && !detail}>{label}</button>)}
        {detail && <span className="small mono dim" style={{ marginLeft: 10 }}>{detail.id}</span>}
      </nav>
      {err && <div className="error">{err}</div>}
      {tab === 'new' && <ProtocolPanel onCreated={(sid) => { void refresh().then(() => open(sid, 'run')); }} />}
      {tab === 'studies' && (
        <div>
          <Table head={['id', 'title', 'mode', 'state', 'runs', '']} rows={list.map((s) => [<span className="mono small" key="i">{s.id}</span>, s.title, s.mode,
            <Chip key="c" s={s.running ? 'running' : s.status.state} />, `${s.status.n_ok}/${s.n_runs}`, <button key="o" onClick={() => open(s.id, 'run')}>Open</button>])} />
          {list.length === 0 && <p className="dim small">No study yet. Create one from a protocol.</p>}
          {detail && <Info study={detail} onChange={() => void refresh()} />}
        </div>
      )}
      {tab === 'run' && detail && <RunPanel key={detail.id} study={detail} onChange={() => void refresh()} />}
      {tab === 'ziran' && detail && <ZiranPanel study={detail} runs={runs} />}
      {tab === 'results' && detail && <ResultsPanel key={detail.id} study={detail} onChange={() => void refresh()} />}
      {tab === 'outputs' && detail && <OutputsPanel study={detail} runs={runs} onChange={() => void refresh()} onOpen={(sid) => open(sid, 'run')} />}
    </div>
  );
}
