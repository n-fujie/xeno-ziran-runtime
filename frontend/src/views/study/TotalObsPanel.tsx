import { useEffect, useState } from 'react';
import { api, type StudyAnalysis, type StudyDetail, type StudyRunRow } from '../../api/client';
import { Chip, Section, Table, fmt } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// The total-observation line: what the research loop did generation by generation (the ten items of each generation), what each operation did to the
// observable sets (reachability), the hypothesis tests against the verifier, rule revisions, the metric definitions, planetary-scale conditions,
// Scale / Size / Speed effects and the ontological ledger. Everything is read from the stored run records and the analysis; nothing is simulated here.

const OPS = (g: any) => (g.ops ?? []).map((o: any) => `${o.op}${o.sid ? ' ' + o.sid : ''}${o.value !== undefined ? '=' + JSON.stringify(o.value) : ''} [${o.status}] ← ${o.reason}`);

export function Conditions({ c }: { c: any }) {
  return (
    <>
      <p className="small dim">{c.note} Synthetic model; <b>earth_claim: {String(c.earth_claim)}</b>.</p>
      <Table head={['condition', 'value', 'unit', 'threshold', 'met']}
        rows={c.conditions.map((r: any) => [r.condition, fmt(r.value), r.unit, r.threshold, <Chip key="m" s={r.met ? 'ok' : 'not met'} />])} />
      <details className="small"><summary>Limits of the model and what a real-world claim would require</summary>
        <ul>{c.limits.map((l: string) => <li key={l}>{l}</li>)}</ul>
        <p className="dim">Requires: {c.requires_for_real_world_claims.join('; ')}.</p></details>
    </>
  );
}

