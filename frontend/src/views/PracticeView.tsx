import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type CommandReport, type ConfigView, type PracticeView as PV } from '../api/client';
import { useSim } from '../store/sim';

export default function PracticeView() {
  const info = useSim((s) => s.info);
  const log = useSim((s) => s.consoleLog);
  const run = useSim((s) => s.runCommand);
  const tickP = useSim((s) => s.practiceTick);
  const jobs = useSim((s) => s.jobs);
  const setView = useSim((s) => s.setView);
  const [pv, setPv] = useState<PV | null>(null);
  const [text, setText] = useState('');
  const [hist, setHist] = useState<string[]>([]);
  const [hi, setHi] = useState(-1);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { if (info) void api.practice(info.id).then(setPv); }, [info, tickP]);
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [log]);

  const suggestions = useMemo(() => {
    if (!pv || !text.trim()) return [];
    const w = text.trim().toLowerCase();
    return pv.grammar.filter((g) => g.toLowerCase().startsWith(w.split(' ')[0]) && g.toLowerCase() !== w).slice(0, 6);
  }, [pv, text]);

  const submit = (s: string) => {
    if (!s.trim()) return;
    setHist([s, ...hist.filter((h) => h !== s)].slice(0, 50));
    setHi(-1);
    setText('');
    void run(s);
  };

  return (
    <div className="practice">
      <div className="console">
        <p className="dim small">Enter a structured intervention. Each command is parsed by a fixed grammar (no language model),
          dependencies are traced, commitments rescored, the compiled operational effects shown, and a baseline-vs-intervention
          comparison is run on the live state. <b>apply</b> commits the draft to the running simulation; <b>discard</b> resets it.</p>
        <div className="console-log">
          {log.map((e) => (
            <div key={e.id} className="entry">
              <div className="mono cmd">› {e.text}</div>
              {e.error && <div className="warn small">{e.error}{e.suggestions?.length ? <div className="dim">try: {e.suggestions.map((s) => (
                <button key={s} className="link" onClick={() => setText(s)}>{s}</button>))}</div> : null}</div>}
              {e.report && <Report r={e.report} jobStatus={e.report.job ? jobs[e.report.job]?.status : undefined}
                onOpenCompare={() => setView('compare')} />}
              {!e.error && !e.report && <div className="dim small">…</div>}
            </div>
          ))}
          <div ref={end} />
        </div>
        <form className="console-input" onSubmit={(ev) => { ev.preventDefault(); submit(text); }}>
          <span className="mono">›</span>
          <input className="mono" value={text} placeholder="remove concept human" autoFocus spellCheck={false}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowUp' && hist.length) { const k = Math.min(hist.length - 1, hi + 1); setHi(k); setText(hist[k]); e.preventDefault(); }
              if (e.key === 'ArrowDown') { const k = hi - 1; setHi(k); setText(k >= 0 ? hist[k] : ''); e.preventDefault(); }
              if (e.key === 'Tab' && suggestions[0]) { setText(suggestions[0]); e.preventDefault(); }
            }} />
          <button type="submit">run</button>
        </form>
        {suggestions.length > 0 && <div className="suggest mono small">{suggestions.map((s) => (
          <button key={s} className="link" onClick={() => setText(s)}>{s}</button>))}</div>}
        {pv && <details className="small"><summary className="dim">grammar</summary>
          <ul className="mono">{pv.grammar.map((g) => <li key={g}><button className="link" onClick={() => setText(g)}>{g}</button></li>)}</ul>
          <p className="dim">Targets: <span className="mono">c123</span> (configuration), <span className="mono">@3.1</span> (cluster address),
            or a scenario set: <span className="mono">{pv.sets.join(', ')}</span></p></details>}
      </div>
      <div className="practice-side">
        {pv && <CommitmentGraph cfg={pv.draft} base={pv.applied} />}
        {pv && <ConfigPanel title="Draft (intervention)" cfg={pv.draft} />}
        {pv && <ConfigPanel title="Applied (baseline)" cfg={pv.applied} />}
      </div>
    </div>
  );
}

