import { useEffect, useState } from 'react';
import { api, type StudyAnalysis, type StudyDetail, type StudyRunRow } from '../../api/client';
import { Chip, Section, Table, fmt } from './common';

/* eslint-disable @typescript-eslint/no-explicit-any */
// What the Ziran records say: observation changes (who made them, what became visible and what was lost), reachability
// predicted versus what the operations then did, meta-revision of the controller's rules, history re-entry, the research
// agents (arms) and the shape detector's separated output.

function ArmCards({ study }: { study: StudyDetail }) {
  return (
    <ul className="hpo-rows">
      {study.protocol.arms.map((a: any) => {
        const p = study.fairness.profiles[a.name];
        return (
          <li key={a.name}>
            <b className="mono">{a.name}</b>
            <Chip s={p?.controller} />
            {p?.meta_revision && <span className="status-chip mono">meta-revision</span>}
            {p?.history_reinsertion && <span className="status-chip mono">history re-entry</span>}
            <span className="small dim">{a.description}</span>
            <span className="small mono dim">authority: {Array.isArray(p?.revision_authority) ? p.revision_authority.join(', ') : p?.revision_authority} · budget/epoch: {fmt(p?.max_changes_per_epoch)}</span>
          </li>
        );
      })}
    </ul>
  );
}

function ChangeList({ rec }: { rec: any }) {
  const rows = [...(rec.protocol_changes ?? []), ...(rec.controller_changes ?? [])].sort((a: any, b: any) => (a.t ?? 0) - (b.t ?? 0));
  if (!rows.length) return <p className="dim small">No configuration change in this run.</p>;
  return (
    <Table head={['epoch', 'by', 'path', 'value', 'why', 'opened', 'closed', 'channels +/−']}
      rows={rows.map((c: any) => [c.epoch, <Chip key="b" s={c.source} />, <span className="mono" key="p">{c.path}</span>, JSON.stringify(c.value), c.why ?? '—',
        c.reachability ? c.reachability.runnable_opened.length : '—', c.reachability ? c.reachability.runnable_closed.length : '—',
        c.reachability ? `${c.reachability.channels_opened.length}/${c.reachability.channels_closed.length}` : '—'])} />
  );
}

export default function ZiranPanel({ study, runs }: { study: StudyDetail; runs: StudyRunRow[] }) {
  const [an, setAn] = useState<StudyAnalysis | null>(null);
  const [sel, setSel] = useState<{ arm: string; k: number } | null>(null);
  const [rec, setRec] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api.studyAnalysis(study.id).then(setAn).catch(() => setAn(null));
  }, [study.id, study.has_analysis, runs.length]);
  useEffect(() => {
    if (!sel) { setRec(null); return; }
    api.studyRunRecord(study.id, sel.arm, sel.k).then(setRec).catch((e) => setErr(String(e)));
  }, [study.id, sel]);

  const z = an?.ziran ?? {};
  return (
    <div>
      <Section title="Research agents (arms)" note="Each arm is one research system: what it observes, what it may revise, and what it spends. Arms are compared on the same seeds.">
        <ArmCards study={study} />
      </Section>
      {!an && <p className="dim small">Analyse the study (Results tab) to aggregate the Ziran records across runs.</p>}
      {an && (
        <>
          <Section title="Observation changes and reachability" note="Opened = the operation could observe what it needs after the change; success = it acted in the next epoch. Opening is not success — the gap is the estimation error of the reachability record.">
            <Table head={['arm', 'controller', 'protocol', 'rejected', 'ch. gained', 'ch. lost', 'opened→acted', 'opened, not used', 'closed→silent']}
              rows={Object.entries(z).map(([arm, e]: [string, any]) => [<span className="mono" key="a">{arm}</span>, e.observation_changes.controller, e.observation_changes.protocol,
                e.observation_changes.rejected_by_authority_or_budget, e.observation_changes.channels_gained, e.observation_changes.channels_lost,
                e.reachability ? `${e.reachability.opened_then_acted}/${e.reachability.opened_predictions}` : '—', e.reachability ? e.reachability.opened_not_used : '—',
                e.reachability ? `${e.reachability.closed_consistent}/${e.reachability.closed_predictions}` : '—'])} />
          </Section>
          <Section title="Meta-revision of the revision rules" note="A revision changes the controller's own rule parameters after a rule's change failed to remove its blindness twice. Whether later changes were better is a separate contrast.">
            <ul className="hpo-rows">{Object.entries(z).filter(([, e]: [string, any]) => e.meta_revision).map(([arm, e]: [string, any]) => (
              <li key={arm}><b className="mono">{arm}</b><span className="mono small">{e.meta_revision.revisions} revisions in {e.meta_revision.runs_with_a_revision}/{e.meta_revision.runs_with_meta} runs ·
                {' '}{e.meta_revision.parameter_revisions} parameter · {e.meta_revision.exhausted_rules} exhausted</span></li>))}
              {!Object.values(z).some((e: any) => e.meta_revision) && <li className="dim small">No arm in this study revises its rules.</li>}</ul>
          </Section>
          <Section title="History re-entry">
            <Table head={['arm', 'runs with re-entry', 'reinsertions', 'with downstream event', 'share']}
              rows={Object.entries(z).filter(([, e]: [string, any]) => e.history_reentry).map(([arm, e]: [string, any]) => [<span className="mono" key="a">{arm}</span>,
                e.history_reentry.enabled_runs, e.history_reentry.reinsertions, e.history_reentry.with_downstream_event, fmt(e.history_reentry.downstream_share)])} />
          </Section>
          <Section title="Proposed variables">
            <ul className="hpo-rows">{Object.entries(z).map(([arm, e]: [string, any]) => (e.proposals?.length ? <li key={arm}><b className="mono">{arm}</b><span className="small dim">{e.proposals.join('; ')}</span></li> : null))}</ul>
            <p className="small dim">A proposal is not a validation; a variable without an implementation stays "proposed (no implementation; untestable here)".</p>
          </Section>
        </>
      )}
      <Section title="One run in detail" note="Choose a run to see every configuration change in order, with what each opened and closed.">
        <div className="study-row">
          <select value={sel ? `${sel.arm}#${sel.k}` : ''} onChange={(e) => { const [a, k] = e.target.value.split('#'); setSel(a ? { arm: a, k: +k } : null); }}>
            <option value="">—</option>{runs.filter((r) => r.status === 'ok').map((r) => <option key={`${r.arm}#${r.index}`} value={`${r.arm}#${r.index}`}>{r.arm} #{r.index}</option>)}
          </select>
        </div>
        {err && <div className="error">{err}</div>}
        {rec && (
          <>
            <ChangeList rec={rec} />
            {rec.controller?.meta_trace?.length > 0 && <Table head={['epoch', 'revision', 'reason', 'param', 'from → to']}
              rows={rec.controller.meta_trace.map((m: any) => [m.epoch, m.revision, m.reason, m.param ?? '—', m.revision === 'parameter' ? `${m.from} → ${m.to}` : 'exhausted'])} />}
            {rec.shape_detection && (
              <Section title="Shape detection (record · detector · interpretation)">
                <p className="small">Transition record: {rec.shape_detection.transition_record.source}, {rec.shape_detection.transition_record.steps} steps. Interpretation: <b>none produced</b>.</p>
                <p className="small dim">{rec.shape_detection.detector_limits}</p>
                <pre className="mono small study-pre">{JSON.stringify(rec.shape_detection.detector_output, null, 1).slice(0, 2500)}</pre>
              </Section>
            )}
          </>
        )}
      </Section>
    </div>
  );
}