export function Trace({ rec }: { rec: any }) {
  const t = rec.totalobs;
  const [open, setOpen] = useState<number | null>(null);
  const g = open === null ? null : t.generations[open];
  return (
    <div>
      <Table head={['gen', 'question', 'reasons found', 'operations (reason)', 'hypothesis test', 'evaluation', 'reachability', 'objects', 'verifier recall', 'rule revision']}
        rows={t.generations.map((x: any, i: number) => [
          <button key="b" className={open === i ? 'on' : ''} onClick={() => setOpen(open === i ? null : i)}>{x.gen}</button>,
          <span className="mono" key="q">{x.before.question}→{x.decision.question_next}</span>,
          <span className="small" key="r">{x.trigger.reasons.join(', ') || '—'}</span>,
          <span className="small" key="o">{OPS(x).join('; ') || '—'}</span>,
          x.hypothesis_test ? <span className="small" key="h">{x.hypothesis_test.outcome}{x.hypothesis_test.lag !== undefined ? ` (lag ${x.hypothesis_test.lag}${x.hypothesis_test.true_lag ? ` / verifier ${x.hypothesis_test.true_lag}` : ''})` : ''}</span> : '—',
          <span className="small" key="e">{x.evaluation.rule} {x.evaluation.satisfied ? '✓' : '✗'}</span>,
          <Chip key="l" s={x.levels.dynamic_effect} />,
          x.observation.objects.length, fmt(x.verifier.recall),
          x.rule_revision.map((m: any) => `${m.revision} ${m.param ?? m.reason}`).join('; ') || '—',
        ])} />
      {g && (
        <Section title={`Generation ${g.gen}: the ten items`} note="Before → trigger → changes → what became possible → what was executed → change in the object system (verifier) → new observation → next decision → failure / stop → revision of the rules themselves.">
          <ol className="small">
            <li><b>Before:</b> <span className="mono">{JSON.stringify({ ...g.before, sensors: Object.keys(g.before.sensors).length + ' sensors' })}</span></li>
            <li><b>Trigger:</b> reasons {g.trigger.reasons.join(', ') || 'none'}; harness events {g.trigger.events.map((e: any) => e.do).join(', ') || 'none'}; denied blocks {g.trigger.denied_blocks}</li>
            <li><b>Changes of condition:</b> {g.changes.map((c: any) => `${c.what}: ${JSON.stringify(c.from)} → ${JSON.stringify(c.to)} (${c.why})`).join('; ') || 'none'}</li>
            <li><b>Operations possible after (static {g.levels.static_effect}):</b> <span className="mono">{g.levels.static.available.join(' ')}</span></li>
            <li><b>Executed:</b> {OPS(g).join('; ') || 'none'}</li>
            <li><b>Object system (verifier-side):</b> true objects {g.world_delta.true_objects.join(' → ')}; marks added {fmt(g.world_delta.marks_added)}</li>
            <li><b>New observation:</b> {g.observation.n_records} records, coverage {fmt(g.observation.coverage)}, objects {g.observation.objects.map((o: any) => o.key).join(', ') || 'none'}; integration rule {g.integration.in_force} ({g.integration.effect})</li>
            <li><b>Decision:</b> next question {g.decision.question_next}; proposed {g.decision.proposed.length}, chosen {g.decision.chosen.length}, deferred (opportunity cost) {g.decision.deferred}</li>
            <li><b>Failure / stop:</b> expired sensors {g.failure.expired.join(', ') || 'none'}; outage regions {g.failure.outage_regions}; {g.stopped ? `STOPPED: ${g.stopped.reason}` : 'running'}</li>
            <li><b>Rule revision:</b> {g.rule_revision.length ? JSON.stringify(g.rule_revision.map((m: any) => ({ rule: m.reason, ...(m.param ? { param: m.param, from: m.from, to: m.to } : { exhausted: true }) }))) : 'none'}; rules in force {JSON.stringify(g.rules.params)}</li>
          </ol>
          <p className="small dim">Level sets this generation (before → dynamic): {Object.entries(g.levels.dynamic_compare).filter(([k]) => ['available', 'executable', 'identified', 'reachable_clusters', 'observable_cells'].includes(k))
            .map(([k, v]: any) => `${k} +${v.gained.length}/−${v.lost.length}`).join(' · ')}</p>
        </Section>
      )}
      <Section title="Ledger: what exists, who may read it" note={t.ledger.claims.statement}>
        <Table head={['layer', 'read by', 'content']} rows={Object.entries(t.ledger.layers).map(([k, v]: any) => [<span className="mono" key="k">{k}</span>, v.reader, <span className="small mono" key="c">{JSON.stringify(Object.fromEntries(Object.entries(v).filter(([a]) => a !== 'reader')))}</span>])} />
        <p className="small">Scope audit: {t.scope_audit.length ? <span className="warn">{t.scope_audit.join('; ')}</span> : <Chip s="ok" />}</p>
      </Section>
      <Section title="Metric definitions in this run" note="A number measured under a changed definition is not compared with the old one.">
        <Table head={['metric', 'version', 'unit', 'definition', 'history']} rows={Object.entries(t.metric_log.registry).map(([k, m]: any) => [<span className="mono" key="k">{k}</span>, m.version, m.unit, <span className="small" key="d">{m.definition}</span>, <span className="small dim" key="h">{m.history.map((h: any) => `v${h.version}: ${h.change}`).join(' | ')}</span>])} />
      </Section>
    </div>
  );
}

