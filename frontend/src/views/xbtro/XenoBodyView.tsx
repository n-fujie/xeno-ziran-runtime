// XenoBody / Total Observation: a simplified planar body (human-like or machine-like), local observation devices, interventions, and
// experiments whose records can be stored, exported, repeated and re-entered. Nothing here is a measurement of a real body.
import { useCallback, useEffect } from 'react';
import './xbtro.css';
import BodyScene, { type SceneData } from './BodyScene';
import { ExperimentsTab } from './ExperimentPanels';
import { HistoryTab, ScopeTab } from './HistoryScope';
import { BodyCreator, Devices, Interventions, LayerBar, LiveCharts, Lines, PartInspector, RunBar } from './LivePanels';
import { ComparePanel, RecordView } from './RecordPanels';
import { comFromAngles, observedPose, SEED } from './logic';
import { frames, obsStore, useXb, type Tab } from './store';

const TABS: { id: Tab; label: string }[] = [
  { id: 'body', label: 'Live body' }, { id: 'experiments', label: 'Experiments' }, { id: 'results', label: 'Results' },
  { id: 'history', label: 'History' }, { id: 'scope', label: 'Scope & Ziran' },
];

export default function XenoBodyView() {
  const init = useXb((s) => s.init);
  const catalog = useXb((s) => s.catalog);
  const tab = useXb((s) => s.tab);
  const error = useXb((s) => s.error);
  const notice = useXb((s) => s.notice);
  const body = useXb((s) => s.body);
  const record = useXb((s) => s.record);
  const compare = useXb((s) => s.compareWith);
  const { setTab, dismiss, pause } = useXb.getState();

  useEffect(() => { void init(); return () => pause(); }, [init, pause]);

  return (
    <div className="panel-view xb">
      <div className="xb-head">
        <h2>XenoBody / Total Observation</h2>
        <span className="small dim">a simplified planar body · nominal parameters · not a measurement of any real body</span>
      </div>
      <nav className="xb-tabs" aria-label="XenoBody sections">{TABS.map((t) => <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => setTab(t.id)}>{t.label}</button>)}</nav>
      {error && <div className="error" role="alert">{error} <button className="ghost" onClick={dismiss}>dismiss</button></div>}
      {notice && <div className="notice small" role="status">{notice} <button className="ghost" onClick={dismiss}>dismiss</button></div>}
      {!catalog ? <div className="dim">starting the research environment…</div> : (
        <>
          {tab === 'body' && <LiveTab />}
          {tab === 'experiments' && <ExperimentsTab catalog={catalog} />}
          {tab === 'results' && (record ? (
            <>
              <RecordView rec={record} catalog={catalog} />
              {compare && <ComparePanel a={record} b={compare} />}
            </>
          ) : <div className="small dim">No record is open. Run an experiment, or open one from the History.</div>)}
          {tab === 'history' && <HistoryTab />}
          {tab === 'scope' && <ScopeTab catalog={catalog} body={body} />}
        </>
      )}
    </div>
  );
}

function LiveTab() {
  const catalog = useXb((s) => s.catalog)!;
  const body = useXb((s) => s.body);
  const layer = useXb((s) => s.layer);
  const overlay = useXb((s) => s.overlay);
  const selected = useXb((s) => s.selected);
  const select = useXb((s) => s.select);

  const read = useCallback((): SceneData | null => {
    const b = useXb.getState().body;
    const f = frames.latest();
    if (!b || !f) return null;
    const r = f.reference;
    const pose = observedPose(b, obsStore, f.t);
    const hasPose = pose.source !== 'none';
    const emgModel = [...obsStore.models.entries()].find(([, m]) => m.kind === 'emg' && m.retired === null);
    let emg: (number | null)[] | null = null;
    if (emgModel) {
      const s = obsStore.holding(emgModel[0], f.t);
      if (s) emg = b.joints.map((j) => { const k = emgModel[1].channels.findIndex((c) => c === `emg:${j.id}`); return k >= 0 ? Math.min(1, (s.x[k] ?? 0) * 1.0) : null; });
    }
    const contact = [...obsStore.models.entries()].find(([, m]) => m.kind === 'contact' && m.retired === null);
    let obsCop: number | null = null;
    if (contact) { const s = obsStore.holding(contact[0], f.t); const k = contact[1].channels.indexOf('cop'); if (s && k >= 0) obsCop = s.x[k]; }
    return {
      t: f.t, theta: r.theta[SEED], drive: r.drive[SEED], cop: r.cop[SEED], com: r.com[SEED], xref: r.xref[SEED], pushForce: r.push_force[SEED], alive: !!r.alive[SEED],
      controllerCom: f.estimates.controller.com[SEED] ?? null, obsAngles: hasPose ? pose.angles : null, obsAge: pose.age, obsEmg: emg, obsCop,
      obsCom: hasPose ? comFromAngles(b, pose.angles) : null, linesActive: r.lines_active[SEED]?.reduce((a, x) => a + x, 0) ?? 0,
    };
  }, []);

  if (!body) {
    return (
      <div className="xb-grid">
        <section className="xb-col"><BodyCreator catalog={catalog} />
          <p className="small dim">Create a body to run it. A human-like and a machine-like planar body are provided, as nominal models with stated limits; other bodies can be added as presets with 2–8 links.</p></section>
        <aside className="xb-col" />
      </div>
    );
  }
  return (
    <div className="xb-live">
      <section className="xb-stage">
        <RunBar body={body} />
        <LayerBar />
        <div className="xb-canvas"><BodyScene info={body} layer={layer} overlay={overlay} selected={selected} onSelect={select} read={read} /></div>
        <div className="small dim">Drag to orbit · scroll or pinch to zoom · click a segment or joint to inspect it. Grey ring: the target; white dot: the reference COM; markers on the body are the observation devices.</div>
        <LiveCharts body={body} />
      </section>
      <aside className="xb-side">
        <BodyCreator catalog={catalog} />
        <Interventions catalog={catalog} body={body} />
        <Devices catalog={catalog} body={body} />
        <PartInspector body={body} />
        <Lines body={body} />
      </aside>
    </div>
  );
}
