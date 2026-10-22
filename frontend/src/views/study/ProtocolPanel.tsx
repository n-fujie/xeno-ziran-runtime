import { useEffect, useMemo, useState } from 'react';
import { api, type StudyProtocol, type StudyValidation } from '../../api/client';
import { Chip, Section, Table, fmt } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Protocol authoring: pick a template, set the conditions in the form (or edit the JSON), validate (schema, seed discipline,
// fairness between arms, cost gate), and create the study. Nothing runs until the study is started.

const MODES = ['functional', 'exploratory', 'confirmatory'];

export default function ProtocolPanel({ onCreated }: { onCreated: (id: string) => void }) {
  const [templates, setTemplates] = useState<Record<string, StudyProtocol>>({});
  const [name, setName] = useState('revision-study');
  const [doc, setDoc] = useState<StudyProtocol | null>(null);
  const [raw, setRaw] = useState('');
  const [rawMode, setRawMode] = useState(false);
  const [val, setVal] = useState<StudyValidation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.studyTemplates().then((t) => { setTemplates(t); setDoc(t['revision-study']); setRaw(JSON.stringify(t['revision-study'], null, 1)); })
      .catch((e) => setErr(String(e)));
  }, []);

  const pick = (n: string) => { setName(n); setDoc(templates[n]); setRaw(JSON.stringify(templates[n], null, 1)); setVal(null); };
  const edit = (f: (d: StudyProtocol) => void) => {
    if (!doc) return;
    const d = structuredClone(doc);
    f(d);
    setDoc(d);
    setRaw(JSON.stringify(d, null, 1));
    setVal(null);
  };
  // Leave an arm in or out: arms and contrasts come from the template, so a contrast naming a left-out arm (and any
  // criterion or hypothesis referring to it) is dropped rather than left dangling.
  const toggleArm = (arm: string, on: boolean) => edit((d) => {
    const tpl = templates[name];
    const names = new Set<string>(d.arms.map((x: any) => x.name));
    if (on) names.add(arm); else names.delete(arm);
    d.arms = tpl.arms.filter((x: any) => names.has(x.name));
    d.contrasts = tpl.contrasts.filter((c: any) => names.has(c.a) && names.has(c.b));
    const ids = new Set<string>(d.contrasts.map((c: any) => c.id));
    for (const k of ['success', 'failure']) d.criteria[k] = (tpl.criteria[k] ?? []).filter((c: any) => ids.has(c.contrast));
    d.hypotheses = (tpl.hypotheses ?? []).map((h: any) => ({ ...h, contrasts: h.contrasts.filter((c: string) => ids.has(c)) }))
      .filter((h: any) => h.contrasts.length);
  });
  const parsed = useMemo(() => { try { return rawMode ? JSON.parse(raw) : doc; } catch { return null; } }, [raw, doc, rawMode]);

  const validate = async () => {
    if (!parsed) { setErr('The JSON does not parse.'); return null; }
    setErr(null);
    try { const v = await api.studyValidate(parsed); setVal(v); return v; } catch (e) { setErr(String(e)); return null; }
  };
  const create = async () => {
    if (!parsed) return;
    setBusy(true);
    try {
      const v = await validate();
      if (!v?.valid) return;
      const s = await api.studyCreate(parsed);
      onCreated(s.id);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  if (!doc) return <p className="dim small">{err ?? 'loading templates…'}</p>;
  const seeds = doc.seeds ?? {};
  return (
    <div className="study-protocol">
      <p className="small">A protocol fixes the question, the arms (methods compared, with the information each uses and what it may revise), the
        seeds, the observation / boundary / scale / time-window conditions and interventions, the metrics, the contrasts, the criteria and the
        stop conditions. Its SHA-256 is its identity. Nothing runs until the study is started.</p>
      <div className="study-row">
        <label>Template <select value={name} onChange={(e) => pick(e.target.value)}>{Object.keys(templates).map((t) => <option key={t}>{t}</option>)}</select></label>
        <label>Mode <select value={doc.mode} onChange={(e) => edit((d) => {
          d.mode = e.target.value;
          // the functional range is reserved: functional protocols must use it, every other mode must not
          if (d.seeds.gen_base !== undefined) {
            const reserved = d.mode === 'functional';
            d.seeds.gen_base = reserved ? 7000 : (d.seeds.gen_base >= 7000 && d.seeds.gen_base < 8000 ? 12000 : d.seeds.gen_base);
            d.seeds.engine_base = reserved ? 70000 : (d.seeds.engine_base >= 70000 && d.seeds.engine_base < 80000 ? 120000 : d.seeds.engine_base);
          }
        })}>{MODES.map((m) => <option key={m}>{m}</option>)}</select></label>
        <button className={rawMode ? 'on' : ''} onClick={() => { if (rawMode && parsed) setDoc(parsed); setRawMode(!rawMode); }}>{rawMode ? 'Form' : 'Edit JSON'}</button>
      </div>
      {rawMode ? (
        <textarea className="mono study-json" value={raw} spellCheck={false} onChange={(e) => { setRaw(e.target.value); setVal(null); }} aria-label="Protocol JSON" />
      ) : (
        <>
          <div className="study-grid">
            <label>Title <input value={doc.title} onChange={(e) => edit((d) => { d.title = e.target.value; })} /></label>
            <label className="wide">Question <textarea rows={2} value={doc.question} onChange={(e) => edit((d) => { d.question = e.target.value; })} /></label>
            <label>Seeds (n) <input type="number" min={1} value={seeds.n ?? seeds.list?.length ?? 1}
              onChange={(e) => edit((d) => { d.seeds = { ...(d.seeds.list ? { gen_base: d.seeds.list[0][0], engine_base: d.seeds.list[0][1] } : d.seeds), n: +e.target.value }; })} /></label>
            <label>Generator seed base <input type="number" value={seeds.gen_base ?? ''} onChange={(e) => edit((d) => { d.seeds.gen_base = +e.target.value; })} /></label>
            <label>Engine seed base <input type="number" value={seeds.engine_base ?? ''} onChange={(e) => edit((d) => { d.seeds.engine_base = +e.target.value; })} /></label>
            {doc.environment?.kind === 'hpo-world' && <>
              <label>Horizon (steps, multiple of 60) <input type="number" step={60} min={60} value={doc.environment.horizon} onChange={(e) => edit((d) => { d.environment.horizon = +e.target.value; })} /></label>
              <label>World configurations <input type="number" min={100} step={100} value={doc.environment.world?.n ?? 800} onChange={(e) => edit((d) => { d.environment.world.n = +e.target.value; })} /></label>
              <label className="check"><input type="checkbox" checked={!!doc.environment.detect_shapes} onChange={(e) => edit((d) => { d.environment.detect_shapes = e.target.checked; })} /> run the shape detector</label>
            </>}
            <label>Timeout per run (s) <input type="number" min={1} value={doc.stop.timeout_per_run_s} onChange={(e) => edit((d) => { d.stop.timeout_per_run_s = +e.target.value; })} /></label>
            <label>Wall-clock budget (s) <input type="number" min={1} value={doc.stop.max_wall_seconds} onChange={(e) => edit((d) => { d.stop.max_wall_seconds = +e.target.value; })} /></label>
            <label>Primary metric <input value={(doc.metrics.primary ?? []).join(', ')} onChange={(e) => edit((d) => { d.metrics.primary = e.target.value.split(',').map((x) => x.trim()).filter(Boolean); })} /></label>
          </div>
          <Section title="Arms" note="Uncheck an arm to leave it out (contrasts that name it are dropped).">
            <ul className="hpo-rows">
              {(templates[name]?.arms ?? doc.arms).map((a: any) => {
                const on = doc.arms.some((x: any) => x.name === a.name);
                return (
                  <li key={a.name}>
                    <label className="check"><input type="checkbox" checked={on} onChange={(e) => toggleArm(a.name, e.target.checked)} /> <b className="mono">{a.name}</b></label>
                    <span className="small dim">{a.description}</span>
                  </li>
                );
              })}
            </ul>
          </Section>
        </>
      )}
      <div className="study-row">
        <button onClick={() => void validate()}>Validate</button>
        <button className="on" disabled={busy || !parsed} onClick={() => void create()}>Create study</button>
        {val && <Chip s={val.valid ? 'valid' : 'invalid'} />}
        {val?.valid && <span className="small dim mono">{val.runs} runs · {val.step_runs} step-runs · digest {val.digest.slice(0, 12)}</span>}
      </div>
      {err && <div className="error">{err}</div>}
      {val && !val.valid && <ul className="small study-issues">{val.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
      {val?.valid && (
        <>
          {val.high_cost && <div className="study-banner">This protocol exceeds the cost gate: it needs an explicit approval record (approval.high_cost) before it can be created.</div>}
          {(val.fairness_issues ?? []).length > 0 && <div className="study-banner soft">Undeclared differences between arms: {val.fairness_issues!.join('; ')}</div>}
          <Section title="Fairness between compared arms" note={`${val.fairness?.controls.initial_condition}. ${val.fairness?.controls.evaluation}.`}>
            <Table head={['contrast', 'arms', 'declared differences', 'undeclared', 'equal on']}
              rows={(val.fairness?.contrasts ?? []).map((c) => [<span className="mono" key="i">{c.contrast}</span>, `${c.a} − ${c.b}`,
                c.declared.join(', ') || '—', <span key="u" className={c.undeclared.length ? 'warn' : 'dim'}>{c.undeclared.join(', ') || 'none'}</span>,
                <span key="e" className="small dim">{c.equal_on.join(', ')}</span>])} />
          </Section>
          <Section title="Arm profiles (information · authority · compute)">
            <Table head={['arm', 'controller', 'meta', 'history', 'authority', 'budget/epoch', 'interventions', 'horizon']}
              rows={Object.entries(val.fairness?.profiles ?? {}).map(([n, p]: [string, any]) => [<span className="mono" key="n">{n}</span>, p.controller,
                String(p.meta_revision), String(p.history_reinsertion), Array.isArray(p.revision_authority) ? p.revision_authority.join(', ') : p.revision_authority,
                fmt(p.max_changes_per_epoch), p.interventions, p.compute.horizon])} />
          </Section>
        </>
      )}
    </div>
  );
}