export default function TotalObsPanel({ study, runs }: { study: StudyDetail; runs: StudyRunRow[] }) {
  const [an, setAn] = useState<StudyAnalysis | null>(null);
  const [sel, setSel] = useState<{ arm: string; k: number } | null>(null);
  const [rec, setRec] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.studyAnalysis(study.id).then(setAn).catch(() => setAn(null)); }, [study.id, study.has_analysis, runs.length]);
  useEffect(() => {
    if (!sel) { setRec(null); return; }
    api.studyRunRecord(study.id, sel.arm, sel.k).then(setRec).catch((e) => setErr(String(e)));
  }, [study.id, sel]);

  if (study.protocol.environment?.kind !== 'total-observation') {
    return <p className="dim small">This study is not a total-observation study. Choose one of the templates total-observation, autonomous-loop, planetary-observation or sss-axes.</p>;
  }
  const to = an?.totalobs;
  const okRuns = runs.filter((r) => r.status === 'ok');
  return (
    <div>
      <div className="study-banner soft" role="note">A synthetic world, a finite model. Its state is not reality as a whole; what the agent identifies is a construction of its observing configuration; the verifier's scores are
        never given to an arm. Nothing here is a statement about the Earth or about any theory.</div>
      {!to && <p className="dim small">Run and analyse the study (Statistics tab) to aggregate the records across runs.</p>}
      {to && (
        <>
          <Section title="Per arm: what the loop found and did (counts)" note="Reasons are the agent's own statements about why its observing configuration was limited; reachability is static/dynamic per generation; hypothesis tests are checked against the verifier.">
            <Table head={['arm', 'runs', 'reasons found', 'operations executed by reason', 'reachability (dynamic)', 'hypothesis tests', 'supported but >50% off verifier', 'suppressed', 'metric breaks', 'stopped']}
              rows={Object.entries(to.arms).map(([a, e]: any) => [<span className="mono" key="a">{a}</span>, e.runs,
                <span className="small" key="r">{Object.entries(e.reasons).map(([k, v]) => `${k} ${v}`).join(', ') || '—'}</span>,
                <span className="small" key="x">{Object.entries(e.executed_by_reason).map(([k, v]) => `${k} ${v}`).join(', ') || '—'}</span>,
                <span className="small" key="d">{Object.entries(e.reachability.dynamic).map(([k, v]) => `${k} ${v}`).join(', ')}</span>,
                <span className="small" key="h">{Object.entries(e.hypothesis_tests).map(([k, v]) => `${k} ${v}`).join(', ') || '—'}</span>,
                e.supported_but_off_by_more_than_50pct_from_the_verifier, e.suppressed_decisions, e.metric_definition_breaks.total_breaks,
                <span className="small" key="s">{Object.entries(e.stopped).map(([k, v]) => `${k} ${v}`).join(', ')}</span>])} />
          </Section>
          {to.sss && (
            <Section title="Scale / Size / Speed" note={to.sss.note}>
              {to.sss.complete ? <Table head={['effect', 'value']} rows={[...Object.entries(to.sss.main).map(([k, v]: any) => [`main ${k}`, fmt(v)]), ...Object.entries(to.sss.interaction).map(([k, v]: any) => [`interaction ${k}`, fmt(v)])]} /> : <p className="small">{to.sss.note}</p>}
            </Section>
          )}
          <Section title="Planetary-scale structural conditions per arm" note="The count of regions or sensors does not satisfy them.">
            {Object.entries(to.planetary ?? {}).slice(0, 12).map(([a, c]: any) => c && (
              <details key={a}><summary><b className="mono">{a}</b> — {c.n_met}/{c.n} met{c.all_met ? ' (all)' : ''}</summary><Conditions c={c} /></details>))}
          </Section>
        </>
      )}
      <Section title="Follow one run" note="Pick an arm and a seed to see the research loop generation by generation.">
        <div className="study-row">
          <select aria-label="Run" value={sel ? `${sel.arm}#${sel.k}` : ''} onChange={(e) => { const [arm, k] = e.target.value.split('#'); setSel(arm ? { arm, k: +k } : null); }}>
            <option value="">—</option>{okRuns.map((r) => <option key={`${r.arm}#${r.index}`} value={`${r.arm}#${r.index}`}>{r.arm} #{r.index} (recall {fmt(r.metrics.recall_final)})</option>)}
          </select>
        </div>
        {err && <div className="error">{err}</div>}
        {rec?.totalobs && <Trace rec={rec} />}
      </Section>
    </div>
  );
}
