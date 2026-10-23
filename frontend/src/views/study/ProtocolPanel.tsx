import { useEffect, useMemo, useState } from 'react';
import { api, type StudyProtocol, type StudyValidation } from '../../api/client';
import { Chip, Section, Table, fmt } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Protocol authoring: pick a template, set the conditions in the form (or edit the JSON), validate (schema, seed discipline,
// fairness between arms, cost gate), and create the study. Nothing runs until the study is started.

const MODES = ['functional', 'exploratory', 'confirmatory'];

// Conditions of the total-observation line, as the protocol's environment sets them. Scale / Size / Speed are the groups of parameters the backend
// declares for the three axes (xzr.totalobs.sss); the planetary-scale conditions are evaluated by the backend for exactly these values.
const FIELDS: { group: string; key: string; path: [string, string] | [string]; step?: number; min?: number }[] = [
  { group: 'Observation layout', key: 'sensors', path: ['net', 'n_sensors'], min: 1 },
  { group: 'Observation layout', key: 'footprint radius', path: ['net', 'radius'], min: 1 },
  { group: 'Observation layout', key: 'absorption by observing', path: ['net', 'backaction'], step: 0.05, min: 0 },
  { group: 'Observation layout', key: 'wear of the observer', path: ['net', 'wear'], step: 0.05, min: 0 },
  { group: 'Observation layout', key: 'resource pool / step', path: ['net', 'pool'], min: 1 },
  { group: 'Planetary model', key: 'interaction span', path: ['world', 'span'], min: 1 },
  { group: 'Planetary model', key: 'latency per hop', path: ['net', 'latency'], min: 0 },
  { group: 'Planetary model', key: 'sources', path: ['world', 'n_sources'], min: 1 },
  { group: 'Scale', key: 'sensor block size', path: ['net', 'scale'], min: 1 },
  { group: 'Size', key: 'rows', path: ['world', 'rows'], min: 3 },
  { group: 'Size', key: 'cols', path: ['world', 'cols'], min: 3 },
  { group: 'Speed', key: 'propagation c', path: ['world', 'c'], step: 0.25, min: 0.25 },
  { group: 'Speed', key: 'source period', path: ['world', 'source_period'], min: 10 },
  { group: 'Speed', key: 'sensor period', path: ['net', 'period'], min: 1 },
  { group: 'Research loop', key: 'generations', path: ['generations'], min: 1 },
  { group: 'Research loop', key: 'steps per generation', path: ['gen_steps'], min: 5 },
];
const DEFAULTS: Record<string, any> = { net: { n_sensors: 2, radius: 3, backaction: 0.05, wear: 0.08, pool: 30, latency: 1, scale: 1, period: 4 },
  world: { span: 2, n_sources: 3, rows: 8, cols: 12, c: 1, source_period: 28 }, generations: 8, gen_steps: 40 };
const read = (env: any, p: string[]) => (p.length === 1 ? env[p[0]] ?? DEFAULTS[p[0]] : env[p[0]]?.[p[1]] ?? DEFAULTS[p[0]][p[1]]);

function TotalObsSetup({ doc, edit }: { doc: StudyProtocol; edit: (f: (d: StudyProtocol) => void) => void }) {
  const [cond, setCond] = useState<any>(null);
  const [issues, setIssues] = useState<string[]>([]);
  const env = doc.environment;
  useEffect(() => {
    const { kind: _k, ...rest } = env;   // eslint-disable-line @typescript-eslint/no-unused-vars
    api.studyConditions(rest).then((r) => { setCond(r.conditions); setIssues(r.issues); }).catch((e) => setIssues([String(e)]));
  }, [env]);
  const groups = [...new Set(FIELDS.map((f) => f.group))];
  return (
    <Section title="Total-observation conditions (study environment)" note="These are the base conditions of every arm; an arm may override them (see its description). Scale, Size and Speed are separate groups of parameters, so each can be changed alone.">
      {groups.map((g) => (
        <div className="study-row" key={g}><b className="small" style={{ minWidth: 130 }}>{g}</b>
          {FIELDS.filter((f) => f.group === g).map((f) => (
            <label className="small" key={f.key}>{f.key} <input type="number" step={f.step ?? 1} min={f.min} style={{ width: 70 }} value={read(env, f.path as string[])}
              onChange={(e) => edit((d) => { if (f.path.length === 1) d.environment[f.path[0]] = +e.target.value; else { d.environment[f.path[0]] = { ...(d.environment[f.path[0]] ?? {}), [f.path[1]]: +e.target.value }; } })} /></label>
          ))}
        </div>))}
      {issues.length > 0 && <ul className="small warn">{issues.map((i) => <li key={i}>{i}</li>)}</ul>}
      {cond && <details><summary className="small">Planetary-scale structural conditions: {cond.n_met}/{cond.n} met{cond.all_met ? ' (all)' : ''} — synthetic model, no claim about the Earth</summary>
        <Table head={['condition', 'value', 'unit', 'threshold', 'met']} rows={cond.conditions.map((r: any) => [r.condition, fmt(r.value), r.unit, r.threshold, <Chip key="m" s={r.met ? 'ok' : 'not met'} />])} />
        <p className="small dim">{cond.note}</p></details>}
    </Section>
  );
}

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
            {['ards', 'shared-oi'].includes(doc.environment?.kind) ? (
              <label>Replicates (ARDS test block 3980–3989) <input type="number" min={1} max={10} value={seeds.list?.length ?? 1}
                onChange={(e) => edit((d) => { d.seeds = { list: Array.from({ length: Math.min(10, Math.max(1, +e.target.value)) }, (_, i) => [3980 + i, 3980 + i]) }; })} /></label>
            ) : <>
              <label>Seeds (n) <input type="number" min={1} value={seeds.n ?? seeds.list?.length ?? 1}
                onChange={(e) => edit((d) => { d.seeds = { ...(d.seeds.list ? { gen_base: d.seeds.list[0][0], engine_base: d.seeds.list[0][1] } : d.seeds), n: +e.target.value }; })} /></label>
              <label>Generator seed base <input type="number" value={seeds.gen_base ?? ''} onChange={(e) => edit((d) => { d.seeds.gen_base = +e.target.value; })} /></label>
              <label>Engine seed base <input type="number" value={seeds.engine_base ?? ''} onChange={(e) => edit((d) => { d.seeds.engine_base = +e.target.value; })} /></label>
            </>}
            {doc.environment?.kind === 'hpo-world' && <>
              <label>Horizon (steps, multiple of 60) <input type="number" step={60} min={60} value={doc.environment.horizon} onChange={(e) => edit((d) => { d.environment.horizon = +e.target.value; })} /></label>
              <label>World configurations <input type="number" min={100} step={100} value={doc.environment.world?.n ?? 800} onChange={(e) => edit((d) => { d.environment.world.n = +e.target.value; })} /></label>
              <label className="check"><input type="checkbox" checked={!!doc.environment.detect_shapes} onChange={(e) => edit((d) => { d.environment.detect_shapes = e.target.checked; })} /> run the shape detector</label>
            </>}
            <label>Timeout per run (s) <input type="number" min={1} value={doc.stop.timeout_per_run_s} onChange={(e) => edit((d) => { d.stop.timeout_per_run_s = +e.target.value; })} /></label>
            <label>Wall-clock budget (s) <input type="number" min={1} value={doc.stop.max_wall_seconds} onChange={(e) => edit((d) => { d.stop.max_wall_seconds = +e.target.value; })} /></label>
            <label>Primary metric <input value={(doc.metrics.primary ?? []).join(', ')} onChange={(e) => edit((d) => { d.metrics.primary = e.target.value.split(',').map((x) => x.trim()).filter(Boolean); })} /></label>
          </div>
          {doc.environment?.kind === 'total-observation' && <TotalObsSetup doc={doc} edit={edit} />}
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
          <Section title="Arm profiles (information · authority · policy · compute)">
            <Table head={['arm', 'controller', 'policy', 'meta', 'history', 'authority', 'budget/epoch', 'interventions', 'scenario']}
              rows={Object.entries(val.fairness?.profiles ?? {}).map(([n, p]: [string, any]) => [<span className="mono" key="n">{n}</span>, p.controller ?? p.policy,
                p.proposal_policy ?? (p.strong_revision ? p.strong_revision.join(', ') || '—' : '—'), String(p.meta_revision), String(p.history_reinsertion ?? p.history), Array.isArray(p.revision_authority) ? p.revision_authority.join(', ') : p.revision_authority,
                fmt(p.max_changes_per_epoch ?? p.compute?.max_ops_per_generation), p.interventions ?? '—', p.scenario ? JSON.stringify(p.scenario) : (p.environment && Object.keys(p.environment).length ? JSON.stringify(p.environment) : '—')])} />
          </Section>
          {val.fairness?.operations && (
            <Section title="Research operations: shared, arm-internal, not available"
              note="Shared operations are available to every arm in the same vocabulary; arm-internal ones are a capability of one method; 'not available' operations are named so that nothing is silently assumed.">
              <Table head={['operation', 'status', 'via', ...Object.keys(val.fairness.operations.access)]}
                rows={Object.entries(val.fairness.operations.operations).map(([op, v]) => [<span className="mono" key="o">{op}</span>, <Chip key="s" s={v.status} />,
                  <span className="small dim" key="v">{v.via}</span>, ...Object.values(val.fairness!.operations!.access).map((a, i) => <span key={i} className={a[op] ? 'up' : 'dim'}>{v.status === 'not available' ? '—' : a[op] ? 'yes' : 'no'}</span>)])} />
            </Section>
          )}
        </>
      )}
    </div>
  );
}