function Report({ r, jobStatus, onOpenCompare }: { r: CommandReport; jobStatus?: string; onOpenCompare: () => void }) {
  return (
    <div className="report small">
      <div className="dim">op <span className="mono">{r.command.op}</span> {JSON.stringify(r.command.args)}</div>
      {r.dependencies && (
        <div><b>1 · dependencies</b> of <span className="mono">{r.dependencies.token}</span>: direct [{r.dependencies.direct.join(', ') || '—'}],
          consequences [{r.dependencies.consequences.join(', ') || '—'}]
          {r.dependencies.incompatibilities.length > 0 && <>, incompatibilities {r.dependencies.incompatibilities.map((x) => x.join('⊥')).join(' ')}</>}</div>
      )}
      {r.commitment_changes && (
        <div><b>2 · commitments</b>{r.commitment_changes.length === 0 ? ' unchanged' : ''}
          <ul>{r.commitment_changes.map((c) => (
            <li key={c.claim}><span className="mono">{c.claim}</span> {c.before.commitment.toFixed(2)}{c.before.entitled ? '✓' : '✗'} →
              {' '}{c.after.commitment.toFixed(2)}{c.after.entitled ? '✓' : '✗'} <span className="dim">{c.after.status}</span></li>))}</ul></div>
      )}
      {r.operational_changes && (
        <div><b>3 · ignition conditions / gates</b>
          <ul>{diffProv(r.operational_changes.before, r.operational_changes.after).map((x, i) => <li key={i} className="mono">{x}</li>)}</ul></div>
      )}
      {r.job && <div><b>4–6 · rerun & compare</b> <span className="mono">{r.job}</span> {jobStatus ?? 'running'}
        {jobStatus === 'done' && <button className="link" onClick={onOpenCompare}>open comparison →</button>}</div>}
      {r.severed_connections !== undefined && <div>{r.severed_connections} connection(s) will be severed</div>}
      {r.grammar && <ul className="mono">{r.grammar.map((g) => <li key={g}>{g}</li>)}</ul>}
      {r.applied !== undefined && <div>draft applied to the live simulation</div>}
      {r.discarded && <div>draft discarded</div>}
      {r.score && <div className="mono">{Object.entries(r.score.status).map(([k, v]) => <div key={k}>{k}: {v}</div>)}</div>}
    </div>
  );
}

function diffProv(a: { source: string; effect: string }[], b: { source: string; effect: string }[]): string[] {
  const sa = new Set(a.map((p) => `${p.source}: ${p.effect}`));
  const sb = new Set(b.map((p) => `${p.source}: ${p.effect}`));
  const out = [...sa].filter((x) => !sb.has(x)).map((x) => `− ${x}`).concat([...sb].filter((x) => !sa.has(x)).map((x) => `+ ${x}`));
  return out.length ? out : ['no operational change'];
}

function ConfigPanel({ title, cfg }: { title: string; cfg: ConfigView }) {
  return (
    <div className="configpanel">
      <h4>{title}</h4>
      <table className="list small">
        <tbody>{cfg.practice.claims.map((c) => {
          const ent = cfg.score.entitled[c.id];
          const com = cfg.score.commitment[c.id] ?? 0;
          return (
            <tr key={c.id} className={ent ? '' : 'dim'}>
              <td className="mono">{c.id}</td>
              <td>{c.text}<div className="dim mono">uses {c.uses.join(', ') || '—'}{c.bindings.map((b) => ` · ${b.op} ${b.target}${b.factor !== undefined ? ' ' + b.factor : ''}`).join('')}</div></td>
              <td className="mono">{com.toFixed(2)}{ent ? ' ✓' : ''}</td>
            </tr>);
        })}</tbody>
      </table>
      <div className="small dim">removed concepts: {cfg.practice.removed_concepts.join(', ') || '—'} · withdrawn: {cfg.practice.withdrawn.join(', ') || '—'} ·
        removed boundaries: {cfg.removed_boundaries.join(', ') || '—'}</div>
      {cfg.direct.length + cfg.actions.length > 0 && <div className="small mono">{[...cfg.direct, ...cfg.actions].map((d, i) => <div key={i}>{d.text ?? d.kind}</div>)}</div>}
    </div>
  );
}

