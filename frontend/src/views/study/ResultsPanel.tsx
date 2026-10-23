import { useState } from 'react';
import { api, type StudyAnalysis, type StudyDetail } from '../../api/client';
import { Chip, ModeBanner, Section, Table, fmt } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Statistical analysis: accounting, descriptives per arm, every declared contrast and metric (null and reversed effects
// included), multiplicity-adjusted p, effect sizes and intervals, sensitivity, and the declared criteria.

export default function ResultsPanel({ study, onChange }: { study: StudyDetail; onChange: () => void }) {
  const [an, setAn] = useState<StudyAnalysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [metric, setMetric] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = async (fresh: boolean) => {
    setErr(null);
    try { const a = fresh ? await api.studyAnalyse(study.id) : await api.studyAnalysis(study.id); setAn(a); setMetric((m) => m ?? a.metrics[0]); if (fresh) onChange(); }
    catch (e) { setErr(String(e)); }
  };
  if (!an && !err && study.has_analysis) void load(false);

  return (
    <div>
      <ModeBanner mode={study.mode} />
      <div className="study-row">
        <button className="on" onClick={() => void load(true)}>{study.has_analysis ? 'Re-run analysis' : 'Run analysis'}</button>
        <span className="small dim">Analysis reads the stored run records only; it can be repeated at any time.</span>
      </div>
      {err && <div className="error">{err}</div>}
      {an && (
        <>
          <Section title="Criteria" note={an.criteria.scope}>
            <p className="mono small"><b>{an.criteria.verdict}</b></p>
            <ul className="hpo-rows">{[...an.criteria.success.map((c: any) => ['success', c]), ...an.criteria.failure.map((c: any) => ['failure', c])].map(([k, c]: any, i: number) => (
              <li key={i}><span className="mono small">{k} · {c.contrast}/{c.metric} · {c.direction} ≥ {fmt(100 * (c.min_relative_effect ?? 0))}%</span><Chip s={c.result} />
                {c.ci95 && <span className="mono small dim">relative effect {fmt(c.observed_relative_effect)} · CI [{fmt(c.ci95[0])}, {fmt(c.ci95[1])}] · {c.n_pairs} pairs</span>}</li>))}</ul>
          </Section>
          <Section title="Runs and failures">
            <Table head={['arm', 'planned', 'ok', 'failed', 'timeout', 'not run', 'failure rate']}
              rows={Object.entries(an.accounting).map(([a, v]: [string, any]) => [<span className="mono" key="a">{a}</span>, v.planned, v.ok, v.failed, v.timeout, v.not_run, fmt(v.failure_rate)])} />
          </Section>
          <Section title="Contrasts" note="Every declared contrast and metric is listed, whatever it shows. p is a paired sign-flip permutation p; Holm and BH are over all contrasts × metrics. Status is the HPO classification (DETECTED needs Holm p < 0.01, ≥ 2% relative effect, and more than the noise floor).">
            <label className="small">Figure metric <select value={metric ?? ''} onChange={(e) => setMetric(e.target.value)}>{an.metrics.map((m: string) => <option key={m}>{m}</option>)}</select></label>
            {an.contrasts.map((c: any) => (
              <div key={c.id} className="study-contrast">
                <button className="link" onClick={() => setOpen(open === c.id ? null : c.id)}><b className="mono">{c.id}</b> {c.a} − {c.b}</button>
                <span className="small dim"> varies: {c.varies.join(', ') || '—'} · </span><Chip s={c.evidence} />
                {c.metrics[metric ?? '']?.n > 0 && <span className="mono small"> Δ {fmt(c.metrics[metric!].mean)} [{fmt(c.metrics[metric!].ci95[0])}, {fmt(c.metrics[metric!].ci95[1])}] <Chip s={c.metrics[metric!].status} /></span>}
                {open === c.id && (
                  <Table head={['metric', 'n', 'mean diff', '95% CI', 'dz', 'p', 'p Holm', 'p BH', 'status', 'LOO range', 'sign agr.']}
                    rows={Object.entries(c.metrics).map(([m, r]: [string, any]) => r.n ? [<span className="mono" key="m">{m}</span>, r.n, fmt(r.mean), `[${fmt(r.ci95[0])}, ${fmt(r.ci95[1])}]`, fmt(r.dz), fmt(r.p),
                      fmt(r.p_holm), fmt(r.p_bh), <Chip key="s" s={r.status} />, r.sensitivity?.leave_one_out_mean_range ? `${fmt(r.sensitivity.leave_one_out_mean_range[0])} … ${fmt(r.sensitivity.leave_one_out_mean_range[1])}` : '—',
                      fmt(r.sensitivity?.sign_agreement)] : [<span className="mono" key="m">{m}</span>, 0, '—', '—', '—', '—', '—', '—', <Chip key="s" s="NOT MEASURED" />, '—', '—'])} />
                )}
              </div>
            ))}
          </Section>
          <Section title={`Arms — ${metric}`}>
            <Table head={['arm', 'n', 'mean', 'median', 'SD', '95% CI of mean', 'min', 'max', 'undefined', 'outliers']}
              rows={an.arms.map((a: string) => { const d = an.descriptives[a][metric ?? '']; return d?.n ? [<span className="mono" key="a">{a}</span>, d.n, fmt(d.mean), fmt(d.median), fmt(d.sd),
                `[${fmt(d.ci95_mean[0])}, ${fmt(d.ci95_mean[1])}]`, fmt(d.min), fmt(d.max), d.undefined, (an.outliers[a]?.[metric ?? ''] ?? []).length] : [a, 0, '—', '—', '—', '—', '—', '—', '—', '—']; })} />
          </Section>
          {an.nonredundancy && (
            <Section title="Operational non-redundancy (assessment, not a finding)" note={an.nonredundancy.rule}>
              <p className="mono small"><b>{an.nonredundancy.verdict}</b></p>
              <Table head={['axis', 'comparable', 'indicators in this study', 'why']}
                rows={an.nonredundancy.axes.map((ax: any) => [ax.axis, <Chip key="c" s={ax.comparable ? 'comparable' : 'not comparable'} />, ax.indicators_in_this_study.join(', ') || '—', <span className="small dim" key="w">{ax.why}</span>])} />
              <p className="small dim">Not evaluable by this environment: {an.nonredundancy.not_evaluable_by_this_environment.join('; ')}.</p>
            </Section>
          )}
          <Section title="Censoring and fairness">
            <Table head={['arm', 'runs with censored first ignition', 'censoring point', 'stopped early']}
              rows={Object.entries(an.censoring).map(([a, v]: [string, any]) => [<span className="mono" key="a">{a}</span>, v.runs_with_censored_first_ignition, v.censoring_point, v.runs_stopped_early])} />
          </Section>
          {an.amendments.length > 0 && <Section title="Amendments after registration">
            <ul className="small">{an.amendments.map((a: any, i: number) => <li key={i}><span className="mono">{a.path}</span> — {a.status} ({a.reason})</li>)}</ul></Section>}
        </>
      )}
    </div>
  );
}