function CommitmentGraph({ cfg, base }: { cfg: ConfigView; base: ConfigView }) {
  const claims = cfg.practice.claims;
  const concepts = cfg.practice.concepts;
  const W = 420;
  const H = 60 + Math.max(claims.length, concepts.length) * 44;
  const cy = (i: number, n: number) => 40 + (i + 0.5) * ((H - 60) / Math.max(1, n));
  const cpos = Object.fromEntries(concepts.map((c, i) => [c, [60, cy(i, concepts.length)]]));
  const kpos = Object.fromEntries(claims.map((c, i) => [c.id, [W - 150, cy(i, claims.length)]]));
  const removed = new Set(cfg.practice.removed_concepts);
  return (
    <svg className="cgraph" viewBox={`0 0 ${W} ${H}`} width="100%">
      <text x={60} y={18} className="svg-dim" textAnchor="middle">concepts</text>
      <text x={W - 150} y={18} className="svg-dim" textAnchor="middle">claims · commitment</text>
      {claims.flatMap((c) => c.uses.filter((u) => cpos[u]).map((u) => (
        <line key={c.id + u} x1={cpos[u][0] + 40} y1={cpos[u][1]} x2={kpos[c.id][0] - 18} y2={kpos[c.id][1]}
          stroke={removed.has(u) ? '#ff5c48' : '#3a3a40'} strokeDasharray={removed.has(u) ? '3 3' : undefined} />)))}
      {cfg.practice.dependencies.flatMap((d, k) => d.premises.filter((p) => kpos[p]).map((p) => {
        const a = kpos[p];
        const b = kpos[d.conclusion];
        const bend = 60 + 14 * k;
        return <path key={`${k}${p}`} d={`M${a[0] + 18},${a[1]} C${a[0] + bend},${a[1]} ${b[0] + bend},${b[1]} ${b[0] + 18},${b[1]}`}
          fill="none" stroke={d.kind === 'committive' ? '#8f8f96' : '#5a5a61'} strokeDasharray={d.kind === 'permissive' ? '2 3' : undefined}
          markerEnd="url(#arr)" />;
      }))}
      {cfg.practice.incompatibilities.map(([a, b]) => kpos[a] && kpos[b] && (
        <line key={a + b} x1={kpos[a][0] - 18} y1={kpos[a][1]} x2={kpos[b][0] - 18} y2={kpos[b][1]} stroke="#ff5c48" strokeDasharray="1 3" />))}
      <defs><marker id="arr" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="5" markerHeight="5" orient="auto">
        <path d="M0,0 L6,3 L0,6 z" fill="#8f8f96" /></marker></defs>
      {concepts.map((c) => (
        <g key={c} transform={`translate(${cpos[c][0]},${cpos[c][1]})`}>
          <rect x={-40} y={-11} width={80} height={22} rx={3} fill="#0c0c0e" stroke={removed.has(c) ? '#ff5c48' : '#4a4a50'} />
          <text textAnchor="middle" y={4} className={removed.has(c) ? 'svg-removed' : 'svg-text'}>{c}</text>
        </g>))}
      {claims.map((c) => {
        const com = cfg.score.commitment[c.id] ?? 0;
        const ent = cfg.score.entitled[c.id];
        const was = (base.score.commitment[c.id] ?? 0) * (base.score.entitled[c.id] ? 1 : 0);
        const now = com * (ent ? 1 : 0);
        const col = now > was + 1e-9 ? '#78e696' : now < was - 1e-9 ? '#ff5c48' : '#8f8f96';
        return (
          <g key={c.id} transform={`translate(${kpos[c.id][0]},${kpos[c.id][1]})`}>
            <circle r={16} fill="#0c0c0e" stroke={col} strokeWidth={1.3} />
            <circle r={14 * com} fill={ent ? '#d8d8dc' : '#3a3a40'} opacity={0.35} />
            <text textAnchor="middle" y={4} className="svg-text">{c.id}</text>
            <text x={24} y={4} className="svg-dim">{com.toFixed(2)}{ent ? ' entitled' : ''}</text>
          </g>);
      })}
    </svg>
  );
}
